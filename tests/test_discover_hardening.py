from scripts.crawl_jica import discover_records
from scripts.http_client import HTTPFetchError


def test_pdf_candidate_skips_detail_fetch_and_priority(monkeypatch):
    sources = [{"source_type": "jica_grant_notice", "url": "https://example.com/list", "enabled": True}]
    scope = {"sources": ["jica_grant_notice"], "max_pages_per_source": 1, "max_detail_pages": 1, "request_interval_seconds": 0}

    monkeypatch.setattr(
        "scripts.crawl_jica.extract_candidates_with_diagnostics",
        lambda *_: ([
            {"source_type": "jica_grant_notice", "source_url": "https://example.com/list", "candidate_url": "https://example.com/nav", "candidate_title": "調達情報"},
            {"source_type": "jica_grant_notice", "source_url": "https://example.com/list", "candidate_url": "https://example.com/notice.pdf#page=1", "candidate_title": "2026年5月11日公示", "candidate_kind": "pdf"},
        ], {"anchors_seen": 2, "candidates_found": 2, "sample_links": [], "rejected_link_samples": []}),
    )

    def fake_fetch(url):
        if "notice.pdf" in url:
            raise AssertionError("pdf detail fetch should not happen")
        return "<html>list</html>"

    out = discover_records(sources, scope, fetcher=fake_fetch, sleeper=lambda _: None)
    assert len(out["records"]) == 1
    assert out["records"][0]["status_detail"] == "pdf_metadata_only"


def test_candidate_dedupe_and_rejected_warning(monkeypatch):
    sources = [{"source_type": "jica_grant_notice", "url": "https://example.com/list", "enabled": True}]
    scope = {"sources": ["jica_grant_notice"], "max_pages_per_source": 1, "max_detail_pages": 5, "request_interval_seconds": 0}
    monkeypatch.setattr(
        "scripts.crawl_jica.extract_candidates_with_diagnostics",
        lambda *_: ([
            {"source_type": "jica_grant_notice", "source_url": "https://example.com/list", "candidate_url": "https://example.com/about/chotatsu/program", "candidate_title": "調達情報のご案内"},
            {"source_type": "jica_grant_notice", "source_url": "https://example.com/list", "candidate_url": "https://example.com/detail"},
            {"source_type": "jica_grant_notice", "source_url": "https://example.com/list", "candidate_url": "https://example.com/detail/"},
        ], {"anchors_seen": 3, "candidates_found": 3, "sample_links": [], "rejected_link_samples": []}),
    )
    out = discover_records(sources, scope, fetcher=lambda _: "<html><h1>2026年5月11日公示 入札</h1><p>公示</p></html>", sleeper=lambda _: None)
    assert any(e.get("reason") == "candidate_rejected" for e in out["errors"])
    assert any(e.get("reason") == "candidate_deduped" for e in out["errors"])


def test_detail_fetch_failed_still_works(monkeypatch):
    sources = [{"source_type": "jica_grant_notice", "url": "https://example.com/list", "enabled": True}]
    scope = {"sources": ["jica_grant_notice"], "max_pages_per_source": 1, "max_detail_pages": 5, "request_interval_seconds": 0}
    monkeypatch.setattr(
        "scripts.crawl_jica.extract_candidates_with_diagnostics",
        lambda *_: ([{
            "source_type": "jica_grant_notice",
            "source_url": "https://example.com/list",
            "candidate_url": "https://example.com/detail/1",
            "candidate_title": "入札案件A",
        }], {"anchors_seen": 1, "candidates_found": 1, "sample_links": [], "rejected_link_samples": []}),
    )

    def fake_fetch(url):
        if "detail" in url:
            raise HTTPFetchError("detail ng", url=url, status_code=500, exception_type="HTTPError")
        return "<html>list</html>"

    out = discover_records(sources, scope, fetcher=fake_fetch, sleeper=lambda _: None)
    assert next(e for e in out["errors"] if e.get("reason") == "detail_fetch_failed")
