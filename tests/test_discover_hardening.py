import json

import pytest

from scripts.crawl_jica import crawl_sources, discover_records
from scripts.http_client import HTTPFetchError
from scripts.validate_config import validate_crawl_scope
from scripts.diff_records import load_records


def test_discover_list_fetch_failure_has_diagnostics():
    sources = [{"source_type": "jica_grant_notice", "url": "https://example.com/list", "enabled": True}]
    scope = {"sources": ["jica_grant_notice"], "max_pages_per_source": 1, "max_detail_pages": 1, "request_interval_seconds": 2}

    def fake_fetch(_):
        raise HTTPFetchError("HTTP取得失敗", url="https://example.com/list", status_code=403, exception_type="HTTPError")

    out = discover_records(sources, scope, fetcher=fake_fetch, sleeper=lambda _: None)
    err = next(e for e in out["errors"] if e.get("reason") == "list_fetch_failed")
    assert err["status_code"] == 403
    assert err["exception_type"] == "HTTPError"
    assert err["error_message"]
    assert err["fetched_at"]


def test_discover_detail_fetch_failure_is_error_not_record(monkeypatch):
    sources = [{"source_type": "jica_grant_notice", "url": "https://example.com/list", "enabled": True}]
    scope = {"sources": ["jica_grant_notice"], "max_pages_per_source": 1, "max_detail_pages": 5, "request_interval_seconds": 2}

    monkeypatch.setattr('scripts.crawl_jica.extract_candidates', lambda *_: [{
        "source_type": "jica_grant_notice",
        "source_url": "https://example.com/list",
        "candidate_url": "https://example.com/detail/1",
        "candidate_title": "入札案件A",
    }])

    def fake_fetch(url):
        if 'detail' in url:
            raise HTTPFetchError("detail ng", url=url, status_code=500, exception_type="HTTPError")
        return '<html>list</html>'

    sleeps = []
    out = discover_records(sources, scope, fetcher=fake_fetch, sleeper=lambda x: sleeps.append(x))
    assert out['records'] == []
    err = next(e for e in out['errors'] if e.get('reason') == 'detail_fetch_failed')
    assert err['status_code'] == 500
    assert err['exception_type'] == 'HTTPError'
    assert err['error_message']
    assert err['fetched_at']
    assert sleeps == [2]


def test_discover_request_interval_applied_between_requests(monkeypatch):
    sources = [{"source_type": "jica_grant_notice", "url": "https://example.com/list", "enabled": True}]
    scope = {"sources": ["jica_grant_notice"], "max_pages_per_source": 1, "max_detail_pages": 2, "request_interval_seconds": 3}

    monkeypatch.setattr('scripts.crawl_jica.extract_candidates', lambda *_: [
        {"source_type": "jica_grant_notice", "source_url": "https://example.com/list", "candidate_url": "https://example.com/detail/1", "candidate_title": "入札案件A"},
        {"source_type": "jica_grant_notice", "source_url": "https://example.com/list", "candidate_url": "https://example.com/detail/2", "candidate_title": "入札案件B"},
    ])

    sleeps = []
    out = discover_records(sources, scope, fetcher=lambda _: '<html></html>', sleeper=lambda x: sleeps.append(x))
    assert len(out['records']) == 2
    assert sleeps == [3, 3, 3]


def test_watchlist_mode_still_works_with_http_fetch_error(monkeypatch):
    projects = [{"project_id": "P1", "country": "JP", "project_name": "案件", "keywords": "k"}]
    sources = [{"source_type": "jica_grant_notice", "url": "https://example.com/list", "enabled": True}]
    monkeypatch.setattr('scripts.crawl_jica.fetch_text', lambda *_: (_ for _ in ()).throw(HTTPFetchError("ng")))
    out = crawl_sources(projects, sources)
    assert len(out) == 1
    assert "HTTP取得失敗" in out[0]["status_detail"]


def test_load_records_accepts_discover_shape(tmp_path):
    p = tmp_path / 'd.json'
    p.write_text(json.dumps({"records": [{"project_id": "P1"}], "errors": [], "meta": {}}), encoding='utf-8')
    assert load_records(str(p)) == [{"project_id": "P1"}]


def test_validate_crawl_scope_upper_bound(tmp_path):
    p = tmp_path / 'crawl_scope.yml'
    p.write_text('''scope:\n  schemes: [grant_aid]\n  sources: [jica_grant_notice]\n  max_pages_per_source: 31\n  request_interval_seconds: 1\n  max_detail_pages: 20\n''', encoding='utf-8')
    with pytest.raises(ValueError, match='max_pages_per_source'):
        validate_crawl_scope(str(p))
