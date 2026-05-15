from pathlib import Path

from scripts.parsers.jica_discovery import _detect_pq_required, _extract_evidence, parse_detail


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


def test_parse_confidence_low_when_only_musho_phrase_in_detail():
    c = {
        "candidate_title": "無償資金協力 入札案件A",
        "candidate_url": "https://www.jica.go.jp/detail/2.html",
        "source_url": "https://www.jica.go.jp/list.html",
        "source_type": "jica_grant_notice",
        "evidence_text": "入札案件A",
    }
    html = "<html><body><h1>無償資金協力</h1><p>無償資金協力の一般説明です。" + ("本文" * 30) + "</p></body></html>"
    r = parse_detail(html, c, "2026-05-15T00:00:00+00:00")
    assert r["parse_confidence"] == "low"
    assert r["evidence_text"] == "入札案件A"


def test_parse_confidence_low_when_candidate_has_bid_but_detail_has_no_evidence():
    c = {
        "candidate_title": "入札案件B",
        "candidate_url": "https://www.jica.go.jp/detail/22.html",
        "source_url": "https://www.jica.go.jp/list.html",
        "source_type": "jica_grant_notice",
        "evidence_text": "入札案件B",
    }
    html = "<html><body><h1>案件B</h1><p>お知らせです。" + ("説明" * 40) + "</p></body></html>"
    r = parse_detail(html, c, "2026-05-15T00:00:00+00:00")
    assert r["parse_confidence"] == "low"


def test_detect_pq_required_conservative_patterns():
    assert _detect_pq_required("PQとは入札参加資格を確認する制度です") == "要確認"
    assert _detect_pq_required("PQは不要です") == "なし"
    assert _detect_pq_required("事前資格審査は実施無しです") == "なし"
    assert _detect_pq_required("事前資格審査の申請を受け付けます") == "あり"


def test_extract_evidence_returns_empty_without_keyword():
    assert _extract_evidence("これは一般的なお知らせです。募集情報はありません。") == ""
