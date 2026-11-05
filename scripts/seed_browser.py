#!/usr/bin/env python3
"""Labelled synthetic browser data, restricted to commute_browser_test only."""

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from alembic import command
from alembic.config import Config
import sqlalchemy as sa
from sqlalchemy.engine import make_url

from commute.db.connection import database_engine
from commute.ingest.pipeline import import_resource
from commute.ingest.registry import CODES, DELAYS
from tests.helpers import FIXTURES, source_file, synthetic_csv


def main():
    raw_url = os.environ.get("BROWSER_TEST_DATABASE_URL")
    if not raw_url or make_url(raw_url).database != "commute_browser_test":
        raise SystemExit("Set BROWSER_TEST_DATABASE_URL to a dedicated database named commute_browser_test. No other database can be reset.")
    admin = database_engine(make_url(raw_url).set(database="postgres"))
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        exists = connection.scalar(sa.text("SELECT 1 FROM pg_database WHERE datname = 'commute_browser_test'"))
        if not exists:
            connection.execute(sa.text('CREATE DATABASE commute_browser_test'))
    admin.dispose()
    engine = database_engine(raw_url)
    try:
        config = Config(str(ROOT / "alembic.ini"))
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with engine.begin() as connection:
            connection.execute(sa.text("TRUNCATE rejected_records, incident_codes, delay_records, raw_records, import_runs, source_snapshots, source_resources"))
        rows = [{"Date": f"2025-01-0{1 if i < 20 else 2}T00:00:00", "Day": "Wednesday" if i < 20 else "Thursday",
                 "Time": f"08:{i:02}", "Min Delay": "" if i == 34 else str((i % 5) * 10),
                 "Code": "SYNTHETIC_UNKNOWN" if i == 1 else "EFB"} for i in range(35)]
        rows.extend({"Line": "116 MORNINGSIDE", "Date": "2025-01-03T00:00:00", "Day": "Friday", "Time": f"09:{i:02}"} for i in range(5))
        import_resource(engine, CODES, lambda: source_file((FIXTURES / "codes.csv").read_bytes()))
        import_resource(engine, DELAYS, lambda: source_file(synthetic_csv(rows)))
        print("Seeded commute_browser_test with 40 labelled synthetic browser records, separate from the real-source database.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
