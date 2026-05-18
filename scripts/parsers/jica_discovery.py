from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urljoin

try:
    from scripts.utils_project_id import canonicalize_url, generate_project_id
except ModuleNotFoundError:
    from utils_project_id import canonicalize_url, generate_project_id

PARSER_NAME = "jica_discovery"
PARSER_VERSION = "0.3"
RAW_TEXT_LIMIT = 1200
EVIDENCE_LIMIT = 220

_TITLE_KEYWORDS = [
    "調達", "入札", "案件", "公示", "公告", "契約", "事前資格審査", "PQ", "ＰＱ",
    "参加意思確認", "参加資格", "コンサルタント", "業務実施契約", "機材", "施工",
]
_HREF_KEYWORDS = ["chotatsu", "procurement", "bid", "keiyaku", ".pdf"]

_NON_PROJECT_PATHS = [
    "/forresearchers",
    "/about/announce/notice",
    "/about/announce/manual",
    "/about/disc/settle",
    "/about/announce/",
    "/about/chotatsu/program/",
]
_NON_PROJECT_TITLE_EXACT = {"Japanese"}
_NON_PROJECT_TITLE_CONTAINS = ["公告・公示情報", "調達ガイドライン", "様式", "決算公告", "for Researchers", "調達情報"]
_MAIN_SELECTORS = ["<main", "<article", "id=\"contents\"", "class=\"contents\"", "class=\"main\"", "class=\"l-main\""]


class _CandidateParser(HTMLParser):
    def __init__(self, base_url: str, source_type: str):
        super().__init__()
        self.base_url = base_url
        self.source_type = source_type
        self.candidates = []
        self.sample_links = []
        self.rejected_link_samples = []
        self.anchors_seen = 0
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
        self.anchors_seen += 1

        if len(self.sample_links) < 10:
            self.sample_links.append({"title": title, "url": url})

        if _is_candidate_link(title, self._href):
            candidate = {
                "source_type": self.source_type,
                "source_url": self.base_url,
                "candidate_url": url,
                "candidate_title": title or "(no title)",
                "country_hint": "",
                "scheme_hint": "無償資金協力",
                "notice_date_hint": "",
                "evidence_text": title,
            }
            if self._href.lower().endswith(".pdf"):
                candidate["candidate_kind"] = "pdf"
            self.candidates.append(candidate)
        elif len(self.rejected_link_samples) < 20:
            self.rejected_link_samples.append({"title": title, "url": url})

        self._href = ""
        self._text = ""


def _is_candidate_link(title: str, href: str) -> bool:
    title_norm = _normalize_text(title)
    href_norm = (href or "").lower()
    return any(k in title_norm for k in _TITLE_KEYWORDS) or any(k in href_norm for k in _HREF_KEYWORDS)


def _extract_candidate_html(html: str) -> str:
    low = (html or "").lower()
    for marker in _MAIN_SELECTORS:
        idx = low.find(marker.lower())
        if idx >= 0:
            return (html or "")[idx:]
    return html or ""


def _canonical_candidate_url(url: str) -> str:
    c = canonicalize_url(url or "")
    if c.endswith("/") and len(c) > len("https://"):
        c = c.rstrip("/")
    return c


def dedupe_and_prioritize_candidates(candidates: list[dict], max_detail: int) -> tuple[list[dict], int]:
    seen = set()
    deduped = []
    deduped_count = 0
    for c in candidates:
        norm = _canonical_candidate_url(c.get("candidate_url") or "")
        if not norm:
            deduped_count += 1
            continue
        if norm in seen:
            deduped_count += 1
            continue
        seen.add(norm)
        copied = dict(c)
        copied["candidate_url"] = norm
        copied["source_url"] = _canonical_candidate_url(copied.get("source_url") or "")
        deduped.append(copied)

    def score(c: dict) -> tuple[int,int,int]:
        title = _normalize_text(c.get("candidate_title") or "")
        is_pdf = 1 if _is_pdf_candidate(c) else 0
        has_date = 1 if extract_notice_date_from_text(title) else 0
        has_notice_word = 1 if any(k in title for k in ["公示", "公告"]) else 0
        return (-is_pdf, -has_date, -has_notice_word)

    deduped.sort(key=score)
    return deduped[:max_detail], deduped_count


