import json

import pytest
from sqlalchemy.engine import make_url

from commute.db.backup import BackupError, TABLE_KEYS, _environment, checked_archive


def test_backup_refuses_escaped_archive_and_changed_bytes(tmp_path):
    manifest = tmp_path / "backup.json"
    value = {"format_version": 1, "archive": "../outside.dump"}
    manifest.write_text(json.dumps(value))
    with pytest.raises(BackupError, match="filename"):
        checked_archive(manifest)
    (tmp_path / "test.dump").write_bytes(b"changed")
    value.update(archive="test.dump", archive_bytes=7, archive_sha256="0" * 64,
                 fingerprints={name: {} for name in TABLE_KEYS})
    manifest.write_text(json.dumps(value))
    with pytest.raises(BackupError, match="checksum"):
        checked_archive(manifest)


def test_backup_connection_preserves_tls_without_credentials_in_arguments(monkeypatch):
    monkeypatch.setenv("PGSERVICE", "unrelated-service")
    env = _environment(make_url("postgresql+psycopg://user:secret@host/db?sslmode=require&channel_binding=require&connect_timeout=12"))
    assert env["PGSSLMODE"] == env["PGCHANNELBINDING"] == "require"
    assert env["PGCONNECT_TIMEOUT"] == "12"
    assert env["PGPASSWORD"] == "secret"
    assert "PGSERVICE" not in env
