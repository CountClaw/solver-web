import logging
from typing import Any, Dict, Tuple

from quart import Quart, jsonify, request

from core.config import load_config
from core.db import init_db
from core.errors import error_response, processing_response, ready_response
from core.queue import RedisTaskQueue
from core.rate_limit import check_api_rate_limit
from core.repositories import (
    create_task,
    ensure_seed_data,
    get_api_key_by_value,
    get_task,
)
from core.settings_service import NetworkSettingsManager

logger = logging.getLogger(__name__)
cfg = load_config()

app = Quart(__name__)
queue = RedisTaskQueue(cfg)
network_settings = NetworkSettingsManager(queue)


def _validate_create_payload(payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any] | str]:
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

    normalized = {
        "taskType": task_type,
        "websiteURL": website_url,
        "websiteKey": website_key,
        "action": (task.get("action") or "").strip() or None,
        "cdata": (task.get("cData") or task.get("cdata") or "").strip() or None,
    }
    return True, normalized


async def _auth_client_key(payload: Dict[str, Any]):
    client_key = str(payload.get("clientKey") or "").strip()
    if not client_key:
        return None, jsonify(error_response("ERROR_KEY_MISSING", "缺少 clientKey")), 200

    api_key = get_api_key_by_value(client_key)
    if not api_key or not bool(api_key.get("enabled")):
        return None, jsonify(error_response("ERROR_KEY_DOES_NOT_EXIST", "无效或已禁用的 clientKey")), 200
    return api_key, None, None


@app.before_serving
async def _startup() -> None:
    init_db()
    ensure_seed_data()
    await queue.ensure_group()
    await network_settings.load_initial()
    await network_settings.start_listener()
    logger.info("API 服务启动完成")


@app.after_serving
async def _shutdown() -> None:
    await network_settings.close()
    await queue.close()


@app.get("/health")
async def health():
    return jsonify({"ok": True, "service": "solver-web-api"}), 200


@app.post("/createTask")
async def create_task_endpoint():
    payload = await request.get_json(force=True, silent=True) or {}
    api_key, error_obj, status_code = await _auth_client_key(payload)
    if error_obj:
        return error_obj, status_code

    allowed, retry_after = await check_api_rate_limit(
        queue.client,
        str(api_key["key"]),
        int(api_key.get("ratePerSecond") or cfg.api_default_rate_second),
        int(api_key.get("ratePerMinute") or cfg.api_default_rate_minute),
    )
    if not allowed:
        return jsonify(
            error_response(
                "ERROR_RATE_LIMIT",
                f"请求过于频繁，请在 {retry_after} 秒后重试",
            )
        ), 200

    valid, normalized_or_err = _validate_create_payload(payload)
    if not valid:
        return jsonify(error_response("ERROR_BAD_TASK_DATA", str(normalized_or_err))), 200

    task_data = normalized_or_err
    record = create_task(
        key_id=int(api_key["id"]),
        task_type=str(task_data["taskType"]),
        website_url=str(task_data["websiteURL"]),
        website_key=str(task_data["websiteKey"]),
        action=task_data.get("action"),
        cdata=task_data.get("cdata"),
        max_attempts=cfg.worker_max_attempts,
    )

    await queue.enqueue_task(
        {
            "task_id": str(record["id"]),
            "website_url": str(record["websiteURL"]),
            "website_key": str(record["websiteKey"]),
            "action": str(record["action"] or ""),
            "cdata": str(record["cdata"] or ""),
        }
    )

    return jsonify({"errorId": 0, "taskId": str(record["id"])}), 200


@app.post("/getTaskResult")
async def get_task_result_endpoint():
    payload = await request.get_json(force=True, silent=True) or {}
    api_key, error_obj, status_code = await _auth_client_key(payload)
    if error_obj:
        return error_obj, status_code

    task_id = str(payload.get("taskId") or "").strip()
    if not task_id:
        return jsonify(error_response("ERROR_TASKID_MISSING", "缺少 taskId")), 200

    record = get_task(task_id)
    if not record or int(record.get("keyId", -1)) != int(api_key["id"]):
        return jsonify(error_response("ERROR_TASK_NOT_FOUND", "任务不存在或无访问权限")), 200

    status = str(record.get("status") or "")
    if status in {"queued", "processing"}:
        return jsonify(processing_response()), 200
    if status == "ready":
        token = str(record.get("resultToken") or "")
        if token:
            return jsonify(ready_response(token)), 200
        return jsonify(error_response("ERROR_EMPTY_TOKEN", "任务已完成但 token 为空")), 200
    if status == "timeout":
        return jsonify(error_response("ERROR_TASK_TIMEOUT", str(record.get("errorDescription") or "任务超时"))), 200

    return jsonify(
        error_response(
            str(record.get("errorCode") or "ERROR_CAPTCHA_UNSOLVABLE"),
            str(record.get("errorDescription") or "验证码无法解析"),
        )
    ), 200


if __name__ == "__main__":
    app.run(host=cfg.api_host, port=cfg.api_port)