def inspect_candidate_links(html: str, source_url: str, source_type: str) -> dict:
    parser = _CandidateParser(source_url, source_type)
    parser.feed(_extract_candidate_html(html))
    return {
        "anchors_seen": parser.anchors_seen,
        "candidates_found": len(parser.candidates),
        "sample_links": parser.sample_links,
        "rejected_link_samples": parser.rejected_link_samples,
    }


def extract_candidates_with_diagnostics(html: str, source_url: str, source_type: str) -> tuple[list[dict], dict]:
    parser = _CandidateParser(source_url, source_type)
    parser.feed(_extract_candidate_html(html))
    return parser.candidates, {
        "anchors_seen": parser.anchors_seen,
        "candidates_found": len(parser.candidates),
        "sample_links": parser.sample_links,
        "rejected_link_samples": parser.rejected_link_samples,
    }


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
    date_pat = r"((?:20\d{2})[./年\-](?:\d{1,2})[./月\-](?:\d{1,2})日?|(?:令和\d{1,2})年\s*(?:\d{1,2})月\s*(?:\d{1,2})日)"
    label_pat = r"(?:公示日|公告日|掲載日|更新日)"
    m = re.search(rf"{label_pat}\s*[:：]?\s*{date_pat}", text)
    if m:
        return m.group(1)
    m = re.search(rf"{date_pat}\s*[:：]?\s*{label_pat}", text)
    if m:
        return m.group(1)
    return ""



def _is_pdf_candidate(candidate: dict) -> bool:
    kind = (candidate.get("candidate_kind") or "").lower()
    if kind == "pdf":
        return True
    url = (candidate.get("candidate_url") or "").lower()
    return url.endswith(".pdf") or ".pdf?" in url or ".pdf#" in url


