"""Audit each attempt; build in one transaction; promote one complete snapshot."""

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from commute.db.schema import source_resources as resources, source_snapshots as snapshots
from commute.db.schema import import_runs as runs, raw_records, delay_records, incident_codes, rejected_records
from commute.ingest.adapter import CONTRACT_VERSION, PARSER_VERSION, ContractError, fingerprint, parse_codes, parse_delays
from commute.ingest.fetch import SourceFile, now
from commute.ingest.registry import CODES, DATASET_URL, Resource


class ImportFailed(RuntimeError):
    def __init__(self, run_id: UUID, code: str, message: str):
        super().__init__(message)
        self.run_id = run_id
        self.code = code


@dataclass(frozen=True)
class ImportResult:
    run_id: UUID
    snapshot_id: UUID
    status: str
    raw_count: int
    accepted_count: int
    rejected_count: int
    warning_record_count: int


def resource_lock_key(resource: Resource) -> int:
    return int.from_bytes(hashlib.sha256(resource.key.encode()).digest()[:8], byteorder="big", signed=True)


def bulk_insert(connection, table, rows, snapshot_id):
    for start in range(0, len(rows), 1000):
        connection.execute(table.insert(), [{"snapshot_id": snapshot_id, **row} for row in rows[start:start + 1000]])


