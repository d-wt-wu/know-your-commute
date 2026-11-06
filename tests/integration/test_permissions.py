from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from commute.api.app import create_app
from commute.db.permissions import create_api_login, grant_api_reads, verify_api_role
from commute.ingest.pipeline import import_resource
from commute.ingest.registry import DELAYS
from tests.helpers import source_file, synthetic_csv

pytestmark = pytest.mark.integration


def test_api_works_with_select_only_role_and_cannot_write_or_read_raw(seeded):
    import_resource(seeded, DELAYS, lambda: source_file(synthetic_csv([{}])))
    role = "commute_api_" + uuid4().hex
    limited = None
    created = False
    try:
        with seeded.begin() as connection:
            connection.execute(sa.text(f'CREATE ROLE "{role}" NOLOGIN'))
            grant_api_reads(connection, role)
        created = True
        # SET ROLE simulates the separately authenticated API login in this test.
        limited = sa.create_engine(seeded.url, connect_args={"options": f"-c role={role}"}, poolclass=sa.pool.NullPool)
        with limited.connect() as connection:
            verify_api_role(connection)
        with TestClient(create_app(limited)) as client:
            for path in ["routes", "summary?route=102", "patterns?route=102", "records?route=102", "data-health", "ready"]:
                response = client.get("/api/v1/" + path)
                assert response.status_code == 200, response.text
        for statement in ["DELETE FROM delay_records", "SELECT * FROM raw_records", "SELECT * FROM rejected_records",
                          "CREATE TABLE public.should_never_exist (id integer)"]:
            with limited.connect() as connection:
                with pytest.raises(DBAPIError) as error:
                    connection.execute(sa.text(statement))
                assert error.value.orig.sqlstate == "42501"  # insufficient_privilege
        with seeded.connect() as connection:
            with pytest.raises(ValueError, match="write or administrative"):
                verify_api_role(connection)
    finally:
        if limited is not None:
            limited.dispose()
        if created:
            with seeded.begin() as connection:
                connection.execute(sa.text(f'DROP OWNED BY "{role}"'))
                connection.execute(sa.text(f'DROP ROLE "{role}"'))


def test_api_login_rerun_preserves_existing_password(seeded):
    role = "commute_api_" + uuid4().hex
    try:
        with seeded.begin() as connection:
            assert create_api_login(connection, role, "synthetic-test-password")
            original = connection.scalar(sa.text("SELECT rolpassword FROM pg_authid WHERE rolname=:role"), {"role": role})
            assert original
            assert create_api_login(connection, role, "replacement-must-never-be-used") is False
            after = connection.scalar(sa.text("SELECT rolpassword FROM pg_authid WHERE rolname=:role"), {"role": role})
            assert original == after
    finally:
        with seeded.begin() as connection:
            connection.execute(sa.text(f'DROP ROLE IF EXISTS "{role}"'))
