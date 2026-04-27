from .config import Settings
from .responses import error_response


def validate_client_key(client_key: str, settings: Settings) -> tuple[bool, dict, int]:
    if not client_key:
        return False, error_response("ERROR_KEY_MISSING", "缺少 clientKey"), 200

    if not settings.client_keys:
        return False, error_response("ERROR_SERVER_MISCONFIGURED", "服务端未配置 CLIENT_KEYS"), 503

    if client_key not in settings.client_keys:
        return False, error_response("ERROR_KEY_DOES_NOT_EXIST", "无效的 clientKey"), 200

    return True, {}, 200
