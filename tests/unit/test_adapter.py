from datetime import date, time
import hashlib
import json

import pytest

from commute.ingest.adapter import ContractError, DELAY_HEADERS, parse_codes, parse_delays
from tests.helpers import FIXTURES, synthetic_csv


def test_missing_duration_is_not_zero_and_invalid_duration_stays_traceable():
    parsed = parse_delays(synthetic_csv([{"Min Delay": ""}, {"Min Delay": "0"}, {"Min Delay": "-3"}, {"Min Delay": "bad"}]), {"EFB": "BODY"})
    assert [row["delay_minutes"] for row in parsed.accepted] == [None, 0, None, None]
    assert parsed.raw[2]["payload"]["Min Delay"] == "-3"
    assert parsed.warning_counts["delay_invalid"] == 2


def test_unknown_values_and_ambiguous_time_are_preserved():
    parsed = parse_delays(synthetic_csv([{"Line": "LINE 2 SHUTTLE", "Code": "NEW", "Time": "25:00", "Bound": "?"}]), {})
    row = parsed.accepted[0]
    assert row["route_identifier"] is None
    assert row["route_label"] == "LINE 2 SHUTTLE"
    assert row["incident_code"] == "NEW" and row["report_time"] is None
    assert {"route_unparsed", "code_unmapped", "time_invalid", "bound_unrecognized"} <= set(row["quality_flags"])
    assert parsed.raw[0]["payload"]["Time"] == "25:00"


def test_branch_routes_are_not_merged_and_timezone_is_not_invented():
    parsed = parse_delays(synthetic_csv([{"Line": "102D MARKHAM ROAD", "Time": "00:01", "Day": "Monday"}]), {"EFB": "BODY"})
    row = parsed.accepted[0]
    assert row["route_identifier"] == "102D"
    assert row["report_date"] == date(2025, 1, 1) and row["report_time"] == time(0, 1)
    assert "weekday_mismatch" in row["quality_flags"]


def test_extra_columns_survive_and_missing_headers_fail():
    headers = (*DELAY_HEADERS, "Publisher Extra")
    parsed = parse_delays(synthetic_csv([{"Publisher Extra": "keep"}], headers), {})
    assert parsed.extra_columns == ["Publisher Extra"]
    assert parsed.raw[0]["payload"]["Publisher Extra"] == "keep"
    with pytest.raises(ContractError, match="Missing required columns"):
        parse_delays(synthetic_csv([{}], DELAY_HEADERS[:-1]), {})


def test_extra_column_cannot_collide_with_malformed_row_bookkeeping():
    parsed = parse_delays(synthetic_csv([{"__cells__": "publisher value"}], (*DELAY_HEADERS, "__cells__")), {})
    assert len(parsed.accepted) == 1 and not parsed.rejected
    assert parsed.raw[0]["payload"]["__cells__"] == "publisher value"


def test_only_unusable_date_is_quarantined_and_totals_reconcile():
    parsed = parse_delays(synthetic_csv([{}, {"Date": "2025-02-30T00:00:00"}, {"Date": "2024-12-31T00:00:00"}]), {})
    assert (len(parsed.raw), len(parsed.accepted), len(parsed.rejected)) == (3, 1, 2)
    assert parsed.rejected[0]["reasons"] == ["invalid_or_out_of_scope_date"]


def test_repeated_payloads_remain_separate_rows_despite_different_source_ids():
    parsed = parse_delays(synthetic_csv([{}, {}]), {"EFB": "BODY"})
    assert len(parsed.accepted) == 2
    assert parsed.raw[0]["payload_sha256"] == parsed.raw[1]["payload_sha256"]
    assert all("repeated_payload" in row["quality_flags"] for row in parsed.accepted)


@pytest.mark.parametrize("data", [b"<html>upstream error</html>", b"", b"Date,Date\n1,1\n", b"\xff\xfe", b"\x00"])
def test_bad_documents_fail_usefully(data):
    with pytest.raises(ContractError):
        parse_delays(data, {})


def test_blank_physical_lines_and_multiline_fields_have_documented_positions():
    data = synthetic_csv([{"Station": "SYNTHETIC\nSTATION"}, {"Time": "09:00"}]) + b"\r\n"
    parsed = parse_delays(data, {})
    assert len(parsed.raw) == 2 and parsed.blank_line_count == 1
    assert (parsed.raw[0]["line_start"], parsed.raw[0]["line_end"]) == (2, 3)
    assert parsed.raw[1]["line_start"] == 4


def test_broken_row_width_is_quarantined_without_losing_cells():
    data = synthetic_csv([{}]) + b"too,few\r\n"
    parsed = parse_delays(data, {})
    assert parsed.rejected[0]["reasons"] == ["column_count_mismatch"]
    assert parsed.raw[1]["payload"]["__cells__"] == ["too", "few"]


def test_lookup_encoding_is_flagged_without_guessing_a_repair(official_lookup):
    parsed = parse_codes(official_lookup)
    assert len(parsed.accepted) == 46
    suspect = next(r for r in parsed.accepted if r["code"] == "MFUIR")
    assert "\u0080" in suspect["description"]
    assert suspect["quality_flags"] == ["description_encoding_suspect"]
    with pytest.raises(ContractError, match="duplicate"):
        parse_codes(b"_id,CODE,DESCRIPTION\n1,A,one\n2,A,two\n")


def test_real_attributed_fixture_is_usable_and_unchanged(official_lookup):
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    raw = (FIXTURES / "ttc-bus-sample.csv").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["fixture_sha256"]
    codes = {r["code"]: r["description"] for r in parse_codes(official_lookup).accepted}
    parsed = parse_delays(raw, codes)
    assert len(parsed.raw) == len(manifest["rows"]) and not parsed.rejected
    assert parsed.warning_counts["route_missing"] >= 1
    assert parsed.warning_counts["code_unmapped"] >= 1
