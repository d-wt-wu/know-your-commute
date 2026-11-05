from concurrent.futures import ThreadPoolExecutor
from datetime import date
import os
from pathlib import Path
import subprocess
import sys
from threading import Event

import httpx
import pytest
import sqlalchemy as sa

from commute.db.reports import data_health, route_report
from commute.db.schema import delay_records, import_runs, raw_records, rejected_records, source_resources, source_snapshots
from commute.ingest.pipeline import ImportFailed, import_resource
from commute.ingest.registry import CODES, DELAYS
from commute.ingest.adapter import DELAY_HEADERS
from tests.helpers import FIXTURES, source_file, synthetic_csv

pytestmark = pytest.mark.integration


def import_delays(engine, data, **kwargs):
    return import_resource(engine, DELAYS, lambda: source_file(data), **kwargs)


def scalar(engine, statement):
    with engine.connect() as connection:
        return connection.scalar(statement)


def count(engine, table):
    return scalar(engine, sa.select(sa.func.count()).select_from(table))


def report(engine, route="102", start=date(2025, 1, 1), end=date(2025, 1, 2)):
    return route_report(engine, route, start, end)


def test_identical_rerun_keeps_counts_and_audits_attempt(seeded):
    data = synthetic_csv([{}, {}])
    first = import_delays(seeded, data)
    second = import_delays(seeded, data)
    assert first.status == "succeeded" and second.status == "no_change"
    assert first.snapshot_id == second.snapshot_id
    assert count(seeded, delay_records) == 2 and count(seeded, raw_records) == 48
    assert report(seeded)["summary"]["reported_records"] == 2
    assert count(seeded, import_runs) == 3


def test_corrected_cumulative_file_replaces_and_retains_old_provenance(seeded):
    first = import_delays(seeded, synthetic_csv([{}, {"Min Delay": "20"}]))
    second = import_delays(seeded, synthetic_csv([{"Min Delay": "30"}]))
    assert first.snapshot_id != second.snapshot_id
    result = report(seeded)
    assert result["summary"]["reported_records"] == 1
    assert result["summary"]["median_recorded_delay_minutes"] == 30
    assert count(seeded, delay_records) == 3
    with seeded.connect() as connection:
        original = connection.scalar(sa.select(raw_records.c.payload).where(raw_records.c.snapshot_id == first.snapshot_id, raw_records.c.row_number == 2))
    assert original["Min Delay"] == "10"


def test_source_reversion_reactivates_existing_snapshot_without_inserting(seeded):
    original = synthetic_csv([{}])
    first = import_delays(seeded, original)
    import_delays(seeded, synthetic_csv([{"Min Delay": "30"}]))
    reverted = import_delays(seeded, original)
    assert reverted.status == "reactivated" and reverted.snapshot_id == first.snapshot_id
    assert count(seeded, delay_records) == 2
    assert report(seeded)["summary"]["median_recorded_delay_minutes"] == 10


@pytest.mark.parametrize("bad", [b"<html>bad download</html>", b"Date,Line\n2025-01-01,102\n", synthetic_csv([{"Date": "bad"}])])
def test_failed_refresh_preserves_good_data_and_separates_last_success(seeded, bad):
    good = import_delays(seeded, synthetic_csv([{}]))
    with pytest.raises(ImportFailed):
        import_delays(seeded, bad)
    assert report(seeded)["source"]["id"] == good.snapshot_id
    health = next(h for h in data_health(seeded) if h["resource"]["id"] == DELAYS.key)
    assert health["latest_attempt"]["status"] == "failed"
    assert health["last_successful_attempt"]["id"] == good.run_id
    assert count(seeded, delay_records) == 1


def test_rejection_reconciliation_and_nullable_fields_survive_database(seeded):
    result = import_delays(seeded, synthetic_csv([{"Min Delay": ""}, {"Min Delay": "0", "Code": "NEW", "Line": ""}, {"Date": "invalid"}]))
    assert (result.raw_count, result.accepted_count, result.rejected_count) == (3, 2, 1)
    assert count(seeded, rejected_records) == 1
    result = report(seeded, route=None)
    assert result["summary"]["reported_records"] == 2
    assert result["summary"]["valid_delay_samples"] == 1
    assert result["summary"]["median_recorded_delay_minutes"] == 0
    assert next(row for row in result["causes"] if row["incident_code"] == "NEW")["mapping_status"] == "unmapped"


def test_failure_after_staging_rolls_back_every_new_row(seeded):
    first = import_delays(seeded, synthetic_csv([{}]))
    def fail():
        raise RuntimeError("Deliberate recovery drill")
    with pytest.raises(ImportFailed):
        import_delays(seeded, synthetic_csv([{"Min Delay": "30"}, {}]), before_promote=fail)
    assert count(seeded, delay_records) == 1
    assert report(seeded)["source"]["id"] == first.snapshot_id
    assert count(seeded, source_snapshots) == 2  # one lookup, one good delay snapshot
    retried = import_delays(seeded, synthetic_csv([{"Min Delay": "30"}, {}]))
    assert retried.status == "succeeded" and report(seeded)["summary"]["reported_records"] == 2


