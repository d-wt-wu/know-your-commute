"""Core tables. Migrations, rather than create_all(), own the database lifecycle."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = sa.MetaData(naming_convention={
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})

source_resources = sa.Table(
    "source_resources", metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column("official_resource_id", sa.Text, nullable=False),
    sa.Column("dataset_url", sa.Text, nullable=False),
    sa.Column("active_snapshot_id", UUID(as_uuid=True)),
    sa.CheckConstraint("kind IN ('delays', 'codes')", name="kind"),
    # An active pointer cannot accidentally select another resource's snapshot.
    sa.ForeignKeyConstraint(
        ["id", "active_snapshot_id"],
        ["source_snapshots.resource_id", "source_snapshots.id"],
        name="fk_resource_active_snapshot", use_alter=True,
    ),
)

source_snapshots = sa.Table(
    "source_snapshots", metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("resource_id", sa.Text, sa.ForeignKey("source_resources.id"), nullable=False),
    sa.Column("processing_key", sa.String(64), nullable=False),
    sa.Column("content_sha256", sa.String(64), nullable=False),
    sa.Column("parser_version", sa.Text, nullable=False),
    sa.Column("contract_version", sa.Text, nullable=False),
    sa.Column("lookup_snapshot_id", UUID(as_uuid=True), sa.ForeignKey("source_snapshots.id")),
    sa.Column("source_url", sa.Text, nullable=False),
    sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("source_last_modified", sa.Text),
    sa.Column("provenance", JSONB, nullable=False),
    sa.Column("headers", JSONB, nullable=False),
    sa.Column("schema_sha256", sa.String(64), nullable=False),
    sa.Column("extra_columns", JSONB, nullable=False),
    sa.Column("raw_count", sa.Integer, nullable=False),
    sa.Column("accepted_count", sa.Integer, nullable=False),
    sa.Column("rejected_count", sa.Integer, nullable=False),
    sa.Column("blank_line_count", sa.Integer, nullable=False),
    sa.Column("warning_record_count", sa.Integer, nullable=False),
    sa.Column("warning_counts", JSONB, nullable=False),
    sa.Column("coverage_start", sa.Date),
    sa.Column("coverage_end", sa.Date),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint("resource_id", "processing_key"),
    sa.UniqueConstraint("resource_id", "id", name="uq_snapshot_resource_id"),
    sa.CheckConstraint("raw_count = accepted_count + rejected_count", name="reconciled"),
    sa.CheckConstraint("accepted_count > 0 AND rejected_count >= 0 AND blank_line_count >= 0", name="counts"),
)

import_runs = sa.Table(
    "import_runs", metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("resource_id", sa.Text, sa.ForeignKey("source_resources.id"), nullable=False),
    sa.Column("snapshot_id", UUID(as_uuid=True), sa.ForeignKey("source_snapshots.id")),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("finished_at", sa.DateTime(timezone=True)),
    sa.Column("content_sha256", sa.String(64)),
    sa.Column("source_url", sa.Text),
    sa.Column("source_provenance", JSONB),
    sa.Column("error_code", sa.Text),
    sa.Column("error_summary", sa.Text),
    sa.CheckConstraint(
        "status IN ('running', 'succeeded', 'no_change', 'reactivated', 'failed', 'interrupted')",
        name="status",
    ),
)
sa.Index("ix_import_runs_resource_started", import_runs.c.resource_id, import_runs.c.started_at)

raw_records = sa.Table(
    "raw_records", metadata,
    sa.Column("snapshot_id", UUID(as_uuid=True), sa.ForeignKey("source_snapshots.id"), primary_key=True),
    sa.Column("row_number", sa.Integer, primary_key=True),
    sa.Column("line_start", sa.Integer, nullable=False),
    sa.Column("line_end", sa.Integer, nullable=False),
    sa.Column("payload", JSONB, nullable=False),
    sa.Column("payload_sha256", sa.String(64), nullable=False),
)

delay_records = sa.Table(
    "delay_records", metadata,
    sa.Column("snapshot_id", UUID(as_uuid=True), primary_key=True),
    sa.Column("row_number", sa.Integer, primary_key=True),
    sa.Column("source_id", sa.Text),
    sa.Column("report_date", sa.Date, nullable=False),
    sa.Column("report_time", sa.Time(timezone=False)),
    sa.Column("source_day", sa.Text),
    sa.Column("route_identifier", sa.Text),
    sa.Column("route_label", sa.Text),
    sa.Column("location", sa.Text),
    sa.Column("incident_code", sa.Text),
    sa.Column("delay_minutes", sa.Integer),
    sa.Column("gap_minutes", sa.Integer),
    sa.Column("bound", sa.Text),
    sa.Column("vehicle", sa.Text),
    sa.Column("quality_flags", JSONB, nullable=False),
    sa.ForeignKeyConstraint(["snapshot_id", "row_number"], ["raw_records.snapshot_id", "raw_records.row_number"]),
    sa.CheckConstraint("delay_minutes IS NULL OR delay_minutes >= 0", name="delay_nonnegative"),
    sa.CheckConstraint("gap_minutes IS NULL OR gap_minutes >= 0", name="gap_nonnegative"),
)
sa.Index("ix_delay_route_date", delay_records.c.snapshot_id, delay_records.c.route_identifier, delay_records.c.report_date)
sa.Index("ix_delay_date", delay_records.c.snapshot_id, delay_records.c.report_date)

incident_codes = sa.Table(
    "incident_codes", metadata,
    sa.Column("snapshot_id", UUID(as_uuid=True), primary_key=True),
    sa.Column("code", sa.Text, primary_key=True),
    sa.Column("row_number", sa.Integer, nullable=False),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("quality_flags", JSONB, nullable=False),
    sa.ForeignKeyConstraint(["snapshot_id", "row_number"], ["raw_records.snapshot_id", "raw_records.row_number"]),
)

rejected_records = sa.Table(
    "rejected_records", metadata,
    sa.Column("snapshot_id", UUID(as_uuid=True), primary_key=True),
    sa.Column("row_number", sa.Integer, primary_key=True),
    sa.Column("reasons", JSONB, nullable=False),
    sa.ForeignKeyConstraint(["snapshot_id", "row_number"], ["raw_records.snapshot_id", "raw_records.row_number"]),
)
