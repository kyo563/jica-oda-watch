from scripts.diff_records import merge_and_diff


DIFF_FIELDS = ["project_name", "status_auto"]


def test_manual_fields_are_preserved():
    previous = [{
        "project_id": "P1",
        "project_name": "A",
        "status_auto": "old",
        "memo": "手入力メモ",
        "manual_status": "確認中",
    }]
    current = [{
        "project_id": "P1",
        "project_name": "A",
        "status_auto": "new",
        "memo": "上書きされるべきでない",
    }]

    merged, _ = merge_and_diff(previous, current, DIFF_FIELDS)
    row = merged[0]
    assert row["memo"] == "手入力メモ"
    assert row["manual_status"] == "確認中"
    assert row["change_flag"] == "updated"
