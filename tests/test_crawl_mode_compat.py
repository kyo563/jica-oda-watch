import json, subprocess, sys

def test_legacy_watchlist_command_works(tmp_path):
    out=tmp_path/'latest.json'
    r=subprocess.run([sys.executable,'scripts/crawl_jica.py','--watchlist','config/watchlist.example.csv','--output',str(out)],capture_output=True,text=True)
    assert r.returncode==0
    data=json.loads(out.read_text(encoding='utf-8'))
    assert isinstance(data,list)

def test_discover_empty_warning(monkeypatch, tmp_path):
    from scripts import crawl_jica
    monkeypatch.setattr(crawl_jica,'fetch_text',lambda _: '<html><body>none</body></html>')
    out=tmp_path/'d.json'
    r=subprocess.run([sys.executable,'scripts/crawl_jica.py','--mode','discover','--output',str(out)],capture_output=True,text=True)
    assert r.returncode==0
