#!/usr/bin/env python3
"""Reproduce the profile and attributed fixture from a verified download manifest."""

import argparse
from collections import Counter
import csv
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from commute.ingest.adapter import DELAY_HEADERS, parse_codes, parse_delays
from commute.ingest.fetch import load_manifest_file
from commute.ingest.registry import CODES, DELAYS, README_ID, DATASET_URL

ROOT = Path(__file__).resolve().parents[1]


def readme_cells(data: bytes) -> list[list[str]]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        strings = ["".join(x.itertext()) for x in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", ns)]
        output = []
        for row in ET.fromstring(archive.read("xl/worksheets/sheet1.xml")).findall(".//m:row", ns):
            values = []
            for cell in row.findall("m:c", ns):
                value = cell.find("m:v", ns)
                if value is not None:
                    values.append(strings[int(value.text)] if cell.attrib.get("t") == "s" else value.text)
            if values:
                output.append(values)
        return output


def write_fixture(parsed, source, lookup, manifest):
    selected = set(range(min(12, len(parsed.raw))))
    for flag in ["route_missing", "route_unparsed", "code_unmapped", "weekday_mismatch", "description_encoding_suspect"]:
        record = next((r for r in parsed.accepted if flag in r["quality_flags"]), None)
        if record:
            selected.add(record["row_number"] - 2)
    groups = {}
    for index, row in enumerate(parsed.raw):
        groups.setdefault(row["payload_sha256"], []).append(index)
    pair = next((indices for indices in groups.values() if len(indices) > 1), [])
    selected.update(pair[:2])
    selected.add(len(parsed.raw) - 1)
    positions = sorted(selected)
    folder = ROOT / "tests/fixtures"
    path = folder / "ttc-bus-sample.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=parsed.headers, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(parsed.raw[i]["payload"] for i in positions)
    (folder / "codes.csv").write_bytes(lookup.data)
    description = {
        "dataset_url": DATASET_URL,
        "attribution": "Contains information licensed under the Open Government Licence – Toronto.",
        "licence_url": "https://open.toronto.ca/open-data-licence/",
        "source_manifest": "docs/source-manifest.json",
        "delay_source_sha256": source.sha256,
        "lookup_source_sha256": lookup.sha256,
        "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "selection": "First twelve source rows, first examples of named quality flags, first repeated payload pair, last row; unique source positions, sorted.",
        "transformation": "Original cell strings, UTF-8, CRLF CSV serialization; no value corrections or deduplication.",
        "rows": [{"fixture_row_number": i + 2, "source_row_number": parsed.raw[index]["row_number"],
                  "source_id": parsed.raw[index]["payload"]["_id"]} for i, index in enumerate(positions)],
    }
    (folder / "manifest.json").write_text(json.dumps(description, indent=2, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/raw/download-manifest.json")
    parser.add_argument("--write-fixture", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    source = load_manifest_file(args.manifest, DELAYS)
    lookup = load_manifest_file(args.manifest, CODES)
    codes = parse_codes(lookup.data)
    parsed = parse_delays(source.data, {r["code"]: r["description"] for r in codes.accepted})
    dates = [r["report_date"] for r in parsed.accepted]
    payloads = Counter(r["payload_sha256"] for r in parsed.raw)
    profile = {
        "content_sha256": source.sha256, "lookup_sha256": lookup.sha256,
        "columns": parsed.headers, "extra_columns": parsed.extra_columns,
        "raw_records": len(parsed.raw), "accepted_records": len(parsed.accepted),
        "rejected_records": len(parsed.rejected), "blank_lines": parsed.blank_line_count,
        "observed_dates": {"min": str(min(dates)), "max": str(max(dates)), "distinct": len(set(dates))},
        "blank_cells": {key: sum(not row["payload"][key] for row in parsed.raw) for key in parsed.headers},
        "distinct_values": {key: len({row["payload"][key] for row in parsed.raw}) for key in parsed.headers},
        "warning_record_count": parsed.warning_record_count, "warning_counts": parsed.warning_counts,
        "repeated_payload_groups": sum(count > 1 for count in payloads.values()),
        "repeated_payload_extra_rows": sum(count - 1 for count in payloads.values()),
        "unmapped_codes": dict(Counter(row["incident_code"] for row in parsed.accepted if "code_unmapped" in row["quality_flags"])),
        "lookup_entries": len(codes.accepted), "lookup_warning_counts": codes.warning_counts,
        "scope": "A profile of these exact bytes, not proof of complete service coverage or stable source identifiers.",
    }
    readme_entry = next(r for r in manifest["resources"] if r["id"] == README_ID)
    readme = (args.manifest.parent / readme_entry["path"]).read_bytes()
    if hashlib.sha256(readme).hexdigest() != readme_entry["sha256"]:
        raise ValueError("README checksum mismatch")
    # Small, inspectable evidence about the actual older README used for the contract.
    profile["readme_cells"] = readme_cells(readme)
    (ROOT / "docs/source-profile.json").write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
    (ROOT / "docs/source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if args.write_fixture:
        write_fixture(parsed, source, lookup, manifest)
    print(json.dumps({key: profile[key] for key in ["raw_records", "accepted_records", "rejected_records", "observed_dates", "warning_record_count", "warning_counts"]}, indent=2))


if __name__ == "__main__":
    main()
