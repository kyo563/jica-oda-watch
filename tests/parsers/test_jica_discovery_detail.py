from pathlib import Path

from scripts.parsers.jica_discovery import parse_detail


FIXTURE_HTML = Path("tests/fixtures/jica/detail.html").read_text(encoding="utf-8")


def test_parse_detail_extracts_heading_date_text_and_pq():
    c = {
        "candidate_title": "候補タイトル",
        "candidate_url": "https://www.jica.go.jp/detail/1.html?x=1#top",
        "source_url": "https://www.jica.go.jp/list.html",
        "source_type": "jica_grant_notice",
    }
    r = parse_detail(FIXTURE_HTML, c, "2026-05-15T00:00:00+00:00")
    assert r["project_id"]
    assert r["project_name"].startswith("無償資金協力")
    assert r["notice_date"] == "2026年5月1日"
    assert r["notice_url"] == "https://www.jica.go.jp/detail/1.html"
    assert r["raw_text"]
    assert r["evidence_text"]
    assert r["pq_required"] == "あり"
    assert r["parse_confidence"] == "medium"
    assert r["country"] == ""
    assert r["sector"] == ""
    assert r["ga_date"] == ""


def test_parse_detail_low_when_body_is_insufficient():
    c = {
        "candidate_title": "無償資金協力 入札案件A",
        "candidate_url": "https://www.jica.go.jp/detail/2.html",
        "source_url": "https://www.jica.go.jp/list.html",
        "source_type": "jica_grant_notice",
    }
    r = parse_detail("<html><body><h1>短文</h1></body></html>", c, "2026-05-15T00:00:00+00:00")
    assert r["parse_confidence"] == "low"
    assert r["pq_required"] == "要確認"
