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


def test_detect_pq_required_patterns():
    assert _detect_pq_required("PQを実施します。申請を受け付けます。") == "あり"
    assert _detect_pq_required("PQは不要です。") == "なし"
    assert _detect_pq_required("PQの説明ページです") == "要確認"
    assert _detect_pq_required("事前資格審査は実施しません") == "なし"


def test_extract_evidence_returns_empty_without_keyword():
    assert _extract_evidence("これは一般的なお知らせです。募集情報はありません。") == ""


def test_parse_confidence_medium_with_heading_body_evidence():
    c = {
        "candidate_title": "候補タイトル",
        "candidate_url": "https://www.jica.go.jp/detail/3.html",
        "source_url": "https://www.jica.go.jp/list.html",
        "source_type": "jica_grant_notice",
    }
    html = """
    <html><head><title>無償資金協力 調達公告</title></head>
    <body><h1>無償資金協力 調達公告</h1><p>公示日: 2026年5月1日</p>
    <p>本件は入札公告として実施します。参加資格と提出手続を示します。</p></body></html>
    """
    r = parse_detail(html, c, "2026-05-15T00:00:00+00:00")
    assert r["parse_confidence"] == "medium"
