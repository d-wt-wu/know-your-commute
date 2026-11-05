"""The shared route/date selection used by the reporting endpoints."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class Filters:
    route: str | None = None
    start: date | None = None
    end: date | None = None
    snapshot_id: UUID | None = None


class NoData(ValueError):
    pass


class MissingSnapshot(ValueError):
    pass


class InvalidRange(ValueError):
    pass
