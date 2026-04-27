import random
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests

from .config import Settings
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
    token: str | None
    node_url: str | None
    error_code: str | None
    error_description: str | None
    retryable: bool = False


class SolverClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.trust_env = False

    def _node_order(self) -> list[str]:
        urls = list(self.settings.solver_node_urls)
        random.shuffle(urls)
        return urls

    def _request(self, method: str, url: str) -> requests.Response:
        return request_with_proxy_fallback(
            self.session,
            method,
            url,
            proxy_url=self.settings.outbound_proxy_url,
            no_proxy=self.settings.outbound_no_proxy,
            connect_timeout_ms=self.settings.solver_connect_timeout_ms,
            read_timeout_ms=self.settings.solver_read_timeout_ms,
        )

    def _create_remote_task(self, node_url: str, task: dict[str, Any]) -> str:
        params = {
            "url": str(task.get("websiteURL") or ""),
            "sitekey": str(task.get("websiteKey") or ""),
        }
        action = task.get("action")
        cdata = task.get("cdata")
        if action:
            params["action"] = str(action)
        if cdata:
            params["cdata"] = str(cdata)

        url = f"{node_url.rstrip('/')}/turnstile?{urlencode(params)}"
        response = self._request("GET", url)
        response.raise_for_status()
        data = response.json()

        if int(data.get("errorId", 1)) != 0:
            raise SolverClientError(
                "SOLVER_CREATE_FAILED",
                str(data.get("errorDescription") or "solver 创建任务失败"),
                retryable=True,
            )

        task_id = str(data.get("taskId") or "").strip()
        if not task_id:
            raise SolverClientError(
                "SOLVER_INVALID_RESPONSE",
                "solver 返回缺少 taskId",
                retryable=True,
            )

        return task_id

    def _poll_remote_task(self, node_url: str, remote_task_id: str) -> str:
        deadline = time.time() + self.settings.solver_max_wait_seconds
        url = f"{node_url.rstrip('/')}/result?id={remote_task_id}"

        while time.time() < deadline:
            response = self._request("GET", url)
            response.raise_for_status()
            data = response.json()

            if int(data.get("errorId", 0)) == 0 and str(data.get("status") or "").lower() == "ready":
                token = str(((data.get("solution") or {}).get("token")) or "").strip()
                if token:
                    return token
                raise SolverClientError("SOLVER_EMPTY_TOKEN", "solver 返回空 token", retryable=True)

            status = str(data.get("status") or "").lower()
            if status == "processing":
                time.sleep(self.settings.solver_poll_interval_ms / 1000.0)
                continue

            if int(data.get("errorId", 0)) != 0:
                raise SolverClientError(
                    str(data.get("errorCode") or "SOLVER_TASK_FAILED"),
                    str(data.get("errorDescription") or "solver 任务失败"),
                    retryable=False,
                )

            time.sleep(self.settings.solver_poll_interval_ms / 1000.0)

        raise SolverClientError("SOLVER_TIMEOUT", "等待 solver 结果超时", retryable=True)

    def solve_turnstile(self, task: dict[str, Any]) -> SolverResult:
        errors: list[SolverClientError] = []

        for node_url in self._node_order():
            try:
                remote_task_id = self._create_remote_task(node_url, task)
                token = self._poll_remote_task(node_url, remote_task_id)
                return SolverResult(
                    ok=True,
                    token=token,
                    node_url=node_url,
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
        return SolverResult(
            ok=False,
            token=None,
            node_url=None,
            error_code=first.code,
            error_description=first.message,
            retryable=any(item.retryable for item in errors),
        )
