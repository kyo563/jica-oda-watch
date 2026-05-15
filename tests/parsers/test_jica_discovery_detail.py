from pathlib import Path
from scripts.parsers.jica_discovery import parse_detail

def test_parse_detail_minimum_fields():
    html = Path('tests/fixtures/jica/detail.html').read_text(encoding='utf-8')
    c = {'candidate_title':'無償資金協力 入札案件A','candidate_url':'https://www.jica.go.jp/detail/1.html?x=1#top','source_url':'https://www.jica.go.jp/list.html','source_type':'jica_grant_notice'}
    r = parse_detail(html, c, '2026-05-15T00:00:00+00:00')
    assert r['project_id']
    assert r['project_name']
    assert r['source_url']
    assert r['parser_name']
    assert r['parser_version']
