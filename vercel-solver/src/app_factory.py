import asyncio
from typing import Any

from quart import Quart, jsonify, request

from .auth import validate_client_key
from .config import Settings, load_settings
from .responses import deprecated_response, error_response, ready_response
from .solver_client import SolverClient
from .validators import validate_solve_payload

DEPRECATED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


def create_app(
    *,
    settings: Settings | None = None,
    solver_client: SolverClient | Any | None = None,
) -> Quart:
    resolved_settings = settings or load_settings()
    resolved_solver_client = solver_client or SolverClient(resolved_settings)

    app = Quart(__name__)
    app.config["SETTINGS"] = resolved_settings
    app.config["SOLVER_CLIENT"] = resolved_solver_client

    @app.get("/health")
    async def health():
        return jsonify(
            {
                "ok": True,
                "service": "vercel-solver",
                "mode": "sync",
            }
        ), 200

    @app.post("/solve")
    async def solve():
        payload: dict[str, Any] = await request.get_json(force=True, silent=True) or {}
        client_key = str(payload.get("clientKey") or "").strip()

        allowed, error_obj, status_code = validate_client_key(client_key, resolved_settings)
        if not allowed:
            return jsonify(error_obj), status_code

        valid, normalized_or_error = validate_solve_payload(payload)
        if not valid:
            return jsonify(error_response("ERROR_BAD_TASK_DATA", str(normalized_or_error))), 200

        result = await asyncio.to_thread(
            resolved_solver_client.solve_turnstile,
            normalized_or_error.to_solver_payload(),
        )
        if result.ok and result.token:
            return jsonify(ready_response(result.token)), 200

        return jsonify(
            error_response(
                str(result.error_code or "SOLVER_FAILED"),
                str(result.error_description or "solver 处理失败"),
            )
        ), 200

    @app.post("/createTask")
    async def create_task_deprecated():
        return jsonify(deprecated_response()), 410

    @app.post("/getTaskResult")
    async def get_task_result_deprecated():
        return jsonify(deprecated_response()), 410

    @app.route("/admin", defaults={"path": ""}, methods=DEPRECATED_METHODS)
    @app.route("/admin/<path:path>", methods=DEPRECATED_METHODS)
    async def admin_deprecated(path: str):
        return jsonify(deprecated_response()), 410

    return app
