"""Public reporting selections: read-only transactions and explicit safe projections."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timezone
from urllib.parse import urlsplit

import sqlalchemy as sa

from commute.db.reports import data_health, sql
from commute.db.schema import source_resources as resources, source_snapshots as snapshots
from commute.db.schema import delay_records as delays, incident_codes as codes
from commute.ingest.registry import DATASET_URL, DELAYS
from commute.query import Filters, InvalidRange, MissingSnapshot, NoData

DEFINITIONS = {
    "count": "Reported delay records, not unique verified incidents or a probability of a delayed trip.",
    "delay": "Recorded delay to the following bus's schedule, in minutes. Valid numeric samples include reported zeroes.",
    "gap": "A separate schedule-related source field; never added to delay or interpreted as passenger time.",
    "missing": "Missing or invalid durations are excluded from numeric summaries; they are not zero.",
    "routes": "Identifiers are conservatively parsed from historical labels; branches remain separate.",
}


def utc(value):
    return value.astimezone(timezone.utc) if value is not None else None


def public_snapshot(row):
    url = urlsplit(row["source_url"])
    safe_url = row["source_url"] if url.scheme == "https" and url.hostname == "ckan0.cf.opendata.inter.prod-toronto.ca" and not url.username and not url.password else None
    return {
        "id": row["id"], "resource_id": row["resource_id"], "content_sha256": row["content_sha256"],
        "lookup_snapshot_id": row["lookup_snapshot_id"], "source_url": safe_url,
        "dataset_url": DATASET_URL, "source_last_modified": row["source_last_modified"],
        "source_metadata_modified": row["provenance"].get("metadata_modified"),
        "retrieved_at": utc(row["retrieved_at"]), "imported_at": utc(row["created_at"]),
        "parser_version": row["parser_version"], "contract_version": row["contract_version"],
    }


def coverage(row):
    return {"start": row["coverage_start"], "end": row["coverage_end"]} if row else {"start": None, "end": None}


def quality(row):
    return {"scope": "entire_selected_snapshot", **{key: row[key] for key in (
        "raw_count", "accepted_count", "rejected_count", "warning_record_count", "warning_counts", "extra_columns")}}


@dataclass
class Selection:
    connection: object
    snapshot: object
    filters: Filters

    @property
    def params(self):
        return {"snapshot_id": self.snapshot["id"], "lookup_snapshot_id": self.snapshot["lookup_snapshot_id"],
                "route": self.filters.route, "start": self.filters.start, "end": self.filters.end}

    @property
    def conditions(self):
        result = [delays.c.snapshot_id == self.snapshot["id"], delays.c.report_date >= self.filters.start,
                  delays.c.report_date <= self.filters.end]
        if self.filters.route is not None:
            result.append(delays.c.route_identifier == self.filters.route)
        return result

    @property
    def context(self):
        return {"snapshot": public_snapshot(self.snapshot),
                "filters": {"route": self.filters.route, "start": self.filters.start, "end": self.filters.end},
                "coverage": coverage(self.snapshot),
                "extends_beyond_loaded_dates": self.filters.start < self.snapshot["coverage_start"] or self.filters.end > self.snapshot["coverage_end"]}


@contextmanager
def selection(engine, filters: Filters):
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.execute(sa.text("SET TRANSACTION READ ONLY"))
            connection.execute(sa.text("SET LOCAL statement_timeout = '5s'"))
            if filters.snapshot_id is not None:
                statement = sa.select(snapshots).where(snapshots.c.resource_id == DELAYS.key, snapshots.c.id == filters.snapshot_id)
            else:
                statement = sa.select(snapshots).join(resources, resources.c.active_snapshot_id == snapshots.c.id).where(resources.c.id == DELAYS.key)
            snapshot = connection.execute(statement).mappings().first()
            if snapshot is None:
                if filters.snapshot_id is not None:
                    raise MissingSnapshot("That delay-data snapshot is not available.")
                raise NoData("Historical data has not been loaded yet.")
            start, end = filters.start or snapshot["coverage_start"], filters.end or snapshot["coverage_end"]
            if start > end:
                raise InvalidRange("Start date must be on or before end date, including defaults from loaded coverage.")
            yield Selection(connection, snapshot, Filters(filters.route, start, end, snapshot["id"]))


def summary(engine, filters):
    with selection(engine, filters) as read:
        return {"context": read.context,
                "summary": dict(read.connection.execute(sql("route_summary"), read.params).mappings().one()),
                "quality": quality(read.snapshot), "definitions": DEFINITIONS}


def patterns(engine, filters):
    with selection(engine, filters) as read:
        weekdays = sa.select(sa.extract("isodow", delays.c.report_date).cast(sa.Integer).label("iso_weekday"),
                             sa.func.count().label("reported_records")).where(*read.conditions).group_by("iso_weekday").order_by("iso_weekday")
        return {"context": read.context,
                "daily_records": [dict(r) for r in read.connection.execute(sql("daily_counts"), read.params).mappings()],
                "causes": [dict(r) for r in read.connection.execute(sql("cause_counts"), read.params).mappings()],
                "calendar_weekdays": [dict(r) for r in read.connection.execute(weekdays).mappings()],
                "missing_dates_meaning": "Only dates with matching records are returned; absent dates are not asserted zero.",
                "time_analysis_note": "Weekdays derive from recorded Date. Timezone and overnight service rules remain unconfirmed; no hour heatmap is supplied."}


def routes(engine, filters, search=None):
    with selection(engine, filters) as read:
        conditions = [*read.conditions, delays.c.route_identifier.is_not(None)]
        if search and search.strip():
            query = search.strip().lower()
            conditions.append(sa.or_(sa.func.strpos(sa.func.lower(delays.c.route_identifier), query) > 0,
                                     sa.func.strpos(sa.func.lower(delays.c.route_label), query) > 0))
        statement = sa.select(delays.c.route_identifier.label("identifier"),
                              sa.func.array_agg(sa.distinct(delays.c.route_label)).label("labels"),
                              sa.func.count().label("reported_records"), sa.func.min(delays.c.report_date).label("first_date"),
                              sa.func.max(delays.c.report_date).label("last_date"))
        statement = statement.where(*conditions).group_by(delays.c.route_identifier).order_by(sa.func.length(delays.c.route_identifier), delays.c.route_identifier)
        unassigned = read.connection.scalar(sa.select(sa.func.count()).select_from(delays).where(*read.conditions, delays.c.route_identifier.is_(None)))
        entries = [dict(row) for row in read.connection.execute(statement).mappings()]
        for entry in entries:
            entry["labels"] = sorted(entry["labels"])
        return {"context": read.context, "routes": entries, "unassigned_route_records": unassigned}


def records(engine, filters, page=1, page_size=25, sort="date_desc"):
    # Only these expressions can become ORDER BY clauses. User text is never SQL.
    orders = {
        "date_desc": [delays.c.report_date.desc(), delays.c.report_time.desc().nulls_last(), delays.c.row_number.desc()],
        "date_asc": [delays.c.report_date.asc(), delays.c.report_time.asc().nulls_last(), delays.c.row_number.asc()],
    }
    with selection(engine, filters) as read:
        total = read.connection.scalar(sa.select(sa.func.count()).select_from(delays).where(*read.conditions))
        statement = sa.select(*[delays.c[name] for name in (
            "row_number", "source_id", "report_date", "report_time", "route_identifier", "route_label", "location",
            "incident_code", "delay_minutes", "gap_minutes", "bound", "quality_flags")], codes.c.description,
            sa.case((codes.c.code.is_(None), "unmapped"), else_="mapped").label("mapping_status"))
        statement = statement.select_from(delays.outerjoin(codes, sa.and_(codes.c.snapshot_id == read.snapshot["lookup_snapshot_id"], codes.c.code == delays.c.incident_code)))
        statement = statement.where(*read.conditions).order_by(*orders[sort]).limit(page_size).offset((page - 1) * page_size)
        return {"context": read.context, "records": [dict(row) for row in read.connection.execute(statement).mappings()],
                "total_records": total, "page": page, "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size, "sort": sort}


def public_attempt(row):
    if not row:
        return None
    issue, message = None, None
    if row["status"] in {"failed", "interrupted"}:
        code = row["error_code"]
        issue = "validation_failed" if code == "contract_error" else "resource_busy" if code == "resource_busy" else "interrupted" if row["status"] == "interrupted" else "refresh_failed"
        message = "This refresh did not replace the selected data. The last successful version remains available."
    return {"id": row["id"], "status": row["status"], "started_at": utc(row["started_at"]),
            "finished_at": utc(row["finished_at"]), "snapshot_id": row["snapshot_id"], "issue": issue, "message": message}


def health(engine):
    output = []
    for resource in data_health(engine):
        snapshot = resource["active_snapshot"]
        output.append({"resource_id": resource["resource"]["id"], "kind": resource["resource"]["kind"],
                       "latest_attempt": public_attempt(resource["latest_attempt"]),
                       "last_successful_attempt": public_attempt(resource["last_successful_attempt"]),
                       "active_snapshot": public_snapshot(snapshot) if snapshot else None,
                       "coverage": coverage(snapshot), "quality": quality(snapshot) if snapshot else None})
    return {"resources": output, "attribution": "Contains information licensed under the Open Government Licence – Toronto.",
            "licence_url": "https://open.toronto.ca/open-data-licence/",
            "independent_project": "An independent project by Wentao Wu. No City of Toronto or TTC endorsement is implied."}
