import json

import pytest
import sqlalchemy as sa

from commute.db import backup
from commute.ingest.pipeline import import_resource
from commute.ingest.registry import DELAYS
from tests.helpers import source_file, synthetic_csv

pytestmark = pytest.mark.integration


def test_real_backup_and_restore_remain_consistent_during_refresh(seeded, tmp_path, monkeypatch):
    first = import_resource(seeded, DELAYS, lambda: source_file(synthetic_csv([{}])))
    original = backup._run
    changed = False

    def refresh_while_dumping(arguments, **kwargs):
        nonlocal changed
        if "--format=custom" in arguments:
            import_resource(seeded, DELAYS, lambda: source_file(synthetic_csv([{}, {"Min Delay": "30"}])))
            changed = True
        return original(arguments, **kwargs)

    monkeypatch.setattr(backup, "_run", refresh_while_dumping)
    manifest = backup.create_backup(seeded, tmp_path)
    value = json.loads(manifest.read_text())
    assert changed
    assert value["fingerprints"]["delay_records"]["rows"] == 1
    restored = backup.restore_check(seeded, manifest)
    assert restored["status"] == "verified" and restored["scratch_database_removed"]
    assert restored["fingerprints"] == value["fingerprints"]
    with seeded.connect() as connection:
        assert connection.scalar(sa.text("SELECT count(*) FROM delay_records")) == 3
        assert str(connection.scalar(sa.text("SELECT active_snapshot_id FROM source_resources WHERE kind='delays'"))) != str(first.snapshot_id)
        assert connection.scalar(sa.text("SELECT count(*) FROM pg_database WHERE datname LIKE 'commute_restore_%_test'")) == 0


def test_failed_restore_cleans_only_its_created_scratch_database(seeded, tmp_path, monkeypatch):
    import_resource(seeded, DELAYS, lambda: source_file(synthetic_csv([{}])))
    manifest = backup.create_backup(seeded, tmp_path)

    def fail(*args, **kwargs):
        raise backup.BackupError("Deliberate restore failure")

    monkeypatch.setattr(backup, "_run", fail)
    with pytest.raises(backup.BackupError, match="Deliberate"):
        backup.restore_check(seeded, manifest)
    with seeded.connect() as connection:
        assert connection.scalar(sa.text("SELECT count(*) FROM delay_records")) == 1
        assert connection.scalar(sa.text("SELECT count(*) FROM pg_database WHERE datname LIKE 'commute_restore_%_test'")) == 0
