"""Contract v1: preserve strings, quarantine unusable dates, flag usable anomalies."""

from collections import Counter
import csv
from dataclasses import dataclass, field
from datetime import datetime, date, time
import hashlib
import io
import json
import re

DELAY_HEADERS = ("_id", "Date", "Line", "Time", "Day", "Station", "Code", "Min Delay", "Min Gap", "Bound", "Vehicle")
CODE_HEADERS = ("_id", "CODE", "DESCRIPTION")
CONTRACT_VERSION = "1"
PARSER_VERSION = "1"
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class ContractError(ValueError):
    pass


def fingerprint(payload: dict) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def encoding_warning(text: str) -> bool:
    # Evidence of the publisher's mojibake; preserve it, do not guess a repair.
    return "\u0080" in text or "â\u0080" in text


@dataclass
class Parsed:
    headers: list[str]
    extra_columns: list[str]
    raw: list[dict] = field(default_factory=list)
    accepted: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    blank_line_count: int = 0
    malformed_rows: set[int] = field(default_factory=set)

    @property
    def warning_counts(self) -> dict[str, int]:
        return dict(Counter(flag for row in self.accepted for flag in row["quality_flags"]))

    @property
    def warning_record_count(self) -> int:
        return sum(bool(row["quality_flags"]) for row in self.accepted)


