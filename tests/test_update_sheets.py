import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.update_sheets import (
    build_history_rows,
    apply_plan,
    build_raw_rows,
    build_watch_upserts,
    plan_updates,
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
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)

    assert result.returncode == 0
    assert "dry-run without sheet state" in result.stdout


def test_raise_error_when_existing_watch_has_duplicate_project_id():
    projects = [{"project_id": "P1", "project_name": "new"}]
    existing_rows = [
        {"project_id": "P1", "memo": "a"},
        {"project_id": "P1", "memo": "b"},
    ]
    with pytest.raises(RuntimeError, match="JICA_ODA_WATCH に重複した project_id があります: P1"):
        build_watch_upserts(projects, existing_rows, ["project_id", "project_name"], ["memo"])


def test_raise_error_when_input_projects_have_duplicate_project_id():
    projects = [
        {"project_id": "P1", "project_name": "a"},
        {"project_id": "P1", "project_name": "b"},
    ]
    with pytest.raises(RuntimeError, match="入力projectsに重複した project_id があります: P1"):
        build_watch_upserts(projects, [], ["project_id", "project_name"], ["memo"])


class _DummyExec:
    def execute(self):
        return {}


class _DummyValues:
    def __init__(self):
        self.batch_update_calls = []
        self.append_calls = []

    def batchUpdate(self, **kwargs):
        self.batch_update_calls.append(kwargs)
        return _DummyExec()

    def append(self, **kwargs):
        self.append_calls.append(kwargs)
        return _DummyExec()


class _DummySpreadsheets:
    def __init__(self):
        self._values = _DummyValues()

    def values(self):
        return self._values


class _DummyService:
    def __init__(self):
        self._spreadsheets = _DummySpreadsheets()

    def spreadsheets(self):
        return self._spreadsheets


def test_apply_plan_updates_only_auto_fields_and_appends_in_schema_order():
    schema = {
        "watch_headers": ["project_id", "project_name", "status_auto", "manual_status", "memo"],
        "auto_fields": ["project_id", "project_name", "status_auto"],
        "manual_fields": ["manual_status", "memo"],
        "history_fields": ["changed_at", "project_id", "field_name"],
        "raw_fields": ["run_id", "project_id", "source_url"],
    }
    plan = {
        "watch_upserts": [
            {
                "project_id": "P1",
                "mode": "update",
                "row_number": 2,
                "auto_values": {"project_name": "A", "status_auto": "updated"},
                "manual_values_on_insert": {"manual_status": "keep", "memo": "keep"},
            },
            {
                "project_id": "P2",
                "mode": "append",
                "row_number": None,
                "auto_values": {"project_id": "P2", "project_name": "B", "status_auto": "new"},
                "manual_values_on_insert": {"manual_status": "", "memo": ""},
            },
        ],
        "history_appends": [{"changed_at": "t", "project_id": "P2", "field_name": "status_auto"}],
        "raw_appends": [{"run_id": "r", "project_id": "P2", "source_url": "u"}],
    }

    service = _DummyService()
    apply_plan(service, "sid", plan, schema)

    values = service.spreadsheets().values()
    update = values.batch_update_calls[0]["body"]["data"][0]
    assert update["range"] == "JICA_ODA_WATCH!B2"
    assert update["values"][0] == ["A", "updated"]

    watch_append = values.append_calls[0]
    assert watch_append["range"] == "JICA_ODA_WATCH!A:A"
    assert watch_append["body"]["values"][0] == ["P2", "B", "new", "", ""]

    history_append = values.append_calls[1]
    assert history_append["body"]["values"][0] == ["t", "P2", "status_auto"]

    raw_append = values.append_calls[2]
    assert raw_append["body"]["values"][0] == ["r", "P2", "u"]