def import_resource(
    engine: Engine,
    resource: Resource,
    load: Callable[[], SourceFile],
    *,
    parser_version: str = PARSER_VERSION,
    contract_version: str = CONTRACT_VERSION,
    before_promote: Callable[[], None] | None = None,
) -> ImportResult:
    """The callback supports a deliberate failure/recovery drill before promotion.

    Running audit rows commit before download. A real process crash leaves that row
    running; the next holder of this resource's session lock marks it interrupted.
    """
    run_id = uuid4()
    with engine.begin() as audit:
        audit.execute(insert(resources).values(id=resource.key, kind=resource.kind,
                                               official_resource_id=resource.official_id, dataset_url=DATASET_URL)
                      .on_conflict_do_nothing(index_elements=[resources.c.id]))
        audit.execute(runs.insert().values(id=run_id, resource_id=resource.key, status="running", started_at=now()))
    locked = False
    try:
        with engine.connect() as connection:
            locked = connection.scalar(sa.text("SELECT pg_try_advisory_lock(:key)"), {"key": resource_lock_key(resource)})
            connection.commit()
            if not locked:
                raise ImportFailed(run_id, "resource_busy", "Another import holds this resource's lock; retry later.")
            try:
                with engine.begin() as audit:
                    audit.execute(runs.update().where(runs.c.resource_id == resource.key,
                                                       runs.c.status == "running", runs.c.id != run_id)
                                  .values(status="interrupted", finished_at=now(), error_code="interrupted",
                                          error_summary="Previous importer ended before recording completion."))
                source = load()
                with engine.begin() as audit:
                    audit.execute(runs.update().where(runs.c.id == run_id).values(
                        content_sha256=source.sha256, source_url=source.url, source_provenance=source.provenance or {}))
                with connection.begin():
                    lookup_id, descriptions = None, {}
                    if resource.kind == "delays":
                        lookup_id = connection.scalar(sa.select(resources.c.active_snapshot_id).where(resources.c.id == CODES.key))
                        if lookup_id is None:
                            raise ContractError("Import the official code lookup before the delay file.")
                        descriptions = {
                            code: description
                            for code, description in connection.execute(
                                sa.select(incident_codes.c.code, incident_codes.c.description)
                                .where(incident_codes.c.snapshot_id == lookup_id)
                            )
                        }
                    processing_key = fingerprint({"sha256": source.sha256, "parser": parser_version,
                                                  "contract": contract_version, "lookup_snapshot_id": str(lookup_id)})
                    existing = connection.execute(sa.select(snapshots).where(snapshots.c.resource_id == resource.key,
                                                                              snapshots.c.processing_key == processing_key)).mappings().first()
                    current = connection.scalar(sa.select(resources.c.active_snapshot_id).where(resources.c.id == resource.key))
                    if existing:
                        snapshot_id = existing["id"]
                        status = "no_change" if current == snapshot_id else "reactivated"
                        counts = dict(existing)
                    else:
                        parsed = parse_delays(source.data, descriptions) if resource.kind == "delays" else parse_codes(source.data)
                        snapshot_id, status = uuid4(), "succeeded"
                        dates = [r["report_date"] for r in parsed.accepted] if resource.kind == "delays" else []
                        counts = {"raw_count": len(parsed.raw), "accepted_count": len(parsed.accepted),
                                  "rejected_count": len(parsed.rejected), "warning_record_count": parsed.warning_record_count}
                        connection.execute(snapshots.insert().values(
                            id=snapshot_id, resource_id=resource.key, processing_key=processing_key,
                            content_sha256=source.sha256, parser_version=parser_version, contract_version=contract_version,
                            lookup_snapshot_id=lookup_id, source_url=source.url, retrieved_at=source.retrieved_at,
                            source_last_modified=source.source_last_modified, provenance=source.provenance or {},
                            headers=parsed.headers, schema_sha256=fingerprint({"headers": parsed.headers}),
                            extra_columns=parsed.extra_columns, blank_line_count=parsed.blank_line_count,
                            warning_counts=parsed.warning_counts, coverage_start=min(dates) if dates else None,
                            coverage_end=max(dates) if dates else None, **counts,
                        ))
                        bulk_insert(connection, raw_records, parsed.raw, snapshot_id)
                        bulk_insert(connection, delay_records if resource.kind == "delays" else incident_codes, parsed.accepted, snapshot_id)
                        if parsed.rejected:
                            bulk_insert(connection, rejected_records, parsed.rejected, snapshot_id)
                        # Check the actual staged rows, not just the parser's counters.
                        actual_raw = connection.scalar(sa.select(sa.func.count()).select_from(raw_records).where(raw_records.c.snapshot_id == snapshot_id))
                        typed_table = delay_records if resource.kind == "delays" else incident_codes
                        actual_accepted = connection.scalar(sa.select(sa.func.count()).select_from(typed_table).where(typed_table.c.snapshot_id == snapshot_id))
                        actual_rejected = connection.scalar(sa.select(sa.func.count()).select_from(rejected_records).where(rejected_records.c.snapshot_id == snapshot_id))
                        if (actual_raw, actual_accepted, actual_rejected) != (counts["raw_count"], counts["accepted_count"], counts["rejected_count"]):
                            raise ContractError("Staged database rows failed count reconciliation.")
                    if before_promote:
                        before_promote()
                    connection.execute(resources.update().where(resources.c.id == resource.key).values(active_snapshot_id=snapshot_id))
                    connection.execute(runs.update().where(runs.c.id == run_id).values(
                        snapshot_id=snapshot_id, status=status, finished_at=now()))
                return ImportResult(run_id, snapshot_id, status, counts["raw_count"], counts["accepted_count"],
                                    counts["rejected_count"], counts["warning_record_count"])
            finally:
                # Session-level locks survive rollback, so always release explicitly.
                if connection.in_transaction():
                    connection.rollback()
                connection.execute(sa.text("SELECT pg_advisory_unlock(:key)"), {"key": resource_lock_key(resource)})
                connection.commit()
    except Exception as exc:
        code = exc.code if isinstance(exc, ImportFailed) else ("contract_error" if isinstance(exc, ContractError) else type(exc).__name__)
        message = str(exc) if isinstance(exc, (ContractError, ImportFailed)) else "Import failed; the previous active snapshot was retained. Inspect the local exception for details."
        with engine.begin() as audit:
            audit.execute(runs.update().where(runs.c.id == run_id).values(
                status="failed", finished_at=now(), error_code=code, error_summary=message[:500]))
        if isinstance(exc, ImportFailed):
            raise
        raise ImportFailed(run_id, code, message) from exc
