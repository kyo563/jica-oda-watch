from scripts.crawl_jica import discover_records
from scripts.http_client import HTTPFetchError


def test_pdf_candidate_skips_detail_fetch(monkeypatch):
    sources = [{"source_type": "jica_grant_notice", "url": "https://example.com/list", "enabled": True}]
    scope = {"sources": ["jica_grant_notice"], "max_pages_per_source": 1, "max_detail_pages": 5, "request_interval_seconds": 0}

    monkeypatch.setattr(
        "scripts.crawl_jica.extract_candidates_with_diagnostics",
        lambda *_: ([{
            "source_type": "jica_grant_notice",
            "source_url": "https://example.com/list",
            "candidate_url": "https://example.com/notice.pdf#page=1",
            "candidate_title": "2026年5月11日公示 ガーナ国",
            "candidate_kind": "pdf",
        }], {"anchors_seen": 1, "candidates_found": 1, "sample_links": [], "rejected_link_samples": []}),
    )

    def fake_fetch(url):
        if "notice.pdf" in url:
            raise AssertionError("pdf detail fetch should not happen")
        return "<html>list</html>"

    out = discover_records(sources, scope, fetcher=fake_fetch, sleeper=lambda _: None)
    assert len(out["records"]) == 1
    assert out["records"][0]["status_detail"] == "pdf_metadata_only"


def test_candidate_rejected_warning(monkeypatch):
    sources = [{"source_type": "jica_grant_notice", "url": "https://example.com/list", "enabled": True}]
    scope = {"sources": ["jica_grant_notice"], "max_pages_per_source": 1, "max_detail_pages": 5, "request_interval_seconds": 0}
    monkeypatch.setattr(
        "scripts.crawl_jica.extract_candidates_with_diagnostics",
        lambda *_: ([{
            "source_type": "jica_grant_notice",
            "source_url": "https://example.com/list",
            "candidate_url": "https://example.com/about/chotatsu/program",
            "candidate_title": "調達情報のご案内",
        }], {"anchors_seen": 1, "candidates_found": 1, "sample_links": [], "rejected_link_samples": []}),
    )
    out = discover_records(sources, scope, fetcher=lambda _: "<html>list</html>", sleeper=lambda _: None)
    assert out["records"] == []
    warn = next(e for e in out["errors"] if e.get("reason") == "candidate_rejected")
    assert warn["reject_reason"] == "non_project_navigation_page"


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
