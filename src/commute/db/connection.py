import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def database_engine(url: str | None = None) -> Engine:
    url = url or os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError("Set DATABASE_URL first; see .env.example and docs/runbook.md.")
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name != "postgresql":
        engine.dispose()
        raise ValueError("This project requires PostgreSQL, including integration tests.")
    return engine
