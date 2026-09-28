"""SQLite engine/session setup and create_all bootstrap for Week 1."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .base import Base
from . import models  # noqa: F401 - registers model metadata


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'data' / 'mira_week1.db'}"


def database_url_from_environment() -> str:
    return os.getenv("MIRA_DATABASE_URL", DEFAULT_DATABASE_URL)


def debug_runs_from_environment() -> bool:
    return os.getenv("MIRA_DEBUG_RUNS", "0").lower() in {"1", "true", "yes"}


def create_week1_engine(database_url: str | None = None) -> Engine:
    url = database_url or database_url_from_environment()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def bootstrap_database(engine: Engine) -> None:
    """Create local Week 1 tables; migrations are intentionally out of scope."""
    Base.metadata.create_all(engine)
