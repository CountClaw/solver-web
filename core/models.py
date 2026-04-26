from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.utcnow()


class Base(DeclarativeBase):
    pass


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_value: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rate_per_second: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    rate_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class TaskRecord(Base):
    __tablename__ = "task_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    key_id: Mapped[int] = mapped_column(Integer, ForeignKey("api_keys.id"), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, default="TurnstileTaskProxyless")
    website_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    website_key: Mapped[str] = mapped_column(String(512), nullable=False)
    action: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cdata: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    result_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    solver_node: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, index=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class NetworkSetting(Base):
    __tablename__ = "network_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    proxy_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    no_proxy: Mapped[str] = mapped_column(String(512), nullable=False, default="localhost,127.0.0.1,::1")
    connect_timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=3000)
    read_timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=7000)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class SolverNodeStatus(Base):
    __tablename__ = "solver_node_status"

    node_url: Mapped[str] = mapped_column(String(1024), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    pending_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

