import pytest

from scripts.diff_records import merge_and_diff


DIFF_FIELDS = ["project_name", "status_auto"]


def test_new_record_adds_history():
    previous = []
    current = [{"project_id": "N1", "project_name": "New"}]

    merged, history = merge_and_diff(previous, current, DIFF_FIELDS)

    assert merged[0]["change_flag"] == "new"
    assert len(history) == 1
    assert history[0]["field_name"] == "__record__"
    assert history[0]["change_summary"] == "新規案件を検出"


def test_missing_record_adds_history():
    previous = [{"project_id": "M1", "project_name": "Old"}]
    current = []

    merged, history = merge_and_diff(previous, current, DIFF_FIELDS)

    assert merged[0]["change_flag"] == "missing"
    assert len(history) == 1
    assert history[0]["field_name"] == "__record__"
    assert history[0]["change_summary"] == "前回存在した案件が今回取得結果に存在しません"


def test_duplicate_project_id_in_current_raises_error():
    previous = []
    current = [{"project_id": "D1"}, {"project_id": "D1"}]

    with pytest.raises(ValueError, match="current: project_id重複"):
        merge_and_diff(previous, current, DIFF_FIELDS)


def test_missing_project_id_raises_error():
    previous = []
    current = [{"project_id": ""}]

    with pytest.raises(ValueError, match="current: project_id欠落"):
        merge_and_diff(previous, current, DIFF_FIELDS)
