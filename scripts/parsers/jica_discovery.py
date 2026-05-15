from html.parser import HTMLParser
from urllib.parse import urljoin

try:
    from scripts.utils_project_id import canonicalize_url, generate_project_id
except ModuleNotFoundError:
    from utils_project_id import canonicalize_url, generate_project_id

PARSER_NAME = "jica_discovery"
PARSER_VERSION = "0.1"


class _CandidateParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.candidates = []
        self._href = ""
        self._text = ""

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        self._href = dict(attrs).get("href", "").strip()
        self._text = ""

    def handle_data(self, data):
        if self._href:
            self._text += data

    def handle_endtag(self, tag):
        if tag != "a" or not self._href:
            return
        title = self._text.strip()
        url = urljoin(self.base_url, self._href)
        if title and ("調達" in title or "入札" in title or "案件" in title):
            self.candidates.append({
                "source_type": "jica_grant_notice",
                "source_url": self.base_url,
                "candidate_url": url,
                "candidate_title": title,
                "country_hint": "",
                "scheme_hint": "無償資金協力",
                "notice_date_hint": "",
                "evidence_text": title,
            })
        self._href = ""
        self._text = ""


def extract_candidates(html: str, source_url: str, source_type: str) -> list[dict]:
    parser = _CandidateParser(source_url)
    parser.feed(html)
    for c in parser.candidates:
        c["source_type"] = source_type
    return parser.candidates


def parse_detail(html: str, candidate: dict, fetched_at: str) -> dict:
    # NOTE: 現段階ではdetail HTMLの本格解析は未実装。
    # candidate metadataを使った最小限レコード生成のみ行う。
    _ = html
    title = (candidate.get("candidate_title") or "").strip()
    notice_url = canonicalize_url(candidate.get("candidate_url") or "")
    project_id = generate_project_id("", title, "無償資金協力", notice_url)
    return {
        "project_id": project_id,
        "country": candidate.get("country_hint", ""),
        "project_name": title or "要確認",
        "sector": "",
        "scheme": "無償資金協力",
        "ga_date": "",
        "pq_required": "要確認",
        "notice_date": candidate.get("notice_date_hint", ""),
        "notice_media": "JICA",
        "notice_url": notice_url,
        "result_url": "",
        "oda_url": candidate.get("source_url", ""),
        "status_auto": "要確認",
        "status_detail": "discovery収集結果",
        "source_type": candidate.get("source_type", "jica_grant_notice"),
        "source_url": candidate.get("source_url", ""),
        "raw_text": "",
        "evidence_text": candidate.get("evidence_text", ""),
        "parser_name": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "parse_confidence": "low",
        "fetched_at": fetched_at,
        "last_checked": fetched_at,
        "change_flag": "new",
    }
