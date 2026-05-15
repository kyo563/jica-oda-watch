import json
import subprocess
import sys


def test_legacy_watchlist_command_works(tmp_path):
    out = tmp_path / 'latest.json'
    r = subprocess.run([sys.executable, 'scripts/crawl_jica.py', '--watchlist', 'config/watchlist.example.csv', '--output', str(out)], capture_output=True, text=True)
    assert r.returncode == 0
    data = json.loads(out.read_text(encoding='utf-8'))
    assert isinstance(data, list)


def test_discover_empty_warning_no_network(monkeypatch):
    from scripts import crawl_jica

    sources = [{"source_type": "jica_grant_notice", "url": "https://example.com", "enabled": True}]
    scope = {"sources": ["jica_grant_notice"], "max_pages_per_source": 1, "max_detail_pages": 5, "request_interval_seconds": 1}

    monkeypatch.setattr(crawl_jica, 'extract_candidates', lambda *_: [])

    calls = []

    def fake_fetch(url):
        calls.append(url)
        return '<html></html>'

    sleeper_calls = []
    result = crawl_jica.discover_records(sources, scope, fetcher=fake_fetch, sleeper=lambda x: sleeper_calls.append(x))

    assert calls == ['https://example.com']
    assert result['records'] == []
    assert sleeper_calls == [1]
