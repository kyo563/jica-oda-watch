from scripts.diff_records import merge_and_diff


DIFF_FIELDS = ["project_name", "status_auto"]


def test_merge_by_project_id_not_row_order():
    previous = [
        {"project_id": "A", "project_name": "A-old", "status_auto": "x"},
        {"project_id": "B", "project_name": "B-old", "status_auto": "x"},
    ]
    current = [
        {"project_id": "B", "project_name": "B-new", "status_auto": "y"},
        {"project_id": "A", "project_name": "A-old", "status_auto": "x"},
    ]

    merged, history = merge_and_diff(previous, current, DIFF_FIELDS)
    merged_map = {m["project_id"]: m for m in merged}

    assert merged_map["A"]["change_flag"] == "no_change"
    assert merged_map["B"]["change_flag"] == "updated"
    assert any(h["project_id"] == "B" for h in history)
