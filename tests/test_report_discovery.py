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
            },
            {
                "project_id": "pid-1",
                "project_name": "案件A",
                "notice_date": "2026年5月1日",
                "notice_url": "https://example.com",
                "parse_confidence": "low",
                "source_type": "jica_grant_notice",
                "evidence_text": "証跡",
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
    assert "parse_confidence全件low: はい" in report
    assert "detail_fetch_failed: 1" in report
