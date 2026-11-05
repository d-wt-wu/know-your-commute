from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect

pytestmark = pytest.mark.integration


def test_migration_round_trip_and_metadata_agreement(engine):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert "source_snapshots" not in inspect(connection).get_table_names()
        connection.commit()
        command.upgrade(config, "head")
        command.check(config)
        assert "source_snapshots" in inspect(connection).get_table_names()
