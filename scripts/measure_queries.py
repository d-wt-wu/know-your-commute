"""Read-only local measurements. A first connection is not a cold database cache."""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import sqlalchemy as sa

from commute.db.connection import database_engine
from commute.db.reports import sql


def measure(engine):
    output = {"measured_at": datetime.now(timezone.utc).isoformat(),
              "conditions": "Local existing PostgreSQL server; existing data/cache; first call and five repeated calls on one connection. No true cold-cache measurement.",
              "cases": {}}
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.execute(sa.text("SET TRANSACTION READ ONLY"))
            connection.execute(sa.text("SET LOCAL statement_timeout = '10s'"))
            output["server_version"] = connection.scalar(sa.text("SHOW server_version"))
            output["database_bytes"] = connection.scalar(sa.text("SELECT pg_database_size(current_database())"))
            snapshot = connection.execute(sa.text("""SELECT s.id, s.lookup_snapshot_id, s.accepted_count,
                s.coverage_start, s.coverage_end FROM source_snapshots s JOIN source_resources r
                ON r.active_snapshot_id=s.id WHERE r.kind='delays'""")).mappings().one()
            output["snapshot_id"] = str(snapshot["id"])
            output["accepted_records"] = snapshot["accepted_count"]
            for name, route, start, end in [
                ("route_102_january_2025", "102", date(2025, 1, 1), date(2025, 1, 31)),
                ("all_loaded_records", None, snapshot["coverage_start"], snapshot["coverage_end"]),
            ]:
                params = {"snapshot_id": snapshot["id"], "lookup_snapshot_id": snapshot["lookup_snapshot_id"],
                          "route": route, "start": start, "end": end}
                timings = []
                for _ in range(6):
                    before = time.perf_counter()
                    result = dict(connection.execute(sql("route_summary"), params).mappings().one())
                    timings.append(round((time.perf_counter() - before) * 1000, 3))
                plan = connection.execute(sa.text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql("route_summary").text), params).scalar_one()[0]
                output["cases"][name] = {"filters": {"route": route, "start": str(start), "end": str(end)},
                    "reported_records": result["reported_records"], "first_call_ms": timings[0],
                    "repeated_call_ms": timings[1:], "repeated_median_ms": statistics.median(timings[1:]),
                    "explain": plan}
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/evidence/query-measurements.json"))
    args = parser.parse_args()
    engine = database_engine()
    try:
        result = measure(engine)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")
        print(json.dumps({"evidence": str(args.output), "accepted_records": result["accepted_records"],
            "cases": {key: {k: v for k, v in value.items() if k != "explain"} for key, value in result["cases"].items()}}, indent=2))
    finally:
        engine.dispose()
