"""Shared helpers. Synthetic records are deliberately labelled, not official observations."""

import csv
from datetime import datetime, timezone
import io
from pathlib import Path

from commute.ingest.adapter import DELAY_HEADERS
from commute.ingest.fetch import SourceFile

FIXTURES = Path(__file__).parent / "fixtures"


def synthetic_csv(rows: list[dict], headers=DELAY_HEADERS) -> bytes:
    defaults = {"_id": "synthetic-1", "Date": "2025-01-01T00:00:00", "Line": "102 MARKHAM ROAD",
                "Time": "08:00", "Day": "Wednesday", "Station": "SYNTHETIC LOCATION",
                "Code": "EFB", "Min Delay": "10", "Min Gap": "20", "Bound": "N", "Vehicle": "1234"}
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for i, values in enumerate(rows):
        writer.writerow({**defaults, "_id": f"synthetic-{i + 1}", **values})
    return text.getvalue().encode("utf-8")


def source_file(data: bytes) -> SourceFile:
    return SourceFile(data, "fixture://synthetic", datetime(2026, 11, 5, tzinfo=timezone.utc),
                      provenance={"input_kind": "synthetic_test"})
