from pathlib import Path
from scripts.parsers.jica_discovery import extract_candidates

def test_extract_candidates_from_fixture():
    html = Path('tests/fixtures/jica/list.html').read_text(encoding='utf-8')
    items = extract_candidates(html, 'https://www.jica.go.jp/activities/schemes/grant_aid/chotatsu/index.html', 'jica_grant_notice')
    assert len(items) == 2
    assert items[0]['candidate_url']
    assert items[0]['candidate_title']
