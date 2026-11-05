import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url

from commute.db.connection import database_engine
from commute.ingest.pipeline import import_resource
from commute.ingest.registry import CODES
from tests.helpers import source_file

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def postgres_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        if os.environ.get("REQUIRE_INTEGRATION_TESTS") == "1":
            pytest.fail("CI requires TEST_DATABASE_URL and a running PostgreSQL service.")
        pytest.skip("Set TEST_DATABASE_URL to a dedicated PostgreSQL database ending in _test.")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("Refusing destructive integration cleanup: database name must end in _test.")
    engine = database_engine(url)
    config = Config(str(ROOT / "alembic.ini"))
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.check(config)
    yield engine
    engine.dispose()


@pytest.fixture
def engine(postgres_engine):
    with postgres_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE rejected_records, incident_codes, delay_records, raw_records, import_runs, source_snapshots, source_resources"))
    return postgres_engine


@pytest.fixture
def seeded(engine, official_lookup):
    import_resource(engine, CODES, lambda: source_file(official_lookup))
    return engine
