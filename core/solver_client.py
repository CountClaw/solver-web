import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from .config import AppConfig, load_config
from .proxy import is_network_exception, request_with_proxy_fallback


class SolverClientError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass
class SolverResult:
    ok: bool
    token: Optional[str]
    node_url: Optional[str]
    error_code: Optional[str]
    error_description: Optional[str]
    retryable: bool = False


class SolverClient:
    def __init__(self, cfg: AppConfig | None = None):
        self.cfg = cfg or load_config()
        self.session = requests.Session()

    def _node_order(self) -> List[str]:
        urls = list(self.cfg.solver_node_urls)
        random.shuffle(urls)
        return urls

    def _create_remote_task(
        self,
        node_url: str,
        website_url: str,
        website_key: str,
        action: Optional[str],
        cdata: Optional[str],
        network_setting: Dict[str, Any],
    ) -> str:
        base = node_url.rstrip("/")
        params = {"url": website_url, "sitekey": website_key}
        if action:
            params["action"] = action
        if cdata:
            params["cdata"] = cdata
        url = f"{base}/turnstile?{urlencode(params)}"
        response = request_with_proxy_fallback(
            self.session,
            "GET",
            url,
            network_setting,
            default_connect_timeout_ms=self.cfg.solver_connect_timeout_ms,
            default_read_timeout_ms=self.cfg.solver_read_timeout_ms,
        )
        response.raise_for_status()
        data = response.json()
        if int(data.get("errorId", 1)) != 0:
            raise SolverClientError(
                "SOLVER_CREATE_FAILED",
                str(data.get("errorDescription") or "solver 创建任务失败"),
                retryable=True,
            )
        task_id = (data.get("taskId") or "").strip()
        if not task_id:
            raise SolverClientError("SOLVER_INVALID_RESPONSE", "solver 返回缺少 taskId", retryable=True)
        return task_id

    def _poll_remote_task(self, node_url: str, remote_task_id: str, network_setting: Dict[str, Any]) -> str:
        base = node_url.rstrip("/")
        deadline = time.time() + self.cfg.solver_max_wait_seconds
        while time.time() < deadline:
            url = f"{base}/result?id={remote_task_id}"
            response = request_with_proxy_fallback(
                self.session,
                "GET",
                url,
                network_setting,
                default_connect_timeout_ms=self.cfg.solver_connect_timeout_ms,
                default_read_timeout_ms=self.cfg.solver_read_timeout_ms,
            )
            response.raise_for_status()
            data = response.json()
            if int(data.get("errorId", 0)) == 0 and str(data.get("status")) == "ready":
                token = (((data.get("solution") or {}).get("token")) or "").strip()
                if token:
                    return token
                raise SolverClientError("SOLVER_EMPTY_TOKEN", "solver 返回空 token", retryable=True)

            status = str(data.get("status") or "").lower()
            if status == "processing":
                time.sleep(self.cfg.solver_poll_interval_ms / 1000.0)
                continue

            if int(data.get("errorId", 0)) != 0:
                desc = str(data.get("errorDescription") or "solver 任务失败")
                code = str(data.get("errorCode") or "SOLVER_TASK_FAILED")
                raise SolverClientError(code, desc, retryable=False)

            time.sleep(self.cfg.solver_poll_interval_ms / 1000.0)

        raise SolverClientError("SOLVER_TIMEOUT", "等待 solver 结果超时", retryable=True)

    def solve_turnstile(self, task: Dict[str, Any], network_setting: Dict[str, Any]) -> SolverResult:
        errors: List[SolverClientError] = []
        for node in self._node_order():
            try:
                remote_task_id = self._create_remote_task(
                    node_url=node,
                    website_url=str(task.get("websiteURL") or ""),
                    website_key=str(task.get("websiteKey") or ""),
                    action=task.get("action"),
                    cdata=task.get("cdata"),
                    network_setting=network_setting,
                )
                token = self._poll_remote_task(node, remote_task_id, network_setting)
                return SolverResult(
                    ok=True,
                    token=token,
                    node_url=node,
                    error_code=None,
                    error_description=None,
                    retryable=False,
                )
            except SolverClientError as exc:
                errors.append(exc)
            except Exception as exc:
                if is_network_exception(exc):
                    errors.append(SolverClientError("SOLVER_NETWORK_ERROR", str(exc), retryable=True))
                else:
                    errors.append(SolverClientError("SOLVER_UNKNOWN_ERROR", str(exc), retryable=True))

        if not errors:
            return SolverResult(
                ok=False,
                token=None,
                node_url=None,
                error_code="NO_SOLVER_NODE",
                error_description="未配置可用 solver 节点",
                retryable=False,
            )

        first = errors[0]
        retryable = any(err.retryable for err in errors)
        return SolverResult(
            ok=False,
            token=None,
            node_url=None,
            error_code=first.code,
            error_description=first.message,
            retryable=retryable,
        )

