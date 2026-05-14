from scripts.parsers.jica_grant_notice import parse_jica_grant_notice


def test_parse_jica_grant_notice_extracts_title_and_links():
    html = """
    <html>
      <head><title>調達情報一覧</title></head>
      <body>
        <a href="/notice/1.html">案件A</a>
        <a href="https://example.org/b">案件B</a>
      </body>
    </html>
    """

    result = parse_jica_grant_notice(html, "https://www.jica.go.jp/activities/schemes/grant_aid/chotatsu/index.html")

    assert result["page_title"] == "調達情報一覧"
    assert len(result["links"]) >= 2
    assert result["links"][0]["url"].startswith("https://www.jica.go.jp/")
