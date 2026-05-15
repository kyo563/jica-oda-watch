import json
import subprocess
import sys
from unittest.mock import Mock

import pytest

from scripts.update_sheets import (
    RAW_SHEET,
    WATCH_SHEET,
    apply_updates,
    build_history_rows,
    build_raw_rows,
    build_watch_upserts,
    column_letter,
    dict_rows_to_values,
    plan_updates,
    quote_sheet_name,
    rows_to_dicts,
)


def test_watch_payload_excludes_manual_fields_from_auto_values():
    projects = [{"project_id": "P1", "project_name": "new", "status_auto": "updated"}]
    existing_rows = [{
        "project_id": "P1",
        "manual_status": "確認中",
        "memo": "手入力メモ",
        "next_manual_action": "連絡",
        "owner": "A",
        "manual_checked_date": "2026-05-01",
        "manual_updated_at": "2026-05-01T00:00:00Z",
        "manual_updated_by": "user",
    }]
    auto_fields = ["project_id", "project_name", "status_auto"]
    manual_fields = [
        "manual_status",
        "memo",
        "next_manual_action",
        "owner",
        "manual_checked_date",
        "manual_updated_at",
        "manual_updated_by",
    ]

    upserts, _ = build_watch_upserts(projects, existing_rows, auto_fields, manual_fields)

    assert "manual_status" not in upserts[0]["auto_values"]
    assert upserts[0]["manual_values_on_insert"]["manual_status"] == "確認中"


def test_new_row_manual_fields_are_blank():
    projects = [{"project_id": "P2", "project_name": "new"}]
    auto_fields = ["project_id", "project_name"]
    manual_fields = ["manual_status", "memo"]
    upserts, _ = build_watch_upserts(projects, [], auto_fields, manual_fields)
    assert upserts[0]["manual_values_on_insert"] == {"manual_status": "", "memo": ""}


def test_history_rows_follow_schema_order():
    fields = ["changed_at", "project_id", "field_name", "run_id"]
    items = [{"project_id": "P1", "field_name": "status_auto", "changed_at": "t", "run_id": "r", "extra": "x"}]
    rows = build_history_rows(items, fields)
    assert list(rows[0].keys()) == fields


def test_raw_rows_follow_schema_order():
    fields = ["run_id", "project_id", "source_url"]
    projects = [{"project_id": "P1", "source_url": "u", "x": "y"}]
    rows = build_raw_rows(projects, fields, "run-1")
    assert list(rows[0].keys()) == fields
    assert rows[0]["run_id"] == "run-1"


def test_stop_on_header_mismatch():
    payload = {"projects": [{"project_id": "P1"}], "history": []}
    schema = {
        "watch_headers": ["project_id", "project_name", "manual_status"],
        "auto_fields": ["project_id", "project_name"],
        "manual_fields": ["manual_status"],
        "history_fields": ["changed_at"],
        "raw_fields": ["run_id"],
    }
    state = {
        "JICA_ODA_WATCH": {"headers": ["project_id", "name"], "rows": []},
        "JICA_ODA_HISTORY": {"headers": ["changed_at"], "rows": []},
        "JICA_ODA_RAW": {"headers": ["run_id"], "rows": []},
    }

    with pytest.raises(RuntimeError, match="ヘッダー不一致"):
        plan_updates(payload, state, schema)


def test_missing_project_id_row_is_skipped_with_warning():
    upserts, warnings = build_watch_upserts(
        [{"project_name": "no id"}], [], ["project_id", "project_name"], ["memo"]
    )
    assert upserts == []
    assert warnings


def test_dry_run_without_endpoint_or_state_file_succeeds(tmp_path):
    input_path = tmp_path / "projects.json"
    input_path.write_text(json.dumps({"projects": [{"project_id": "P1"}], "history": []}), encoding="utf-8")

    cmd = [sys.executable, "scripts/update_sheets.py", "--input", str(input_path), "--dry-run"]
    result = subprocess.run(cmd, cwd="/workspace/jica-oda-watch", capture_output=True, text=True)

    assert result.returncode == 0
    assert "dry-run without sheet state" in result.stdout


def test_column_letter_and_sheet_quote_helpers():
    assert column_letter(1) == "A"
    assert column_letter(26) == "Z"
    assert column_letter(27) == "AA"
    assert quote_sheet_name("A'B") == "'A''B'"


def test_rows_to_dicts_preserves_row_numbers_and_padding():
    rows = rows_to_dicts([["P1"], ["P2", "name"]], ["project_id", "project_name"], start_row_number=2)
    assert rows[0] == {"project_id": "P1", "project_name": "", "_row_number": 2}
    assert rows[1]["_row_number"] == 3


def test_dict_rows_to_values_uses_schema_order_and_blanks_missing_values():
    rows = [{"b": "B", "a": "A"}, {"a": "A2"}]
    assert dict_rows_to_values(rows, ["a", "b"]) == [["A", "B"], ["A2", ""]]


def test_apply_updates_updates_only_auto_columns_and_appends_rows():
    schema = {
        "watch_headers": ["project_id", "project_name", "status_auto", "memo"],
        "auto_fields": ["project_id", "project_name", "status_auto"],
        "manual_fields": ["memo"],
        "history_fields": ["changed_at", "project_id"],
        "raw_fields": ["run_id", "project_id"],
    }
    state = {
        WATCH_SHEET: {
            "headers": ["project_id", "project_name", "status_auto", "memo"],
            "rows": [{"project_id": "P1", "memo": "keep", "_row_number": 2}],
        },
        "JICA_ODA_HISTORY": {"headers": ["changed_at", "project_id"], "rows": []},
        RAW_SHEET: {"headers": ["run_id", "project_id"], "rows": []},
    }
    plan = {
        "watch_upserts": [
            {"project_id": "P1", "auto_values": {"project_name": "updated", "status_auto": "要確認"}, "manual_values_on_insert": {"memo": "keep"}},
            {"project_id": "P2", "auto_values": {"project_name": "new", "status_auto": "new"}, "manual_values_on_insert": {"memo": ""}},
        ],
        "history_appends": [{"changed_at": "t", "project_id": "P1"}],
        "raw_appends": [{"run_id": "r", "project_id": "P1"}],
    }

    service = Mock()
    values_api = service.spreadsheets.return_value.values.return_value
    values_api.batchUpdate.return_value.execute.return_value = {"totalUpdatedRows": 1}
    values_api.append.return_value.execute.return_value = {"updates": {"updatedRows": 1}}

    result = apply_updates(service, "sid", plan, state, schema)

    batch_body = values_api.batchUpdate.call_args.kwargs["body"]
    assert batch_body["data"] == [
        {"range": "'JICA_ODA_WATCH'!A2:C2", "values": [["P1", "updated", "要確認"]]}
    ]
    appended_values = [call.kwargs["body"]["values"] for call in values_api.append.call_args_list]
    assert [["P2", "new", "new", ""]] in appended_values
    assert [["t", "P1"]] in appended_values
    assert [["r", "P1"]] in appended_values
    assert result["watch_updated_rows"] == 1
