from pathlib import Path

from scripts.parsers.jica_discovery import (
    build_pdf_metadata_only_record,
    extract_notice_date_from_text,
    parse_detail,
    _should_reject_candidate,
)

FIXTURE_HTML = Path("tests/fixtures/jica/detail.html").read_text(encoding="utf-8")


def test_extract_notice_date_from_text_formats():
    assert extract_notice_date_from_text("2026年5月11日公示 ガーナ") == "2026-05-11"
    assert extract_notice_date_from_text("2026/05/11 公示") == "2026-05-11"
    assert extract_notice_date_from_text("2026-05-11 公示") == "2026-05-11"


def test_pdf_candidate_metadata_only_record():
    c = {
        "candidate_title": "2026年5月11日公示 ガーナ国 案件A",
        "candidate_url": "https://example.com/notice.pdf?download=1",
        "source_url": "https://example.com/list",
        "source_type": "jica_grant_notice",
        "candidate_kind": "pdf",
    }
    r = build_pdf_metadata_only_record(c, "2026-05-15T00:00:00+00:00")
    assert r["parse_confidence"] == "low"
    assert r["notice_date"] == "2026-05-11"
    assert "%PDF" not in r["raw_text"]


def test_parse_detail_falls_back_to_title_notice_date():
    c = {
        "candidate_title": "2026年4月8日公示 スリランカ国 案件",
        "candidate_url": "https://www.jica.go.jp/detail/1.html",
        "source_url": "https://www.jica.go.jp/list.html",
        "source_type": "jica_grant_notice",
    }
    r = parse_detail("<html><h1>案件</h1><p>本文のみ</p></html>", c, "2026-05-15T00:00:00+00:00")
    assert r["notice_date"] == "2026-04-08"


def test_reject_non_project_pages():
    yes = {
        "source_url": "https://www.jica.go.jp/activities/schemes/grant_aid/chotatsu/index.html",
        "candidate_url": "https://www.jica.go.jp/about/chotatsu/program",
        "candidate_title": "調達情報のご案内",
    }
    no = {
        "source_url": "https://www.jica.go.jp/activities/schemes/grant_aid/chotatsu/index.html",
        "candidate_url": "https://www.jica.go.jp/activities/schemes/grant_aid/chotatsu/2026/index.html",
        "candidate_title": "2026年5月11日公示 ガーナ国",
    }
    assert _should_reject_candidate(yes)[0] is True
    assert _should_reject_candidate(no)[0] is False
