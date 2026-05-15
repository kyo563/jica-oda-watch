from scripts.crawl_jica import validate_discovered_records

def test_duplicate_project_id_detected():
    rec={"project_id":"x","project_name":"a","source_url":"u","parser_name":"p","parser_version":"1"}
    valid, errors = validate_discovered_records([rec, rec.copy()])
    assert len(valid)==1
    assert any('duplicate_project_id' in e['reason'] for e in errors)
