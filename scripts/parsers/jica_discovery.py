from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urljoin

try:
    from scripts.utils_project_id import canonicalize_url, generate_project_id
except ModuleNotFoundError:
    from utils_project_id import canonicalize_url, generate_project_id

PARSER_NAME = "jica_discovery"
PARSER_VERSION = "0.1"
RAW_TEXT_LIMIT = 1200
EVIDENCE_LIMIT = 220


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


class _DetailTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.h1_texts = []
        self.h2_texts = []
        self.text_parts = []
        self._tag_stack = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)
        if tag in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if self._tag_stack:
            self._tag_stack.pop()
        if tag in {"script", "style"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        txt = _normalize_text(data)
        if not txt:
            return
        self.text_parts.append(txt)
        current = self._tag_stack[-1] if self._tag_stack else ""
        if current == "title":
            self.title = (self.title + " " + txt).strip()
        elif current == "h1":
            self.h1_texts.append(txt)
        elif current == "h2":
            self.h2_texts.append(txt)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text or "")).strip()


def _truncate(text: str, limit: int) -> str:
    t = _normalize_text(text)
    if len(t) <= limit:
        return t
    return t[: limit - 1].rstrip() + "…"


def _extract_notice_date(text: str) -> str:
    if not text:
        return ""
    patterns = [
        r"(20\d{2})[./年\-](\d{1,2})[./月\-](\d{1,2})日?",
        r"(令和\d{1,2})年\s*(\d{1,2})月\s*(\d{1,2})日",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0)
    return ""


def _extract_evidence(text: str) -> str:
    if not text:
        return ""
    keys = ["公告", "公示", "入札", "調達", "事前資格審査", "PQ", "無償資金協力"]
    for key in keys:
        idx = text.find(key)
        if idx >= 0:
            start = max(0, idx - 60)
            end = min(len(text), idx + 140)
            return _truncate(text[start:end], EVIDENCE_LIMIT)
    return _truncate(text, EVIDENCE_LIMIT)


def _detect_pq_required(text: str) -> str:
    if not text:
        return "要確認"
    if re.search(r"(PQ|ＰＱ|事前資格審査).{0,30}(不要|実施しない|なし)", text):
        return "なし"
    if re.search(r"(PQ|ＰＱ|事前資格審査)", text):
        return "あり"
    return "要確認"


def extract_candidates(html: str, source_url: str, source_type: str) -> list[dict]:
    parser = _CandidateParser(source_url)
    parser.feed(html)
    for c in parser.candidates:
        c["source_type"] = source_type
    return parser.candidates


def parse_detail(html: str, candidate: dict, fetched_at: str) -> dict:
    parser = _DetailTextParser()
    parser.feed(html or "")

    notice_url = canonicalize_url(candidate.get("candidate_url") or "")
    heading = next((x for x in [*(parser.h1_texts or []), *(parser.h2_texts or []), parser.title] if x), "")
    title = _normalize_text(heading) or _normalize_text(candidate.get("candidate_title") or "")

    text = _normalize_text(" ".join(parser.text_parts))
    raw_text = _truncate(text, RAW_TEXT_LIMIT)
    notice_date = _extract_notice_date(text) or _normalize_text(candidate.get("notice_date_hint") or "")
    evidence_text = _extract_evidence(text) or _normalize_text(candidate.get("evidence_text") or "")
    pq_required = _detect_pq_required(text)

    has_heading = bool(_normalize_text(heading))
    has_body = len(raw_text) >= 40
    parse_confidence = "medium" if has_heading and notice_url and has_body else "low"

    project_id = generate_project_id("", title, "無償資金協力", notice_url)
    return {
        "project_id": project_id,
        "country": "",
        "project_name": title or "要確認",
        "sector": "",
        "scheme": "無償資金協力",
        "ga_date": "",
        "pq_required": pq_required,
        "notice_date": notice_date,
        "notice_media": "JICA",
        "notice_url": notice_url,
        "result_url": "",
        "oda_url": candidate.get("source_url", ""),
        "status_auto": "要確認",
        "status_detail": "discovery収集結果",
        "source_type": candidate.get("source_type", "jica_grant_notice"),
        "source_url": candidate.get("source_url", ""),
        "raw_text": raw_text,
        "evidence_text": evidence_text,
        "parser_name": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "parse_confidence": parse_confidence,
        "fetched_at": fetched_at,
        "last_checked": fetched_at,
        "change_flag": "new",
    }
