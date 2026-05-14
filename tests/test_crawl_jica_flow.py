from scripts.crawl_jica import crawl_sources


def test_crawl_sources_keeps_stub_style_output_for_watchlist(monkeypatch):
    projects = [
        {"project_id": "P1", "country": "JP", "project_name": "案件1", "keywords": "abc"},
    ]
    sources = [{"source_type": "jica_grant_notice", "url": "https://example.com", "enabled": True}]

    monkeypatch.setattr("scripts.crawl_jica.fetch_text", lambda _: "<html><title>X</title></html>")
    monkeypatch.setattr("scripts.crawl_jica.parse_jica_grant_notice", lambda html, base_url: {"page_title": "X", "links": []})

    records = crawl_sources(projects, sources)
    assert len(records) == 1
    assert records[0]["project_id"] == "P1"
    assert records[0]["status_auto"] == "要確認"
    assert "要確認" in records[0]["status_detail"]
