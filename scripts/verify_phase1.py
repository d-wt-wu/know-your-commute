#!/usr/bin/env python3
"""Run the real Phase 1 gate and save evidence only after every check succeeds."""

import argparse
import csv
from dataclasses import asdict
from datetime import date, datetime, timezone
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import sqlalchemy as sa

from commute.db.connection import database_engine
from commute.db.reports import data_health, route_report
from commute.ingest.fetch import DownloadSession, load_manifest_file
from commute.ingest.pipeline import import_resource
from commute.ingest.registry import CODES, DELAYS


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, default=str, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-postgres", action="store_true", help="Start the optional project-local PostgreSQL build first")
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/raw/download-manifest.json")
    args = parser.parse_args()
    environment = {
        **os.environ,
        "DATABASE_URL": os.environ.get("DATABASE_URL", "postgresql+psycopg://commute:commute_local@127.0.0.1:54329/commute"),
        "TEST_DATABASE_URL": os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://commute:commute_local@127.0.0.1:54329/commute_test"),
        "REQUIRE_INTEGRATION_TESTS": "1",
        "PYTHONPATH": str(ROOT / "src"),
    }
    environment.pop("PYTEST_ADDOPTS", None)
    (ROOT / "work").mkdir(exist_ok=True)
    commands = []
    for command in (
        ([[sys.executable, "scripts/local_postgres.py", "setup"]] if args.local_postgres else [])
        + [[sys.executable, "-m", "alembic", "upgrade", "head"],
           [sys.executable, "-m", "pytest", "-q", "--tb=short", "--junitxml=work/phase1-tests.xml"]]
    ):
        result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
        print(result.stdout, end="", flush=True)
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        commands.append({"command": command[1:], "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        if result.returncode:
            (ROOT / "work").mkdir(exist_ok=True)
            write_json(ROOT / "work/phase1-failed-check.json", commands)
            raise SystemExit(result.returncode)
    cases = ET.parse(ROOT / "work/phase1-tests.xml").findall(".//testcase")
    integration_cases = [case for case in cases if ".integration." in case.attrib.get("classname", "")]
    assert integration_cases, "No PostgreSQL integration cases ran"
    assert not any(case.find("skipped") is not None for case in cases), "Skipped checks cannot pass the Phase 1 gate"
    manifest = args.manifest.resolve()
    if not manifest.exists():
        session = DownloadSession(ROOT / "data/raw")
        try:
            session.resource(CODES)
            session.resource(DELAYS)
            manifest = session.write_manifest()
        finally:
            session.close()
    engine = database_engine(environment["DATABASE_URL"])
    try:
        started = perf_counter()
        first = [import_resource(engine, resource, lambda r=resource: load_manifest_file(manifest, r)) for resource in (CODES, DELAYS)]
        import_seconds = perf_counter() - started
        started = perf_counter()
        second = [import_resource(engine, resource, lambda r=resource: load_manifest_file(manifest, r)) for resource in (CODES, DELAYS)]
        rerun_seconds = perf_counter() - started
        assert all(r.status == "no_change" for r in second), "Identical real source did not take the no-change path"
        assert [r.snapshot_id for r in first] == [r.snapshot_id for r in second]
        started = perf_counter()
        report = route_report(engine, "102", date(2025, 1, 1), date(2025, 1, 31))
        report_seconds = perf_counter() - started
        raw = load_manifest_file(manifest, DELAYS)
        # Independent calculation uses original string cells, not the adapter or report SQL.
        records = list(csv.DictReader(io.StringIO(raw.data.decode("utf-8-sig"))))
        expected = [row for row in records if row["Line"].split()[:1] == ["102"] and "2025-01-01" <= row["Date"][:10] <= "2025-01-31"]
        durations = [int(row["Min Delay"]) for row in expected if row["Min Delay"].isdigit()]
        assert report["summary"]["reported_records"] == len(expected)
        assert report["summary"]["valid_delay_samples"] == len(durations)
        assert report["summary"]["median_recorded_delay_minutes"] == statistics.median(durations)
        assert report["summary"]["reported_records"] == sum(row["reported_records"] for row in report["causes"])
        assert report["summary"]["reported_records"] == sum(row["reported_records"] for row in report["daily_records"])
        with engine.connect() as connection:
            database_version = connection.scalar(sa.text("SELECT version()"))
            database_bytes = connection.scalar(sa.text("SELECT pg_database_size(current_database())"))
        evidence = ROOT / "docs/evidence"
        evidence.mkdir(exist_ok=True)
        completed_at = datetime.now(timezone.utc).isoformat()
        write_json(evidence / "phase1-checks.json", {
            "verified_at": completed_at, "commands": commands,
            "tests": {"passed": len(cases), "integration_passed": len(integration_cases), "skipped": 0},
            "python": platform.python_version(), "platform": platform.system(), "machine": platform.machine(),
            "database_version": database_version, "manifest": str(manifest.relative_to(ROOT)),
            "first_attempts_this_gate": [asdict(r) for r in first], "rerun_attempts": [asdict(r) for r in second],
            "measurements": {"first_attempts_seconds": import_seconds, "same_bytes_rerun_seconds": rerun_seconds,
                             "route_report_seconds": report_seconds, "database_bytes_after_gate": database_bytes,
                             "conditions": "One local run with an existing server; no controlled cold-cache benchmark. First attempt may reuse preexisting snapshots; see statuses."},
            "independent_route_102_january_check": {"records": len(expected), "duration_samples": len(durations), "median_recorded_minutes": statistics.median(durations)},
        })
        write_json(evidence / "route-102-2025-01.json", report)
        write_json(evidence / "data-health.json", data_health(engine))
        with (ROOT / "docs/progress.md").open("a") as file:
            file.write(f"\n## Phase 1 gate verified — {completed_at}\n\n")
            file.write("All required PostgreSQL cases passed. The real official bundle imported, an identical rerun reused the active snapshots, and route 102 for January 2025 matched an independent calculation from the raw CSV. ")
            file.write("See `docs/evidence/phase1-checks.json`, the SQL report and data-health output. Phase 1 is complete; proceed to the tested reporting API in Phase 2.\n")
        print("Phase 1 gate passed. Evidence saved in docs/evidence/.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
