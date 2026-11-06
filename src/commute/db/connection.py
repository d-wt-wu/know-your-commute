import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL, make_url


def database_url(url: str | URL | None = None, *, purpose: str = "api") -> URL:
    if purpose not in {"api", "writer"}:
        raise ValueError("Database purpose must be api or writer.")
    keys = (("IMPORT_DATABASE_URL", "DATABASE_URL_UNPOOLED", "DATABASE_URL") if purpose == "writer"
            else ("COMMUTE_API_DATABASE_URL", "DATABASE_URL"))
    url = url or next((os.environ[key] for key in keys if os.environ.get(key)), None)
    if not url:
        raise ValueError("Set DATABASE_URL first; see .env.example and docs/runbook.md.")
    parsed = make_url(url)
    if parsed.drivername in {"postgres", "postgresql"}:
        parsed = parsed.set(drivername="postgresql+psycopg")
    if parsed.drivername != "postgresql+psycopg":
        raise ValueError("This project requires PostgreSQL with the psycopg driver.")
    if purpose == "writer" and "-pooler." in (parsed.host or ""):
        raise ValueError("Imports, migrations and backups require a direct connection. Set DATABASE_URL_UNPOOLED or IMPORT_DATABASE_URL.")
    return parsed


def database_engine(url: str | URL | None = None, *, purpose: str = "api") -> Engine:
    parsed = database_url(url, purpose=purpose)
    engine = create_engine(parsed, pool_pre_ping=True, pool_size=3, max_overflow=2,
                           connect_args={"connect_timeout": 10})
    if engine.dialect.name != "postgresql":
        engine.dispose()
        raise ValueError("This project requires PostgreSQL, including integration tests.")
    return engine
