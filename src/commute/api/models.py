from datetime import date, datetime, time
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from commute.query import Filters


class FilterQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route: str | None = Field(default=None, max_length=100)
    start: date | None = None
    end: date | None = None
    snapshot_id: UUID | None = None

    @field_validator("route")
    @classmethod
    def nonempty_route(cls, value):
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("Route must be nonempty; omit it for all recorded routes.")
        return value

    @field_validator("start", "end", mode="before")
    @classmethod
    def iso_dates(cls, value):
        if isinstance(value, str) and not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("Use a calendar date in YYYY-MM-DD form.")
        return value

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.start and self.end and self.start > self.end:
            raise ValueError("Start date must be on or before end date.")
        return self

    def selection(self) -> Filters:
        return Filters(**{name: getattr(self, name) for name in Filters.__dataclass_fields__})


class RoutesQuery(FilterQuery):
    q: str | None = Field(default=None, max_length=80)


class RecordsQuery(FilterQuery):
    page: int = Field(default=1, ge=1, le=10_000)
    page_size: int = Field(default=25, ge=1, le=100)
    sort: Literal["date_desc", "date_asc"] = "date_desc"


class PublicSnapshot(BaseModel):
    id: UUID
    resource_id: str
    content_sha256: str
    lookup_snapshot_id: UUID | None
    source_url: str | None
    dataset_url: str
    source_last_modified: str | None
    source_metadata_modified: str | None
    retrieved_at: datetime
    imported_at: datetime
    parser_version: str
    contract_version: str


class Coverage(BaseModel):
    start: date | None
    end: date | None
    meaning: str = "Observed record dates; completeness of disruption reporting is not established."


class Quality(BaseModel):
    scope: Literal["entire_active_delay_snapshot", "entire_selected_snapshot"] = "entire_selected_snapshot"
    raw_count: int
    accepted_count: int
    rejected_count: int
    warning_record_count: int
    warning_counts: dict[str, int]
    extra_columns: list[str]


class AppliedFilters(BaseModel):
    route: str | None
    start: date
    end: date
    date_bounds: Literal["inclusive"] = "inclusive"


class Context(BaseModel):
    snapshot: PublicSnapshot
    filters: AppliedFilters
    coverage: Coverage
    extends_beyond_loaded_dates: bool


class Statistics(BaseModel):
    reported_records: int
    valid_delay_samples: int
    zero_delay_samples: int
    median_recorded_delay_minutes: float | None
    mean_recorded_delay_minutes: float | None
    valid_gap_samples: int
    flagged_records: int
    first_matching_date: date | None
    last_matching_date: date | None


class SummaryResponse(BaseModel):
    context: Context
    summary: Statistics
    quality: Quality
    definitions: dict[str, str]


class DailyCount(BaseModel):
    report_date: date
    reported_records: int


class CauseCount(BaseModel):
    incident_code: str | None
    description: str | None
    mapping_status: Literal["mapped", "unmapped"]
    reported_records: int


class WeekdayCount(BaseModel):
    iso_weekday: int
    reported_records: int


class PatternsResponse(BaseModel):
    context: Context
    daily_records: list[DailyCount]
    causes: list[CauseCount]
    calendar_weekdays: list[WeekdayCount]
    missing_dates_meaning: str
    time_analysis_note: str


class RouteEntry(BaseModel):
    identifier: str
    labels: list[str]
    reported_records: int
    first_date: date
    last_date: date


class RoutesResponse(BaseModel):
    context: Context
    routes: list[RouteEntry]
    unassigned_route_records: int


class Record(BaseModel):
    row_number: int
    source_id: str | None
    report_date: date
    report_time: time | None
    route_identifier: str | None
    route_label: str | None
    location: str | None
    incident_code: str | None
    description: str | None
    mapping_status: Literal["mapped", "unmapped"]
    delay_minutes: int | None
    gap_minutes: int | None
    bound: str | None
    quality_flags: list[str]


class RecordsResponse(BaseModel):
    context: Context
    records: list[Record]
    total_records: int
    page: int
    page_size: int
    total_pages: int
    sort: Literal["date_desc", "date_asc"]


class Attempt(BaseModel):
    id: UUID
    status: Literal["running", "succeeded", "no_change", "reactivated", "failed", "interrupted"]
    started_at: datetime
    finished_at: datetime | None
    snapshot_id: UUID | None
    issue: str | None
    message: str | None


class ResourceHealth(BaseModel):
    resource_id: str
    kind: Literal["delays", "codes"]
    latest_attempt: Attempt | None
    last_successful_attempt: Attempt | None
    active_snapshot: PublicSnapshot | None
    coverage: Coverage
    quality: Quality | None


class DataHealthResponse(BaseModel):
    resources: list[ResourceHealth]
    attribution: str
    licence_url: str
    independent_project: str
