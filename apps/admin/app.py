import logging
from functools import wraps
from typing import Any, Callable, Dict

from quart import Quart, jsonify, request

from core.config import load_config
from core.db import init_db
from core.errors import error_response
from core.queue import RedisTaskQueue
from core.repositories import (
    create_api_key,
    ensure_seed_data,
    list_api_keys,
    list_solver_nodes,
    list_tasks,
    patch_api_key,
)
from core.settings_service import NetworkSettingsManager

logger = logging.getLogger(__name__)
cfg = load_config()

app = Quart(__name__)
queue = RedisTaskQueue(cfg)
network_settings = NetworkSettingsManager(queue)


def _admin_required(handler: Callable):
    @wraps(handler)
    async def wrapped(*args, **kwargs):
        token = (request.headers.get("X-Admin-Token") or "").strip()
        if token != cfg.admin_token:
            return jsonify(error_response("ERROR_ADMIN_UNAUTHORIZED", "管理员令牌无效")), 401
        return await handler(*args, **kwargs)

    return wrapped


@app.before_serving
async def _startup() -> None:
    init_db()
    ensure_seed_data()
    await network_settings.load_initial()
    await network_settings.start_listener()
    logger.info("Admin 服务启动完成")


@app.after_serving
async def _shutdown() -> None:
    await network_settings.close()
    await queue.close()


@app.get("/health")
async def health():
    return jsonify({"ok": True, "service": "solver-web-admin"}), 200


@app.get("/admin/settings/network")
@_admin_required
async def get_network_settings():
    return jsonify({"errorId": 0, "data": await network_settings.get_current()}), 200


@app.put("/admin/settings/network")
@_admin_required
async def update_network_settings():
    payload: Dict[str, Any] = await request.get_json(force=True, silent=True) or {}
    if "proxyURL" in payload:
        proxy = str(payload.get("proxyURL") or "").strip()
        if proxy and not (proxy.startswith("http://") or proxy.startswith("https://")):
            return jsonify(error_response("ERROR_BAD_PROXY", "proxyURL 必须以 http:// 或 https:// 开头")), 400
    if "connectTimeoutMs" in payload:
        payload["connectTimeoutMs"] = max(300, int(payload.get("connectTimeoutMs") or 300))
    if "readTimeoutMs" in payload:
        payload["readTimeoutMs"] = max(300, int(payload.get("readTimeoutMs") or 300))
    data = await network_settings.update(payload)
    return jsonify({"errorId": 0, "data": data}), 200


@app.get("/admin/keys")
@_admin_required
async def get_keys():
    return jsonify({"errorId": 0, "data": list_api_keys()}), 200


@app.post("/admin/keys")
@_admin_required
async def post_key():
    payload: Dict[str, Any] = await request.get_json(force=True, silent=True) or {}
    name = str(payload.get("name") or "").strip() or "default"
    note = str(payload.get("note") or "").strip()
    rate_s = int(payload.get("ratePerSecond") or cfg.api_default_rate_second)
    rate_m = int(payload.get("ratePerMinute") or cfg.api_default_rate_minute)
    key_value = str(payload.get("key") or "").strip() or None
    item = create_api_key(
        name=name,
        rate_per_second=rate_s,
        rate_per_minute=rate_m,
        note=note,
        key_value=key_value,
    )
    return jsonify({"errorId": 0, "data": item}), 201


@app.patch("/admin/keys/<int:key_id>")
@_admin_required
async def patch_key(key_id: int):
    payload: Dict[str, Any] = await request.get_json(force=True, silent=True) or {}
    item = patch_api_key(key_id, payload)
    if not item:
        return jsonify(error_response("ERROR_KEY_NOT_FOUND", "未找到对应 API Key")), 404
    return jsonify({"errorId": 0, "data": item}), 200


@app.get("/admin/tasks")
@_admin_required
async def get_tasks():
    status = (request.args.get("status") or "").strip() or None
    limit = int(request.args.get("limit") or 100)
    data = list_tasks(status=status, limit=limit)
    return jsonify({"errorId": 0, "data": data}), 200


@app.get("/admin/solvers")
@_admin_required
async def get_solvers():
    return jsonify({"errorId": 0, "data": list_solver_nodes()}), 200


if __name__ == "__main__":
    app.run(host=cfg.admin_host, port=cfg.admin_port)

