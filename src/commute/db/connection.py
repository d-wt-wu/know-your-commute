import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine import make_url


def database_engine(url: str | None = None) -> Engine:
    url = url or os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError("Set DATABASE_URL first; see .env.example and docs/runbook.md.")
    parsed = make_url(url)
    if parsed.drivername in {"postgres", "postgresql"}:
        parsed = parsed.set(drivername="postgresql+psycopg")
    if parsed.drivername != "postgresql+psycopg":
        raise ValueError("This project requires PostgreSQL with the psycopg driver.")
    engine = create_engine(parsed, pool_pre_ping=True, pool_size=3, max_overflow=2,
                           connect_args={"connect_timeout": 10})
    if engine.dialect.name != "postgresql":
        engine.dispose()
        raise ValueError("This project requires PostgreSQL, including integration tests.")
    return engine