def test_process_death_before_promotion_is_recoverable(seeded, tmp_path):
    good = import_delays(seeded, synthetic_csv([{}]))
    path = tmp_path / "corrected.csv"
    path.write_bytes(synthetic_csv([{"Min Delay": "30"}, {}]))
    script = """
import os,sys
from pathlib import Path
from commute.db.connection import database_engine
from commute.ingest.fetch import SourceFile,now
from commute.ingest.pipeline import import_resource
from commute.ingest.registry import DELAYS
engine=database_engine(os.environ['TEST_DATABASE_URL'])
source=SourceFile(Path(sys.argv[1]).read_bytes(),'fixture://process-death',now())
import_resource(engine,DELAYS,lambda:source,before_promote=lambda:os._exit(91))
"""
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src")}
    child = subprocess.run([sys.executable, "-c", script, str(path)], env=environment, capture_output=True, timeout=30)
    assert child.returncode == 91, child.stderr.decode()
    assert report(seeded)["source"]["id"] == good.snapshot_id and count(seeded, delay_records) == 1
    assert scalar(seeded, sa.select(sa.func.count()).select_from(import_runs).where(import_runs.c.status == "running")) == 1
    import_delays(seeded, path.read_bytes())
    assert scalar(seeded, sa.select(sa.func.count()).select_from(import_runs).where(import_runs.c.status == "interrupted")) == 1
    assert report(seeded)["summary"]["reported_records"] == 2


def test_competing_import_is_refused_before_loading_and_can_retry(seeded):
    entered, release = Event(), Event()
    data = synthetic_csv([{}])
    def slow_load():
        entered.set()
        assert release.wait(10)
        return source_file(data)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(import_resource, seeded, DELAYS, slow_load)
        assert entered.wait(10)
        try:
            with pytest.raises(ImportFailed) as failure:
                import_resource(seeded, DELAYS, lambda: pytest.fail("competing attempt must not load"))
            assert failure.value.code == "resource_busy"
        finally:
            release.set()
        assert first.result(timeout=10).status == "succeeded"
    assert import_delays(seeded, data).status == "no_change"


def test_lookup_revision_pins_old_meaning_then_reprocesses_identical_delay_bytes(seeded, official_lookup):
    data = synthetic_csv([{}])
    first = import_delays(seeded, data)
    import_resource(seeded, CODES, lambda: source_file(official_lookup.replace(b",BODY", b",REVISED BODY")))
    assert report(seeded)["causes"][0]["description"] == "BODY"
    second = import_delays(seeded, data)
    assert second.snapshot_id != first.snapshot_id and second.status == "succeeded"
    assert report(seeded)["causes"][0]["description"] == "REVISED BODY"


def test_parser_version_can_deliberately_reprocess_same_bytes(seeded):
    data = synthetic_csv([{}])
    first = import_delays(seeded, data)
    second = import_delays(seeded, data, parser_version="test-v2")
    assert first.snapshot_id != second.snapshot_id
    assert report(seeded)["summary"]["reported_records"] == 1


def test_download_failure_is_audited_without_losing_active_data(seeded):
    good = import_delays(seeded, synthetic_csv([{}]))
    def timeout():
        raise httpx.ReadTimeout("Synthetic upstream timeout")
    with pytest.raises(ImportFailed):
        import_resource(seeded, DELAYS, timeout)
    assert report(seeded)["source"]["id"] == good.snapshot_id
    health = next(h for h in data_health(seeded) if h["resource"]["id"] == DELAYS.key)
    assert health["latest_attempt"]["error_code"] == "ReadTimeout"


def test_real_fixture_import_preserves_source_rows(seeded):
    result = import_delays(seeded, (FIXTURES / "ttc-bus-sample.csv").read_bytes())
    assert result.accepted_count == 20 and result.rejected_count == 0
    assert count(seeded, delay_records) == 20
    assert scalar(seeded, sa.select(sa.func.count()).select_from(delay_records).where(delay_records.c.route_identifier.is_(None))) >= 1


def test_new_named_column_is_preserved_and_reported(seeded):
    result = import_delays(seeded, synthetic_csv([{"Publisher Extra": "preserve me"}], (*DELAY_HEADERS, "Publisher Extra")))
    assert report(seeded)["quality"]["extra_columns"] == ["Publisher Extra"]
    payload = scalar(seeded, sa.select(raw_records.c.payload).where(raw_records.c.snapshot_id == result.snapshot_id))
    assert payload["Publisher Extra"] == "preserve me"


def test_active_pointer_cannot_select_another_resource_snapshot(seeded):
    good = import_delays(seeded, synthetic_csv([{}]))
    lookup_id = scalar(seeded, sa.select(source_resources.c.active_snapshot_id).where(source_resources.c.id == CODES.key))
    with pytest.raises(sa.exc.IntegrityError):
        with seeded.begin() as connection:
            connection.execute(source_resources.update().where(source_resources.c.id == DELAYS.key).values(active_snapshot_id=lookup_id))
    assert report(seeded)["source"]["id"] == good.snapshot_id
