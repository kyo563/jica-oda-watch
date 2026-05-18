from scripts.report_discovery import build_report


def test_report_shows_rejected_and_pdf_metadata_only_counts():
    obj = {
        "records": [
            {
                "project_id": "pid-1",
                "project_name": "2026年5月11日公示 ガーナ国",
                "notice_date": "2026-05-11",
                "notice_url": "https://example.com/n.pdf",
                "parse_confidence": "low",
                "source_type": "jica_grant_notice",
                "evidence_text": "証跡",
                "pq_required": "要確認",
                "raw_text": "title + url",
                "status_detail": "pdf_metadata_only",
            },
        ],
        "errors": [
            {"reason": "candidate_rejected", "reject_reason": "non_project_navigation_page"},
            {"reason": "candidate_rejected", "reject_reason": "non_project_navigation_page"},
        ],
        "meta": {"sources_checked": 1, "list_fetch_success": 1, "anchors_seen": 10, "candidates_found": 3},
    }
    report = build_report(obj)
    assert "candidate_rejected: 2" in report
    assert "pdf_metadata_only件数: 1" in report
    assert "non_project_navigation_page: 2" in report
    assert "notice_date欠落件数: 0" in report
    assert "review_status: BLOCK" in report
