from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from commute.api.app import create_app
from commute.ingest.pipeline import ImportFailed, import_resource
from commute.ingest.registry import DELAYS
from tests.helpers import source_file, synthetic_csv

pytestmark = pytest.mark.integration


@pytest.fixture
def api(seeded):
    data = synthetic_csv([
        {}, {"Min Delay": "", "Code": "NEW"},
        {"Date": "2025-01-02T00:00:00", "Day": "Thursday", "Min Delay": "0"},
        {"Date": "2025-01-02T00:00:00", "Day": "Thursday", "Line": "102D MARKHAM ROAD", "Min Delay": "15"},
        {"Date": "2025-01-03T00:00:00", "Day": "Friday", "Line": "", "Min Delay": "30", "Time": "bad"},
    ])
    import_resource(seeded, DELAYS, lambda: source_file(data))
    with TestClient(create_app(seeded)) as client:
        yield client


FILTER = {"route": "102", "start": "2025-01-01", "end": "2025-01-02"}


def test_shared_filters_match_known_sql_counts_and_numeric_types(api):
    response = api.get("/api/v1/summary", params=FILTER)
    assert response.status_code == 200
    result = response.json()
    assert result["summary"]["reported_records"] == 3
    assert result["summary"]["valid_delay_samples"] == 2
    assert result["summary"]["median_recorded_delay_minutes"] == 5.0
    assert isinstance(result["summary"]["mean_recorded_delay_minutes"], float)
    pinned = {**FILTER, "snapshot_id": result["context"]["snapshot"]["id"]}
    patterns = api.get("/api/v1/patterns", params=pinned).json()
    records = api.get("/api/v1/records", params=pinned).json()
    assert sum(r["reported_records"] for r in patterns["daily_records"]) == records["total_records"] == 3
    assert sum(r["reported_records"] for r in patterns["causes"]) == 3
    assert patterns["calendar_weekdays"] == [{"iso_weekday": 3, "reported_records": 2}, {"iso_weekday": 4, "reported_records": 1}]
    assert result["context"] == patterns["context"] == records["context"]


def test_route_catalog_preserves_branches_unknowns_and_literal_search(api):
    result = api.get("/api/v1/routes").json()
    assert [r["identifier"] for r in result["routes"]] == ["102", "102D"]
    assert result["unassigned_route_records"] == 1
    assert result["routes"][0]["reported_records"] == 3
    assert api.get("/api/v1/routes", params={"q": "markham"}).json()["routes"]
    assert api.get("/api/v1/routes", params={"q": "%"}).json()["routes"] == []
    assert api.get("/api/v1/routes", params={"start": "2025-01-02", "end": "2025-01-02"}).json()["routes"][0]["reported_records"] == 1


@pytest.mark.parametrize("params", [
    {"start": "2025-02-30"}, {"start": "1735689600"}, {"start": "2025-01-02", "end": "2025-01-01"},
    {"route": " "}, {"page": 0}, {"page_size": 101}, {"page_size": 0}, {"sort": "DROP TABLE delay_records"},
    {"unexpected": "value"}, {"snapshot_id": "bad"},
])
def test_invalid_filters_fail_clearly(api, params):
    response = api.get("/api/v1/records", params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_filters"


def test_duplicate_query_values_are_rejected(api):
    assert api.get("/api/v1/summary?route=102&route=102D").status_code == 422


def test_empty_results_missing_duration_and_unknown_category_are_honest(api):
    empty = api.get("/api/v1/summary", params={"route": "102' OR TRUE --"}).json()
    assert empty["summary"]["reported_records"] == 0 and empty["summary"]["valid_delay_samples"] == 0
    assert empty["summary"]["median_recorded_delay_minutes"] is None
    assert api.get("/api/v1/patterns", params={"route": "99999"}).json()["daily_records"] == []
    records = api.get("/api/v1/records", params=FILTER).json()["records"]
    unknown = next(r for r in records if r["incident_code"] == "NEW")
    assert unknown["delay_minutes"] is None and unknown["mapping_status"] == "unmapped"
    assert next(r for r in records if r["delay_minutes"] == 0)["report_date"] == "2025-01-02"


def test_pagination_is_stable_across_refresh_when_snapshot_is_pinned(api, seeded):
    page1 = api.get("/api/v1/records", params={"page_size": 2, "sort": "date_asc"}).json()
    snapshot = page1["context"]["snapshot"]["id"]
    import_resource(seeded, DELAYS, lambda: source_file(synthetic_csv([{"Min Delay": "99"}])))
    page2 = api.get("/api/v1/records", params={"snapshot_id": snapshot, "page_size": 2, "page": 2, "sort": "date_asc"}).json()
    assert page1["total_records"] == page2["total_records"] == 5
    assert {r["row_number"] for r in page1["records"]}.isdisjoint({r["row_number"] for r in page2["records"]})
    assert api.get("/api/v1/summary").json()["summary"]["reported_records"] == 1
    assert api.get("/api/v1/summary", params={"snapshot_id": snapshot}).json()["summary"]["reported_records"] == 5
    assert api.get("/api/v1/summary", params={"snapshot_id": str(uuid4())}).status_code == 404


def test_partial_coverage_is_exposed_and_dates_are_not_silently_clamped(api):
    result = api.get("/api/v1/summary", params={"start": "2024-01-01", "end": "2026-01-01"}).json()
    assert result["context"]["extends_beyond_loaded_dates"] is True
    assert result["context"]["filters"]["start"] == "2024-01-01"
    assert result["context"]["coverage"]["start"] == "2025-01-01"


def test_latest_failure_and_last_success_are_separate_without_private_diagnostics(api, seeded):
    def broken():
        raise RuntimeError("secret-password private/path database-driver-trace")
    with pytest.raises(ImportFailed):
        import_resource(seeded, DELAYS, broken)
    response = api.get("/api/v1/data-health")
    resource = next(r for r in response.json()["resources"] if r["kind"] == "delays")
    assert resource["latest_attempt"]["status"] == "failed"
    assert resource["last_successful_attempt"]["status"] == "succeeded"
    assert resource["active_snapshot"] is not None
    for private in ["secret-password", "private/path", "error_summary", "source_provenance", "fixture://", "http_headers"]:
        assert private not in response.text


def test_process_health_survives_database_failure_and_errors_are_safe(api, seeded):
    def unavailable(connection, cursor, statement, parameters, context, executemany):
        raise OperationalError("secret SQL and host", {}, RuntimeError("secret DSN"))
    event.listen(seeded, "before_cursor_execute", unavailable)
    try:
        assert api.get("/api/v1/health").status_code == 200
        response = api.get("/api/v1/summary")
        assert response.status_code == 503 and "secret" not in response.text
        assert api.get("/api/v1/ready").status_code == 503
    finally:
        event.remove(seeded, "before_cursor_execute", unavailable)


def test_no_dataset_is_a_clear_unavailable_state(engine):
    with TestClient(create_app(engine)) as client:
        assert client.get("/api/v1/ready").status_code == 200
        response = client.get("/api/v1/summary")
        assert response.status_code == 503 and response.json()["error"]["code"] == "data_not_loaded"


def test_spa_paths_never_swallow_api_or_asset_errors(api, tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>local app shell</html>")
    with TestClient(create_app(api.app.state.engine, web_dir=tmp_path)) as client:
        assert "local app shell" in client.get("/about").text
        for path in ["/api/v1/missing", "/assets/missing.js", "/random"]:
            response = client.get(path)
            assert response.status_code == 404 and "local app shell" not in response.text