def extract_notice_date_from_text(text: str) -> str:
    if not text:
        return ""
    t = _normalize_text(text)
    patterns = [
        r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日",
        r"(20\d{2})/(\d{1,2})/(\d{1,2})",
        r"(20\d{2})-(\d{1,2})-(\d{1,2})",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            y, mo, d = m.groups()
            return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return ""


def _should_reject_candidate(candidate: dict) -> tuple[bool, str]:
    source_url = _canonical_candidate_url(candidate.get("source_url") or "")
    url = _canonical_candidate_url(candidate.get("candidate_url") or "")
    title = _normalize_text(candidate.get("candidate_title") or "")
    if not url or (source_url and url == source_url):
        return True, "non_project_navigation_page"
    url_low = url.lower()
    if any(path in url_low for path in _NON_PROJECT_PATHS):
        return True, "non_project_navigation_page"
    if title in _NON_PROJECT_TITLE_EXACT:
        return True, "non_project_navigation_page"
    if any(term in title for term in _NON_PROJECT_TITLE_CONTAINS):
        return True, "non_project_navigation_page"
    return False, ""


def build_pdf_metadata_only_record(candidate: dict, fetched_at: str) -> dict:
    notice_url = canonicalize_url(candidate.get("candidate_url") or "")
    title = _normalize_text(candidate.get("candidate_title") or "") or "要確認"
    notice_date = extract_notice_date_from_text(title)
    raw_text = _truncate(f"{title} {notice_url}", RAW_TEXT_LIMIT)
    project_id = generate_project_id("", title, "無償資金協力", notice_url)
    return {
        "project_id": project_id,
        "country": "",
        "project_name": title,
        "sector": "",
        "scheme": "無償資金協力",
        "ga_date": "",
        "pq_required": "要確認",
        "notice_date": notice_date,
        "notice_media": "JICA",
        "notice_url": notice_url,
        "result_url": "",
        "oda_url": candidate.get("source_url", ""),
        "status_auto": "要確認",
        "status_detail": "pdf_metadata_only",
        "source_type": candidate.get("source_type", "jica_grant_notice"),
        "source_url": candidate.get("source_url", ""),
        "raw_text": raw_text,
        "evidence_text": title,
        "parser_name": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "parse_confidence": "low",
        "fetched_at": fetched_at,
        "last_checked": fetched_at,
        "change_flag": "new",
    }

def _extract_evidence(text: str) -> str:
    if not text:
        return ""
    keys = ["公告", "公示", "入札", "調達", "事前資格審査", "PQ", "ＰＱ"]
    for key in keys:
        idx = text.find(key)
        if idx >= 0:
            start = max(0, idx - 60)
            end = min(len(text), idx + 140)
            return _truncate(text[start:end], EVIDENCE_LIMIT)
    return ""


def _detect_pq_required(text: str) -> str:
    if not text:
        return "要確認"
    term = r"(?:PQ|ＰＱ|事前資格審査)"
    neg = r"(?:不要|なし|無し|ありません|有りません|実施しない|実施しません|実施なし|実施無し|行わない|行いません|対象外|該当なし|該当しない)"
    if re.search(rf"{term}.{{0,24}}{neg}|{neg}.{{0,24}}{term}", text):
        return "なし"

    pos_patterns = [
        r"事前資格審査.{0,12}実施",
        r"PQ.{0,12}実施",
        r"ＰＱ.{0,12}実施",
        r"事前資格審査.{0,16}申請.{0,8}受け付け",
        r"PQ.{0,16}申請.{0,8}受け付け",
        r"ＰＱ.{0,16}申請.{0,8}受け付け",
        r"事前資格審査.{0,16}提出.{0,8}受け付け",
        r"PQ.{0,16}提出.{0,8}受け付け",
        r"ＰＱ.{0,16}提出.{0,8}受け付け",
    ]
    if any(re.search(p, text) for p in pos_patterns):
        return "あり"
    return "要確認"


def extract_candidates(html: str, source_url: str, source_type: str) -> list[dict]:
    candidates, _ = extract_candidates_with_diagnostics(html, source_url, source_type)
    return candidates


def parse_detail(html: str, candidate: dict, fetched_at: str) -> dict:
    parser = _DetailTextParser()
    parser.feed(html or "")

    notice_url = canonicalize_url(candidate.get("candidate_url") or "")
    heading = next((x for x in [*(parser.h1_texts or []), *(parser.h2_texts or []), parser.title] if x), "")
    title = _normalize_text(heading) or _normalize_text(candidate.get("candidate_title") or "")

    text = _normalize_text(" ".join(parser.text_parts))
    raw_text = _truncate(text, RAW_TEXT_LIMIT)
    notice_date = _extract_notice_date(text) or extract_notice_date_from_text(candidate.get("candidate_title") or "") or _normalize_text(candidate.get("notice_date_hint") or "")
    detail_evidence = _extract_evidence(text)
    candidate_evidence = _normalize_text(candidate.get("evidence_text") or "")
    evidence_text = detail_evidence or candidate_evidence
    pq_required = _detect_pq_required(text)

    has_heading = bool(_normalize_text(heading))
    has_body = len(raw_text) >= 40
    has_evidence = bool(detail_evidence)
    is_pdf = _is_pdf_candidate(candidate)
    has_date = bool(notice_date)
    has_title_hint = any(k in title for k in ["調達", "公示", "公告", "入札"])
    parse_confidence = "medium" if (has_heading and notice_url and has_body and has_evidence and has_date and has_title_hint and not is_pdf) else "low"

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
        if tag in {"script", "style", "nav", "header", "footer"}:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if self._tag_stack:
            self._tag_stack.pop()
        if tag in {"script", "style", "nav", "header", "footer"} and self._skip_depth > 0:
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
