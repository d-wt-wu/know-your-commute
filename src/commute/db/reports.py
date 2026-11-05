from datetime import date
from importlib.resources import files

import sqlalchemy as sa

from commute.db.schema import source_resources, source_snapshots, import_runs
from commute.ingest.registry import DELAYS


def sql(name: str):
    return sa.text(files("commute.db").joinpath("sql", name + ".sql").read_text())


def route_report(engine, route: str | None, start: date, end: date) -> dict:
    if start > end:
        raise ValueError("Start date must be on or before end date.")
    if route is not None and (not route.strip() or len(route) > 100):
        raise ValueError("Route must be a nonempty identifier of at most 100 characters.")
    # Repeatable read pins the resource selection and every subsequent query.
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.execute(sa.text("SET TRANSACTION READ ONLY"))
            snapshot = connection.execute(
                sa.select(source_snapshots).join(source_resources,
                    source_resources.c.active_snapshot_id == source_snapshots.c.id)
                .where(source_resources.c.id == DELAYS.key)
            ).mappings().first()
            if snapshot is None:
                raise ValueError("No active delay data. Import a lookup and delay file first.")
            params = {"snapshot_id": snapshot["id"], "lookup_snapshot_id": snapshot["lookup_snapshot_id"],
                      "route": route, "start": start, "end": end}
            result = {
                "filters": {"route": route, "start": start, "end": end, "date_bounds": "inclusive"},
                "source": {key: snapshot[key] for key in ("id", "content_sha256", "source_url", "source_last_modified", "retrieved_at", "lookup_snapshot_id", "parser_version", "contract_version")},
                "loaded_coverage": {"start": snapshot["coverage_start"], "end": snapshot["coverage_end"],
                                    "meaning": "Observed record dates, not a guarantee of complete disruption reporting."},
                "quality": {"scope": "entire_active_delay_snapshot", **{key: snapshot[key] for key in ("raw_count", "accepted_count", "rejected_count", "warning_record_count", "warning_counts", "extra_columns")}},
                "summary": dict(connection.execute(sql("route_summary"), params).mappings().one()),
                "daily_records": [dict(row) for row in connection.execute(sql("daily_counts"), params).mappings()],
                "causes": [dict(row) for row in connection.execute(sql("cause_counts"), params).mappings()],
                "examples": [dict(row) for row in connection.execute(sql("matching_records"), params).mappings()],
                "definitions": {
                    "count": "Reported delay records; no trip-level exposure denominator is available.",
                    "delay": "Recorded minutes of delay to the following bus's schedule; valid nonnegative numeric values, including reported zeroes.",
                    "gap": "Separate publisher field; not added to delay or interpreted as passenger time.",
                    "time": "Source date and wall-clock time; timezone and overnight service rules remain unconfirmed.",
                    "missing_days": "Daily output includes observed matching dates only; absent dates are not asserted zero.",
                },
            }
            return result


def data_health(engine) -> list[dict]:
    """Internal CLI view. A later public API will choose its own safe response model."""
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.execute(sa.text("SET TRANSACTION READ ONLY"))
            output = []
            for resource in connection.execute(sa.select(source_resources).order_by(source_resources.c.id)).mappings():
                latest = connection.execute(sa.select(import_runs).where(import_runs.c.resource_id == resource["id"])
                                            .order_by(import_runs.c.started_at.desc(), import_runs.c.id.desc()).limit(1)).mappings().first()
                last_success = connection.execute(sa.select(import_runs).where(
                    import_runs.c.resource_id == resource["id"], import_runs.c.status.in_(["succeeded", "no_change", "reactivated"]))
                    .order_by(import_runs.c.finished_at.desc(), import_runs.c.id.desc()).limit(1)).mappings().first()
                snapshot = connection.execute(sa.select(source_snapshots).where(
                    source_snapshots.c.id == resource["active_snapshot_id"])).mappings().first()
                output.append({"resource": dict(resource), "latest_attempt": dict(latest) if latest else None,
                               "last_successful_attempt": dict(last_success) if last_success else None,
                               "active_snapshot": dict(snapshot) if snapshot else None})
            return output
