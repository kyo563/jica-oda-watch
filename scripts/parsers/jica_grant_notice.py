from html.parser import HTMLParser
from urllib.parse import urljoin


class _NoticeHTMLParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.in_title = False
        self.title = ""
        self.links: list[dict] = []
        self._current_href = ""
        self._current_text = ""

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "a":
            self._current_href = attr_map.get("href", "").strip()
            self._current_text = ""

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "a" and self._current_href:
            text = self._current_text.strip()
            if text:
                self.links.append({"text": text, "url": urljoin(self.base_url, self._current_href)})
            self._current_href = ""
            self._current_text = ""

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self._current_href:
            self._current_text += data


def parse_jica_grant_notice(html: str, base_url: str) -> dict:
    parser = _NoticeHTMLParser(base_url)
    parser.feed(html)
    return {
        "page_title": parser.title.strip(),
        "links": parser.links,
    }
