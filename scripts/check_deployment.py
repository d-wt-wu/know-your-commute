"""Verify a running built app, including packaged SQL and Home Screen assets."""
import argparse
import json
from urllib.error import HTTPError
from urllib.request import urlopen


def check(base: str, expected: int):
    for path in ("/", "/about", "/data-health"):
        with urlopen(base + path, timeout=90) as response:
            assert response.status == 200 and b"/manifest.webmanifest" in response.read()

    def read_api(path):
        with urlopen(base + path, timeout=30) as response:
            assert response.status == 200
            assert response.headers.get_content_type() == "application/json"
            assert response.headers["Cache-Control"] == "no-store"
            return json.load(response)

    assert read_api("/api/v1/health")["status"] == "ok"
    assert read_api("/api/v1/ready")["status"] == "ready"
    with urlopen(base + "/manifest.webmanifest", timeout=30) as response:
        assert response.headers.get_content_type() == "application/manifest+json"
        manifest = json.load(response)
    for icon in manifest["icons"] + [{"src": "/apple-touch-icon.png"}]:
        with urlopen(base + icon["src"], timeout=30) as response:
            assert response.headers.get_content_type() == "image/png"
            assert response.read(8) == b"\x89PNG\r\n\x1a\n"
    query = "route=102&start=2025-01-01&end=2025-01-31"
    summary = read_api("/api/v1/summary?" + query)
    assert summary["summary"]["reported_records"] == expected
    snapshot = summary["context"]["snapshot"]["id"]
    query += "&snapshot_id=" + snapshot
    patterns = read_api("/api/v1/patterns?" + query)
    assert patterns["context"]["snapshot"]["id"] == snapshot
    for grouping in ("daily_records", "causes", "calendar_weekdays"):
        assert sum(row["reported_records"] for row in patterns[grouping]) == expected
    records = read_api("/api/v1/records?" + query)
    assert records["total_records"] == expected
    assert records["context"]["snapshot"]["id"] == snapshot
    if records["total_pages"] > 1:
        second_page = read_api("/api/v1/records?" + query + "&page=2")
        assert second_page["page"] == 2
        assert second_page["context"]["snapshot"]["id"] == snapshot
        assert {row["row_number"] for row in records["records"]}.isdisjoint(
            row["row_number"] for row in second_page["records"]
        )
    health = read_api("/api/v1/data-health")
    delay_health = next(row for row in health["resources"] if row["kind"] == "delays")
    assert delay_health["active_snapshot"]["id"] == snapshot
    assert delay_health["quality"]["accepted_count"] == summary["quality"]["accepted_count"]
    for path in ["/api/v1/missing", "/missing.png"]:
        try:
            urlopen(base + path, timeout=30)
        except HTTPError as error:
            assert error.code == 404
            assert error.headers.get_content_type() == "application/json"
        else:
            raise AssertionError("A missing API/asset path returned success.")
    return {
        "status": "verified", "base_url": base,
        "route_102_january_records": expected,
        "median_recorded_delay_minutes": summary["summary"]["median_recorded_delay_minutes"],
        "active_snapshot": snapshot,
        "accepted_source_records": delay_health["quality"]["accepted_count"],
        "rejected_source_records": delay_health["quality"]["rejected_count"],
        "readiness": "ready", "pattern_totals": "reconciled",
        "pagination": "snapshot pinned; nonoverlapping pages",
        "direct_page_links": "served", "home_screen_assets": "served",
        "missing_api_and_assets": "JSON 404",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-records", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.base_url.rstrip("/"), args.expected_records)))
