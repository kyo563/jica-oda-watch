import pytest

from scripts.update_sheets import build_watch_upserts, plan_updates


def test_manual_fields_never_overwritten():
    projects = [{"project_id": "P1", "project_name": "new", "status_auto": "updated"}]
    existing_rows = [{
        "project_id": "P1",
        "project_name": "old",
        "status_auto": "old",
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

    upserts = build_watch_upserts(projects, existing_rows, auto_fields, manual_fields)

    assert upserts[0]["project_name"] == "new"
    assert upserts[0]["manual_status"] == "確認中"
    assert upserts[0]["memo"] == "手入力メモ"


def test_stop_on_header_mismatch():
    payload = {"projects": [{"project_id": "P1"}], "history": []}
    schema = {
        "watch_headers": ["project_id", "project_name", "manual_status"],
        "auto_fields": ["project_id", "project_name"],
        "manual_fields": ["manual_status"],
        "history_fields": [],
        "raw_fields": [],
    }
    state = {"JICA_ODA_WATCH": {"headers": ["project_id", "name"], "rows": []}}

    with pytest.raises(RuntimeError, match="ヘッダー不一致"):
        plan_updates(payload, state, schema)
