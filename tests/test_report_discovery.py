from scripts.report_discovery import build_report


def test_build_report_contains_quality_warnings_and_high_risk_note():
    obj = {
        "records": [
            {
                "project_id": "pid-1",
                "project_name": "要確認",
                "notice_date": "",
                "notice_url": "",
                "parse_confidence": "low",
                "source_type": "jica_grant_notice",
                "evidence_text": "",
                "pq_required": "要確認",
                "raw_text": "短文",
            },
            {
                "project_id": "pid-1",
                "project_name": "案件A",
                "notice_date": "2026年5月1日",
                "notice_url": "https://example.com",
                "parse_confidence": "low",
                "source_type": "jica_grant_notice",
                "evidence_text": "証跡",
                "pq_required": "あり",
                "raw_text": "入札公告テキスト" * 10,
            },
        ],
        "errors": [{"reason": "detail_fetch_failed"}],
        "meta": {},
    }
    report = build_report(obj)
    assert "review_status: BLOCK" in report
    assert "project_id重複件数: 1" in report
    assert "project_id_missing件数: 0" in report
    assert "high-risk records総数:" in report
    assert "## high-risk records" in report
    assert "※表示は先頭20件まで" in report


def test_build_report_blocks_when_project_id_missing_exists():
    obj = {
        "records": [{"project_id": "", "parse_confidence": "medium", "project_name": "案件", "notice_url": "u", "notice_date": "d", "evidence_text": "e", "raw_text": "x" * 50}],
        "errors": [],
        "meta": {},
    }
    report = build_report(obj)
    assert "project_id_missing件数: 1" in report
    assert "review_status: BLOCK" in report


def test_build_report_blocks_when_errors_are_greater_or_equal_to_records():
    obj = {
        "records": [{"project_id": "pid-1", "parse_confidence": "medium", "project_name": "案件", "notice_url": "u", "notice_date": "d", "evidence_text": "e", "raw_text": "x" * 50}],
        "errors": [{"reason": "fetch_failed"}],
        "meta": {},
    }
    report = build_report(obj)
    assert "errors件数: 1" in report
    assert "review_status: BLOCK" in report


def test_build_report_empty_records_with_errors():
    obj = {
        "records": [],
        "errors": [{"reason": "fetch_failed"}, {"reason": "fetch_failed"}],
        "meta": {},
    }
    report = build_report(obj)
    assert "records件数: 0" in report
    assert "errors件数: 2" in report
    assert "review_status: BLOCK" in report
    assert "fetch_failed: 2" in report
