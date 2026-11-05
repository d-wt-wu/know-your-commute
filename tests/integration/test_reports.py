from datetime import date

import pytest
from sqlalchemy import event

from commute.db.reports import route_report
from commute.ingest.pipeline import import_resource
from commute.ingest.registry import DELAYS
from tests.helpers import source_file, synthetic_csv

pytestmark = pytest.mark.integration


def test_sql_matches_hand_calculation_and_inclusive_bounds(seeded):
    # Route 102, Jan 1–2: 3 records; delays [10, missing, 0]; median 5, n=2.
    data = synthetic_csv([
        {}, {"Min Delay": "", "Code": "UNKNOWN"},
        {"Date": "2025-01-02T00:00:00", "Day": "Thursday", "Min Delay": "0"},
        {"Date": "2025-01-02T00:00:00", "Day": "Thursday", "Line": "103 TEST", "Min Delay": "999"},
        {"Date": "2025-01-03T00:00:00", "Day": "Friday", "Min Delay": "30"},
        {"Date": "2025-01-02T00:00:00", "Day": "Thursday", "Line": "102D MARKHAM ROAD", "Min Delay": "15"},
    ])
    import_resource(seeded, DELAYS, lambda: source_file(data))
    result = route_report(seeded, "102", date(2025, 1, 1), date(2025, 1, 2))
    summary = result["summary"]
    assert summary["reported_records"] == 3 and summary["valid_delay_samples"] == 2
    assert summary["median_recorded_delay_minutes"] == 5 and summary["mean_recorded_delay_minutes"] == 5
    assert summary["zero_delay_samples"] == 1
    assert [r["reported_records"] for r in result["daily_records"]] == [2, 1]
    assert [(r["incident_code"], r["reported_records"]) for r in result["causes"]] == [("EFB", 2), ("UNKNOWN", 1)]
    assert len(result["examples"]) == 3
    one_day = route_report(seeded, "102", date(2025, 1, 2), date(2025, 1, 2))
    assert one_day["summary"]["reported_records"] == 1
    assert route_report(seeded, "102D", date(2025, 1, 1), date(2025, 1, 2))["summary"]["reported_records"] == 1


def test_empty_results_are_nullable_and_filter_values_are_parameters(seeded):
    import_resource(seeded, DELAYS, lambda: source_file(synthetic_csv([{}])))
    for route in ["99999", "102' OR TRUE --"]:
        result = route_report(seeded, route, date(2025, 1, 1), date(2025, 1, 1))
        assert result["summary"]["reported_records"] == 0
        assert result["summary"]["median_recorded_delay_minutes"] is None
        assert result["summary"]["valid_delay_samples"] == 0
        assert result["daily_records"] == result["causes"] == result["examples"] == []
    with pytest.raises(ValueError, match="Start date"):
        route_report(seeded, "102", date(2025, 1, 2), date(2025, 1, 1))


def test_refresh_between_report_queries_cannot_mix_snapshots(seeded):
    first = import_resource(seeded, DELAYS, lambda: source_file(synthetic_csv([{}])))
    refreshed = False
    def refresh_during_report(connection, cursor, statement, parameters, context, executemany):
        nonlocal refreshed
        if not refreshed and statement.startswith("-- One row per ingested"):
            refreshed = True
            import_resource(seeded, DELAYS, lambda: source_file(synthetic_csv([{"Min Delay": "20"}, {"Min Delay": "30"}])))
    event.listen(seeded, "before_cursor_execute", refresh_during_report)
    try:
        report = route_report(seeded, "102", date(2025, 1, 1), date(2025, 1, 2))
    finally:
        event.remove(seeded, "before_cursor_execute", refresh_during_report)
    assert refreshed
    assert report["source"]["id"] == first.snapshot_id
    assert report["summary"]["reported_records"] == sum(r["reported_records"] for r in report["daily_records"]) == 1
    assert sum(r["reported_records"] for r in report["causes"]) == 1
    assert route_report(seeded, "102", date(2025, 1, 1), date(2025, 1, 2))["summary"]["reported_records"] == 2
