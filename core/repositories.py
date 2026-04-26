import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import desc, select

from .config import load_config
from .db import session_scope
from .models import ApiKey, NetworkSetting, SolverNodeStatus, TaskRecord


def _utcnow() -> datetime:
    return datetime.utcnow()


def _serialize_api_key(row: ApiKey) -> Dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "key": row.key_value,
        "enabled": row.enabled,
        "ratePerSecond": row.rate_per_second,
        "ratePerMinute": row.rate_per_minute,
        "note": row.note or "",
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_task(row: TaskRecord) -> Dict[str, Any]:
    return {
        "id": row.id,
        "keyId": row.key_id,
        "taskType": row.task_type,
        "websiteURL": row.website_url,
        "websiteKey": row.website_key,
        "action": row.action,
        "cdata": row.cdata,
        "status": row.status,
        "resultToken": row.result_token,
        "errorCode": row.error_code,
        "errorDescription": row.error_description,
        "attempts": row.attempts,
        "maxAttempts": row.max_attempts,
        "solverNode": row.solver_node,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "queuedAt": row.queued_at.isoformat() if row.queued_at else None,
        "startedAt": row.started_at.isoformat() if row.started_at else None,
        "finishedAt": row.finished_at.isoformat() if row.finished_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_network_setting(row: NetworkSetting) -> Dict[str, Any]:
    return {
        "enabled": bool(row.enabled),
        "proxyURL": (row.proxy_url or "").strip(),
        "noProxy": (row.no_proxy or "").strip(),
        "connectTimeoutMs": int(row.connect_timeout_ms),
        "readTimeoutMs": int(row.read_timeout_ms),
        "version": int(row.version),
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def ensure_seed_data() -> None:
    cfg = load_config()
    with session_scope() as session:
        setting = session.get(NetworkSetting, 1)
        if not setting:
            session.add(
                NetworkSetting(
                    id=1,
                    enabled=False,
                    proxy_url=None,
                    no_proxy=cfg.default_no_proxy,
                    connect_timeout_ms=3000,
                    read_timeout_ms=7000,
                    version=1,
                )
            )


def create_api_key(
    name: str,
    rate_per_second: int,
    rate_per_minute: int,
    note: str = "",
    key_value: Optional[str] = None,
) -> Dict[str, Any]:
    key = key_value or f"swk_{secrets.token_urlsafe(24)}"
    with session_scope() as session:
        record = ApiKey(
            name=name.strip() or "default",
            key_value=key,
            enabled=True,
            rate_per_second=max(1, int(rate_per_second)),
            rate_per_minute=max(1, int(rate_per_minute)),
            note=note.strip() or None,
        )
        session.add(record)
        session.flush()
        session.refresh(record)
        return _serialize_api_key(record)


def list_api_keys() -> List[Dict[str, Any]]:
    with session_scope() as session:
        rows = session.execute(select(ApiKey).order_by(ApiKey.id.asc())).scalars().all()
        return [_serialize_api_key(row) for row in rows]


def get_api_key_by_value(key_value: str) -> Optional[Dict[str, Any]]:
    with session_scope() as session:
        row = session.execute(select(ApiKey).where(ApiKey.key_value == key_value)).scalar_one_or_none()
        return _serialize_api_key(row) if row else None


def patch_api_key(key_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with session_scope() as session:
        row = session.get(ApiKey, key_id)
        if not row:
            return None
        if "name" in payload:
            row.name = (payload.get("name") or row.name).strip()
        if "enabled" in payload:
            row.enabled = bool(payload.get("enabled"))
        if "ratePerSecond" in payload:
            row.rate_per_second = max(1, int(payload.get("ratePerSecond") or row.rate_per_second))
        if "ratePerMinute" in payload:
            row.rate_per_minute = max(1, int(payload.get("ratePerMinute") or row.rate_per_minute))
        if "note" in payload:
            row.note = (payload.get("note") or "").strip() or None
        row.updated_at = _utcnow()
        session.flush()
        session.refresh(row)
        return _serialize_api_key(row)


def create_task(
    key_id: int,
    task_type: str,
    website_url: str,
    website_key: str,
    action: Optional[str],
    cdata: Optional[str],
    max_attempts: int,
) -> Dict[str, Any]:
    with session_scope() as session:
        task_id = uuid4().hex
        row = TaskRecord(
            id=task_id,
            key_id=key_id,
            task_type=task_type,
            website_url=website_url.strip(),
            website_key=website_key.strip(),
            action=(action or "").strip() or None,
            cdata=(cdata or "").strip() or None,
            status="queued",
            attempts=0,
            max_attempts=max(1, int(max_attempts)),
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        return _serialize_task(row)


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    with session_scope() as session:
        row = session.get(TaskRecord, task_id)
        return _serialize_task(row) if row else None


def mark_task_processing(task_id: str) -> Optional[Dict[str, Any]]:
    with session_scope() as session:
        row = session.get(TaskRecord, task_id)
        if not row:
            return None
        row.status = "processing"
        if not row.started_at:
            row.started_at = _utcnow()
        row.updated_at = _utcnow()
        session.flush()
        session.refresh(row)
        return _serialize_task(row)


def mark_task_retry(task_id: str, attempts: int, error_code: str, error_description: str) -> Optional[Dict[str, Any]]:
    with session_scope() as session:
        row = session.get(TaskRecord, task_id)
        if not row:
            return None
        row.status = "queued"
        row.attempts = max(0, int(attempts))
        row.error_code = error_code
        row.error_description = error_description
        row.updated_at = _utcnow()
        session.flush()
        session.refresh(row)
        return _serialize_task(row)


def mark_task_ready(task_id: str, token: str, solver_node: Optional[str]) -> Optional[Dict[str, Any]]:
    with session_scope() as session:
        row = session.get(TaskRecord, task_id)
        if not row:
            return None
        row.status = "ready"
        row.result_token = token
        row.error_code = None
        row.error_description = None
        row.solver_node = solver_node
        row.finished_at = _utcnow()
        row.updated_at = _utcnow()
        session.flush()
        session.refresh(row)
        return _serialize_task(row)


def mark_task_failed(
    task_id: str,
    error_code: str,
    error_description: str,
    solver_node: Optional[str] = None,
    status: str = "failed",
) -> Optional[Dict[str, Any]]:
    with session_scope() as session:
        row = session.get(TaskRecord, task_id)
        if not row:
            return None
        row.status = status
        row.error_code = error_code
        row.error_description = error_description
        row.solver_node = solver_node
        row.finished_at = _utcnow()
        row.updated_at = _utcnow()
        session.flush()
        session.refresh(row)
        return _serialize_task(row)


def list_tasks(status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 500))
    with session_scope() as session:
        query = select(TaskRecord).order_by(desc(TaskRecord.created_at)).limit(safe_limit)
        if status:
            query = query.where(TaskRecord.status == status.strip())
        rows = session.execute(query).scalars().all()
        return [_serialize_task(row) for row in rows]


def get_network_setting() -> Dict[str, Any]:
    with session_scope() as session:
        row = session.get(NetworkSetting, 1)
        if not row:
            cfg = load_config()
            row = NetworkSetting(
                id=1,
                enabled=False,
                proxy_url=None,
                no_proxy=cfg.default_no_proxy,
                connect_timeout_ms=3000,
                read_timeout_ms=7000,
                version=1,
            )
            session.add(row)
            session.flush()
            session.refresh(row)
        return _serialize_network_setting(row)


def update_network_setting(payload: Dict[str, Any]) -> Dict[str, Any]:
    with session_scope() as session:
        row = session.get(NetworkSetting, 1)
        if not row:
            row = NetworkSetting(id=1, version=1)
            session.add(row)
            session.flush()
        if "enabled" in payload:
            row.enabled = bool(payload.get("enabled"))
        if "proxyURL" in payload:
            proxy_url = (payload.get("proxyURL") or "").strip()
            row.proxy_url = proxy_url or None
        if "noProxy" in payload:
            row.no_proxy = (payload.get("noProxy") or "").strip() or "localhost,127.0.0.1,::1"
        if "connectTimeoutMs" in payload:
            row.connect_timeout_ms = max(300, int(payload.get("connectTimeoutMs") or row.connect_timeout_ms))
        if "readTimeoutMs" in payload:
            row.read_timeout_ms = max(300, int(payload.get("readTimeoutMs") or row.read_timeout_ms))
        row.version = int(row.version) + 1
        row.updated_at = _utcnow()
        session.flush()
        session.refresh(row)
        return _serialize_network_setting(row)


def upsert_solver_node_status(node_url: str, status: str, pending_tasks: int, last_error: Optional[str]) -> Dict[str, Any]:
    with session_scope() as session:
        row = session.get(SolverNodeStatus, node_url)
        if not row:
            row = SolverNodeStatus(
                node_url=node_url,
                status=status,
                pending_tasks=max(0, int(pending_tasks)),
                last_error=last_error or None,
                last_seen_at=_utcnow(),
            )
            session.add(row)
        else:
            row.status = status
            row.pending_tasks = max(0, int(pending_tasks))
            row.last_error = (last_error or "").strip() or None
            row.last_seen_at = _utcnow()
            row.updated_at = _utcnow()
        session.flush()
        session.refresh(row)
        return {
            "nodeURL": row.node_url,
            "status": row.status,
            "pendingTasks": row.pending_tasks,
            "lastError": row.last_error,
            "lastSeenAt": row.last_seen_at.isoformat() if row.last_seen_at else None,
            "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        }


def list_solver_nodes() -> List[Dict[str, Any]]:
    with session_scope() as session:
        rows = session.execute(select(SolverNodeStatus).order_by(SolverNodeStatus.node_url.asc())).scalars().all()
        return [
            {
                "nodeURL": row.node_url,
                "status": row.status,
                "pendingTasks": row.pending_tasks,
                "lastError": row.last_error,
                "lastSeenAt": row.last_seen_at.isoformat() if row.last_seen_at else None,
                "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ]

