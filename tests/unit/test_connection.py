import pytest

from commute.db.connection import database_url
from commute.environment import load_environment


@pytest.fixture(autouse=True)
def clean_urls(monkeypatch):
    for name in ["DATABASE_URL", "DATABASE_URL_UNPOOLED", "IMPORT_DATABASE_URL", "COMMUTE_API_DATABASE_URL"]:
        monkeypatch.delenv(name, raising=False)


def test_neon_api_and_writer_use_distinct_connections(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://owner:fake@ep-test-pooler.example/db?sslmode=require")
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", "postgresql://owner:fake@ep-test.example/db?sslmode=require")
    monkeypatch.setenv("COMMUTE_API_DATABASE_URL", "postgresql://reader:fake@ep-test-pooler.example/db?sslmode=require")
    assert database_url().username == "reader"
    assert database_url().drivername == "postgresql+psycopg"
    writer = database_url(purpose="writer")
    assert writer.username == "owner" and writer.host == "ep-test.example"
    assert writer.query["sslmode"] == "require"


def test_importer_refuses_pooler_instead_of_losing_session_lock(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://owner:fake@ep-test-pooler.example/db")
    with pytest.raises(ValueError, match="direct connection"):
        database_url(purpose="writer")


def test_explicit_test_url_wins_and_local_workflow_still_works(monkeypatch):
    local = "postgresql+psycopg://test:fake@127.0.0.1/commute_test"
    monkeypatch.setenv("COMMUTE_API_DATABASE_URL", "postgresql://reader:fake@remote/db")
    assert database_url(local).database == "commute_test"
    monkeypatch.setenv("DATABASE_URL", local)
    assert database_url(purpose="writer").host == "127.0.0.1"


def test_env_loader_preserves_injected_settings_and_literal_passwords(tmp_path, monkeypatch):
    path = tmp_path / ".env.local"
    path.write_text("DATABASE_URL='postgresql://file:fake@host/db'\nLITERAL_TEST='${KEEP_LITERAL}'\n")
    monkeypatch.setenv("DATABASE_URL", "injected")
    monkeypatch.delenv("LITERAL_TEST", raising=False)
    load_environment(path)
    assert database_url("postgresql://explicit:fake@host/db").username == "explicit"
    import os
    assert os.environ["DATABASE_URL"] == "injected"
    assert os.environ["LITERAL_TEST"] == "${KEEP_LITERAL}"
    monkeypatch.delenv("LITERAL_TEST", raising=False)
