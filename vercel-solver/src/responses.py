from typing import Any


def error_response(error_code: str, error_description: str, error_id: int = 1) -> dict[str, Any]:
    return {
        "errorId": int(error_id),
        "errorCode": error_code,
        "errorDescription": error_description,
    }


def ready_response(token: str) -> dict[str, Any]:
    return {
        "errorId": 0,
        "status": "ready",
        "solution": {
            "token": token,
        },
    }


def deprecated_response() -> dict[str, Any]:
    return error_response(
        "ERROR_UNSUPPORTED_ENDPOINT",
        "该接口已废弃，请改用 POST /solve",
    )