def csv_rows(data: bytes, kind: str) -> Parsed:
    if data.lstrip().lower().startswith((b"<!doctype html", b"<html")):
        raise ContractError("Received HTML instead of a CSV.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ContractError("Expected UTF-8 CSV; original bytes are retained.") from exc
    if "\x00" in text:
        raise ContractError("NUL byte in CSV.")
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        headers = next(reader)
    except (StopIteration, csv.Error) as exc:
        raise ContractError("Missing or malformed CSV header.") from exc
    required = DELAY_HEADERS if kind == "delays" else CODE_HEADERS
    if len(headers) != len(set(headers)) or any(not h for h in headers):
        raise ContractError("CSV headers must be unique and nonempty.")
    missing = sorted(set(required) - set(headers))
    if missing:
        raise ContractError(f"Missing required columns: {', '.join(missing)}.")
    parsed = Parsed(headers=headers, extra_columns=[h for h in headers if h not in required])
    logical_row = 1  # Header is CSV record 1. Blank physical lines are not data records.
    try:
        while True:
            line_start = reader.line_num + 1
            try:
                cells = next(reader)
            except StopIteration:
                break
            if not cells:
                parsed.blank_line_count += 1
                continue
            logical_row += 1
            payload = dict(zip(headers, cells))
            if len(cells) != len(headers):
                # Preserve every cell on a malformed row as well as its available fields.
                payload = {"__cells__": cells, "__fields__": payload}
                parsed.malformed_rows.add(logical_row)
            parsed.raw.append({
                "row_number": logical_row, "line_start": line_start, "line_end": reader.line_num,
                "payload": payload,
                "payload_sha256": fingerprint({k: v for k, v in payload.items() if k != "_id"}),
            })
    except csv.Error as exc:
        # A broken quoting structure cannot be assigned reliable row boundaries.
        raise ContractError("Malformed CSV quoting; snapshot was not promoted.") from exc
    if not parsed.raw:
        raise ContractError("Header-only or blank CSV cannot replace an active snapshot.")
    return parsed


def numeric_minutes(value: str, field_name: str, flags: list[str]) -> int | None:
    if not value.strip():
        flags.append(f"{field_name}_missing")
        return None
    if re.fullmatch(r"[0-9]+", value.strip()) and len(value.strip()) <= 10:
        number = int(value)
        if number <= 2_147_483_647:
            if number == 0:
                flags.append(f"{field_name}_zero_reported")
            return number
    flags.append(f"{field_name}_invalid")
    return None


def parse_codes(data: bytes) -> Parsed:
    parsed = csv_rows(data, "codes")
    seen = set()
    for raw in parsed.raw:
        payload = raw["payload"]
        code = payload.get("CODE", "").strip()
        description = payload.get("DESCRIPTION", "")
        if raw["row_number"] in parsed.malformed_rows or not code or not description.strip() or code in seen:
            raise ContractError("Lookup has malformed, empty or duplicate code entries; refusing ambiguous mapping.")
        seen.add(code)
        flags = ["description_encoding_suspect"] if encoding_warning(description) else []
        parsed.accepted.append({"row_number": raw["row_number"], "code": code,
                                "description": description, "quality_flags": flags})
    return parsed


def parse_delays(data: bytes, code_descriptions: dict[str, str]) -> Parsed:
    parsed = csv_rows(data, "delays")
    repeated = Counter(row["payload_sha256"] for row in parsed.raw)
    source_ids = Counter(row["payload"].get("_id", "") for row in parsed.raw)
    for raw in parsed.raw:
        payload = raw["payload"]
        number = raw["row_number"]
        if number in parsed.malformed_rows:
            parsed.rejected.append({"row_number": number, "reasons": ["column_count_mismatch"]})
            continue
        try:
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T00:00:00", payload["Date"]):
                raise ValueError
            report_date = date.fromisoformat(payload["Date"][:10])
            if report_date < date(2025, 1, 1):
                raise ValueError
        except ValueError:
            parsed.rejected.append({"row_number": number, "reasons": ["invalid_or_out_of_scope_date"]})
            continue
        flags = []
        source_time = payload["Time"].strip()
        try:
            if not re.fullmatch(r"[0-9]{2}:[0-9]{2}", source_time):
                raise ValueError
            report_time = time.fromisoformat(source_time)
        except ValueError:
            report_time = None
            flags.append("time_missing" if not source_time else "time_invalid")
        source_day = payload["Day"].strip()
        if source_day != WEEKDAYS[report_date.weekday()]:
            flags.append("weekday_mismatch")
        route_label = payload["Line"].strip() or None
        match = re.fullmatch(r"([0-9]{1,4}[A-Za-z]?)(?:\s+.+)?", route_label or "")
        route_identifier = match[1] if match else None
        if not route_label:
            flags.append("route_missing")
        elif not route_identifier:
            flags.append("route_unparsed")
        code = payload["Code"].strip() or None
        if not code:
            flags.append("code_missing")
        elif code not in code_descriptions:
            flags.append("code_unmapped")
        elif encoding_warning(code_descriptions[code]):
            flags.append("description_encoding_suspect")
        delay = numeric_minutes(payload["Min Delay"], "delay", flags)
        gap = numeric_minutes(payload["Min Gap"], "gap", flags)
        bound = payload["Bound"].strip() or None
        if bound is None:
            flags.append("bound_missing")
        elif bound not in {"N", "S", "E", "W", "B", "b", "BW", "NB", "SB", "EB", "WB"}:
            flags.append("bound_unrecognized")
        vehicle = payload["Vehicle"].strip() or None
        if vehicle is None or vehicle == "0":
            flags.append("vehicle_missing" if vehicle is None else "vehicle_zero_reported")
        if not payload["Station"].strip():
            flags.append("location_missing")
        source_id = payload["_id"].strip() or None
        if not source_id:
            flags.append("source_id_missing")
        elif source_ids[payload["_id"]] > 1:
            flags.append("source_id_repeated")
        if repeated[raw["payload_sha256"]] > 1:
            flags.append("repeated_payload")
        parsed.accepted.append({
            "row_number": number, "source_id": source_id, "report_date": report_date,
            "report_time": report_time, "source_day": source_day or None,
            "route_identifier": route_identifier, "route_label": route_label,
            "location": payload["Station"].strip() or None, "incident_code": code,
            "delay_minutes": delay, "gap_minutes": gap, "bound": bound, "vehicle": vehicle,
            "quality_flags": flags,
        })
    if not parsed.accepted:
        raise ContractError("No usable dated records; snapshot was not promoted.")
    assert len(parsed.raw) == len(parsed.accepted) + len(parsed.rejected)
    return parsed
