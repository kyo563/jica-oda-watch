from scripts.report_discovery import build_report


def test_build_report_contains_quality_warnings():
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
    assert "records件数: 2" in report
    assert "project_id重複件数: 1" in report
    assert "notice_url欠落件数: 1" in report
    assert "evidence_text欠落件数: 1" in report
    assert "notice_date欠落件数: 1" in report
    assert "raw_text欠落/短文件数(<40): 1" in report
    assert "parse_confidence全件low: はい" in report
    assert "parse_confidence low率: 100%" in report
    assert "## pq_required別件数" in report
    assert "- 要確認: 1" in report
    assert "## 重複project_id詳細" in report
    assert "## high-risk records" in report
    assert "detail_fetch_failed: 1" in report


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
