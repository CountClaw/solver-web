from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import load_config
from .models import Base

_engine = None
_session_factory = None


def _ensure_sqlite_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    relative_path = database_url.replace("sqlite:///", "", 1)
    path = Path(relative_path)
    if path.parent and str(path.parent) not in {"", "."}:
        path.parent.mkdir(parents=True, exist_ok=True)


def get_engine():
    global _engine
    if _engine is not None:
        return _engine

    cfg = load_config()
    _ensure_sqlite_dir(cfg.database_url)
    _engine = create_engine(cfg.database_url, future=True, pool_pre_ping=True)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is not None:
        return _session_factory
    _session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
    return _session_factory


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session: Session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

