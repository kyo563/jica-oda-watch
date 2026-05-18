from scripts.parsers.jica_discovery import (
    build_pdf_metadata_only_record,
    dedupe_and_prioritize_candidates,
    extract_notice_date_from_text,
    parse_detail,
    _should_reject_candidate,
)


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


def test_parse_detail_confidence_low_without_date():
    c = {
        "candidate_title": "案件",
        "candidate_url": "https://www.jica.go.jp/detail/1.html",
        "source_url": "https://www.jica.go.jp/list.html",
        "source_type": "jica_grant_notice",
    }
    r = parse_detail("<html><h1>案件</h1><p>本文 公示 証跡あり</p></html>", c, "2026-05-15T00:00:00+00:00")
    assert r["parse_confidence"] == "low"


def test_reject_non_project_pages_and_title():
    for url in [
        "https://www.jica.go.jp/forresearchers",
        "https://www.jica.go.jp/about/announce/notice",
        "https://www.jica.go.jp/about/announce/manual",
        "https://www.jica.go.jp/about/disc/settle",
    ]:
        assert _should_reject_candidate({"source_url": "https://x/list", "candidate_url": url, "candidate_title": "x"})[0] is True
    assert _should_reject_candidate({"source_url": "https://x/list", "candidate_url": "https://x/a", "candidate_title": "Japanese"})[0] is True


def test_dedupe_and_priority():
    cands = [
        {"candidate_url": "https://a/detail", "candidate_title": "一般", "source_url": "https://a/list"},
        {"candidate_url": "https://a/detail/", "candidate_title": "一般重複", "source_url": "https://a/list"},
        {"candidate_url": "https://a/notice.pdf#page=1", "candidate_title": "2026年5月11日公示", "source_url": "https://a/list"},
        {"candidate_url": "https://a/list", "candidate_title": "same as source", "source_url": "https://a/list"},
    ]
    out, ded = dedupe_and_prioritize_candidates(cands, 10)
    assert ded >= 1
    assert out[0]["candidate_url"].endswith(".pdf")
