from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedTask:
    task_type: str
    website_url: str
    website_key: str
    action: str | None
    cdata: str | None

    def to_solver_payload(self) -> dict[str, str | None]:
        return {
            "taskType": self.task_type,
            "websiteURL": self.website_url,
            "websiteKey": self.website_key,
            "action": self.action,
            "cdata": self.cdata,
        }


def validate_solve_payload(payload: dict[str, Any]) -> tuple[bool, NormalizedTask | str]:
    task = payload.get("task")
    if not isinstance(task, dict):
        return False, "请求缺少 task 对象"

    task_type = str(task.get("type") or "").strip()
    if task_type != "TurnstileTaskProxyless":
        return False, "当前仅支持 TurnstileTaskProxyless"

    website_url = str(task.get("websiteURL") or "").strip()
    website_key = str(task.get("websiteKey") or "").strip()
    if not website_url or not website_key:
        return False, "websiteURL 和 websiteKey 为必填参数"

    return True, NormalizedTask(
        task_type=task_type,
        website_url=website_url,
        website_key=website_key,
        action=(task.get("action") or "").strip() or None,
        cdata=(task.get("cData") or task.get("cdata") or "").strip() or None,
    )
