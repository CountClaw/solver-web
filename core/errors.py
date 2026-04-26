from typing import Any, Dict


def error_response(error_code: str, error_description: str, error_id: int = 1) -> Dict[str, Any]:
    return {
        "errorId": int(error_id),
        "errorCode": error_code,
        "errorDescription": error_description,
    }


def processing_response() -> Dict[str, Any]:
    return {
        "errorId": 0,
        "status": "processing",
    }


def ready_response(token: str) -> Dict[str, Any]:
    return {
        "errorId": 0,
        "status": "ready",
        "solution": {
            "token": token,
        },
    }

