from pathlib import Path

from scripts.parsers.jica_discovery import (
    _detect_pq_required,
    _extract_evidence,
    extract_candidates,
    extract_candidates_with_diagnostics,
    parse_detail,
)


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


def test_parse_confidence_low_when_pdf_candidate():
    c = {
        "candidate_title": "入札公告PDF",
        "candidate_url": "https://www.jica.go.jp/files/x.pdf",
        "source_url": "https://www.jica.go.jp/list.html",
        "source_type": "jica_grant_notice",
        "candidate_kind": "pdf",
    }
    r = parse_detail(FIXTURE_HTML, c, "2026-05-15T00:00:00+00:00")
    assert r["parse_confidence"] == "low"


def test_candidate_detection_keywords_and_href_and_diagnostics():
    html = """
    <a href='/a1.html'>公示</a>
    <a href='/a2.html'>公告</a>
    <a href='/a3.html'>契約</a>
    <a href='/a4.html'>参加意思確認</a>
    <a href='/a5.html'>参加資格</a>
    <a href='/a6.html'>PQ</a>
    <a href='/a7.html'>ＰＱ</a>
    <a href='/chotatsu/list.html'>無関係</a>
    <a href='/procurement/list.html'>無関係2</a>
    <a href='/bid/list.html'>無関係3</a>
    <a href='/keiyaku/list.html'>無関係4</a>
    <a href='/docs/notice.pdf'>資料</a>
    <a href='/about.html'>トップ</a>
    """
    cs, d = extract_candidates_with_diagnostics(html, "https://example.com/list", "jica_grant_notice")
    titles = [c["candidate_title"] for c in cs]
    assert "公示" in titles and "公告" in titles and "契約" in titles
    assert "参加意思確認" in titles and "参加資格" in titles
    assert "PQ" in titles and "ＰＱ" in titles
    assert any("chotatsu" in c["candidate_url"] for c in cs)
    assert any("procurement" in c["candidate_url"] for c in cs)
    assert any("/bid/" in c["candidate_url"] for c in cs)
    assert any("keiyaku" in c["candidate_url"] for c in cs)
    assert any(c.get("candidate_kind") == "pdf" for c in cs)
    assert all("about.html" not in c["candidate_url"] for c in cs)
    assert d["anchors_seen"] == 13
    assert d["sample_links"]
    assert d["rejected_link_samples"]
    assert len(d["sample_links"]) <= 10
    assert len(d["rejected_link_samples"]) <= 20
    assert extract_candidates(html, "https://example.com/list", "jica_grant_notice")


def test_detect_pq_required_conservative_patterns():
    assert _detect_pq_required("PQとは入札参加資格を確認する制度です") == "要確認"
    assert _detect_pq_required("PQは不要です") == "なし"
    assert _detect_pq_required("事前資格審査は実施無しです") == "なし"
    assert _detect_pq_required("事前資格審査の申請を受け付けます") == "あり"


def test_extract_evidence_returns_empty_without_keyword():
    assert _extract_evidence("これは一般的なお知らせです。募集情報はありません。") == ""
