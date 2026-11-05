"""Versioned sources, audited imports and historical reported records.

Frozen initial schema; future model changes require a new migration.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():

    op.create_table('source_resources',
    sa.Column('id', sa.Text(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('official_resource_id', sa.Text(), nullable=False),
    sa.Column('dataset_url', sa.Text(), nullable=False),
    sa.Column('active_snapshot_id', sa.UUID(), nullable=True),
    sa.CheckConstraint("kind IN ('delays', 'codes')", name=op.f('ck_source_resources_kind')),
    sa.ForeignKeyConstraint(['id', 'active_snapshot_id'], ['source_snapshots.resource_id', 'source_snapshots.id'], name='fk_resource_active_snapshot', use_alter=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_source_resources'))
    )
    op.create_table('source_snapshots',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('resource_id', sa.Text(), nullable=False),
    sa.Column('processing_key', sa.String(length=64), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('parser_version', sa.Text(), nullable=False),
    sa.Column('contract_version', sa.Text(), nullable=False),
    sa.Column('lookup_snapshot_id', sa.UUID(), nullable=True),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('source_last_modified', sa.Text(), nullable=True),
    sa.Column('provenance', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('headers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('schema_sha256', sa.String(length=64), nullable=False),
    sa.Column('extra_columns', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('raw_count', sa.Integer(), nullable=False),
    sa.Column('accepted_count', sa.Integer(), nullable=False),
    sa.Column('rejected_count', sa.Integer(), nullable=False),
    sa.Column('blank_line_count', sa.Integer(), nullable=False),
    sa.Column('warning_record_count', sa.Integer(), nullable=False),
    sa.Column('warning_counts', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('coverage_start', sa.Date(), nullable=True),
    sa.Column('coverage_end', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('accepted_count > 0 AND rejected_count >= 0 AND blank_line_count >= 0', name=op.f('ck_source_snapshots_counts')),
    sa.CheckConstraint('raw_count = accepted_count + rejected_count', name=op.f('ck_source_snapshots_reconciled')),
    sa.ForeignKeyConstraint(['lookup_snapshot_id'], ['source_snapshots.id'], name=op.f('fk_source_snapshots_lookup_snapshot_id_source_snapshots')),
    sa.ForeignKeyConstraint(['resource_id'], ['source_resources.id'], name=op.f('fk_source_snapshots_resource_id_source_resources')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_source_snapshots')),
    sa.UniqueConstraint('resource_id', 'id', name='uq_snapshot_resource_id'),
    sa.UniqueConstraint('resource_id', 'processing_key', name=op.f('uq_source_snapshots_resource_id'))
    )
    op.create_table('import_runs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('resource_id', sa.Text(), nullable=False),
    sa.Column('snapshot_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('content_sha256', sa.String(length=64), nullable=True),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('source_provenance', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error_code', sa.Text(), nullable=True),
    sa.Column('error_summary', sa.Text(), nullable=True),
    sa.CheckConstraint("status IN ('running', 'succeeded', 'no_change', 'reactivated', 'failed', 'interrupted')", name=op.f('ck_import_runs_status')),
    sa.ForeignKeyConstraint(['resource_id'], ['source_resources.id'], name=op.f('fk_import_runs_resource_id_source_resources')),
    sa.ForeignKeyConstraint(['snapshot_id'], ['source_snapshots.id'], name=op.f('fk_import_runs_snapshot_id_source_snapshots')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_import_runs'))
    )
    op.create_index('ix_import_runs_resource_started', 'import_runs', ['resource_id', 'started_at'], unique=False)
    op.create_table('raw_records',
    sa.Column('snapshot_id', sa.UUID(), nullable=False),
    sa.Column('row_number', sa.Integer(), nullable=False),
    sa.Column('line_start', sa.Integer(), nullable=False),
    sa.Column('line_end', sa.Integer(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('payload_sha256', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['snapshot_id'], ['source_snapshots.id'], name=op.f('fk_raw_records_snapshot_id_source_snapshots')),
    sa.PrimaryKeyConstraint('snapshot_id', 'row_number', name=op.f('pk_raw_records'))
    )
    op.create_table('delay_records',
    sa.Column('snapshot_id', sa.UUID(), nullable=False),
    sa.Column('row_number', sa.Integer(), nullable=False),
    sa.Column('source_id', sa.Text(), nullable=True),
    sa.Column('report_date', sa.Date(), nullable=False),
    sa.Column('report_time', sa.Time(), nullable=True),
    sa.Column('source_day', sa.Text(), nullable=True),
    sa.Column('route_identifier', sa.Text(), nullable=True),
    sa.Column('route_label', sa.Text(), nullable=True),
    sa.Column('location', sa.Text(), nullable=True),
    sa.Column('incident_code', sa.Text(), nullable=True),
    sa.Column('delay_minutes', sa.Integer(), nullable=True),
    sa.Column('gap_minutes', sa.Integer(), nullable=True),
    sa.Column('bound', sa.Text(), nullable=True),
    sa.Column('vehicle', sa.Text(), nullable=True),
    sa.Column('quality_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.CheckConstraint('delay_minutes IS NULL OR delay_minutes >= 0', name=op.f('ck_delay_records_delay_nonnegative')),
    sa.CheckConstraint('gap_minutes IS NULL OR gap_minutes >= 0', name=op.f('ck_delay_records_gap_nonnegative')),
    sa.ForeignKeyConstraint(['snapshot_id', 'row_number'], ['raw_records.snapshot_id', 'raw_records.row_number'], name=op.f('fk_delay_records_snapshot_id_raw_records')),
    sa.PrimaryKeyConstraint('snapshot_id', 'row_number', name=op.f('pk_delay_records'))
    )
    op.create_index('ix_delay_date', 'delay_records', ['snapshot_id', 'report_date'], unique=False)
    op.create_index('ix_delay_route_date', 'delay_records', ['snapshot_id', 'route_identifier', 'report_date'], unique=False)
    op.create_table('incident_codes',
    sa.Column('snapshot_id', sa.UUID(), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('row_number', sa.Integer(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('quality_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['snapshot_id', 'row_number'], ['raw_records.snapshot_id', 'raw_records.row_number'], name=op.f('fk_incident_codes_snapshot_id_raw_records')),
    sa.PrimaryKeyConstraint('snapshot_id', 'code', name=op.f('pk_incident_codes'))
    )
    op.create_table('rejected_records',
    sa.Column('snapshot_id', sa.UUID(), nullable=False),
    sa.Column('row_number', sa.Integer(), nullable=False),
    sa.Column('reasons', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['snapshot_id', 'row_number'], ['raw_records.snapshot_id', 'raw_records.row_number'], name=op.f('fk_rejected_records_snapshot_id_raw_records')),
    sa.PrimaryKeyConstraint('snapshot_id', 'row_number', name=op.f('pk_rejected_records'))
    )
    op.create_foreign_key('fk_resource_active_snapshot', 'source_resources', 'source_snapshots', ['id', 'active_snapshot_id'], ['resource_id', 'id'], use_alter=True)



def downgrade():

    op.drop_constraint('fk_resource_active_snapshot', 'source_resources', type_='foreignkey')
    op.drop_table('rejected_records')
    op.drop_table('incident_codes')
    op.drop_table('delay_records')
    op.drop_table('raw_records')
    op.drop_table('import_runs')
    op.drop_table('source_snapshots')
    op.drop_table('source_resources')
