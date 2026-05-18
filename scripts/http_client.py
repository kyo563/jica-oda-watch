#!/usr/bin/env python3
from __future__ import annotations

import re

import requests

DEFAULT_TIMEOUT = (10, 30)
DEFAULT_USER_AGENT = "jica-oda-watch/0.2 (+https://github.com/kyo563/jica-oda-watch)"
MAX_RESPONSE_EXCERPT = 500

_MOJIBAKE_PATTERNS = ["ã\x81", "ã\x82", "ã\x83", "Â", "ï¼"]
_LATIN_ALIASES = {"latin-1", "latin1", "iso-8859-1"}
_META_CHARSET_RE = re.compile(br"<meta[^>]+charset\s*=\s*['\"]?\s*([a-zA-Z0-9_\-]+)", re.I)
_META_HTTP_EQUIV_RE = re.compile(
    br"<meta[^>]+http-equiv\s*=\s*['\"]content-type['\"][^>]+content\s*=\s*['\"][^>]*charset\s*=\s*([a-zA-Z0-9_\-]+)",
    re.I,
)


class HTTPFetchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        url: str = "",
        status_code: int | None = None,
        reason: str = "",
        exception_type: str = "",
        response_excerpt: str = "",
    ):
        self.message = message
        self.url = url
        self.status_code = status_code
        self.reason = reason
        self.exception_type = exception_type
        self.response_excerpt = (response_excerpt or "")[:MAX_RESPONSE_EXCERPT]
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        parts = [self.message]
        if self.url:
            parts.append(f"url={self.url}")
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.reason:
            parts.append(f"reason={self.reason}")
        if self.exception_type:
            parts.append(f"exception={self.exception_type}")
        return " | ".join(parts)

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "url": self.url,
            "status_code": self.status_code,
            "reason": self.reason,
            "exception_type": self.exception_type,
            "response_excerpt": self.response_excerpt,
        }


def looks_mojibake(text: str) -> bool:
    if not text:
        return False
    return any(p in text for p in _MOJIBAKE_PATTERNS)


def _encoding_from_content_type(response: requests.Response) -> str:
    content_type = response.headers.get("Content-Type", "") if getattr(response, "headers", None) else ""
    m = re.search(r"charset\s*=\s*([\w\-]+)", content_type, re.I)
    return (m.group(1) if m else "").strip().lower()


def _encoding_from_html_meta(content: bytes) -> str:
    head = content[:4096] if content else b""
    for pat in (_META_CHARSET_RE, _META_HTTP_EQUIV_RE):
        m = pat.search(head)
        if m:
            return m.group(1).decode("ascii", errors="ignore").strip().lower()
    return ""


def detect_encoding(response: requests.Response) -> str:
    content = response.content or b""
    header_enc = _encoding_from_content_type(response)
    meta_enc = _encoding_from_html_meta(content)
    apparent = (response.apparent_encoding or "").strip().lower()

    if meta_enc:
        if header_enc in _LATIN_ALIASES and meta_enc.startswith("utf"):
            return meta_enc
        if not header_enc:
            return meta_enc
    if header_enc:
        return header_enc
    if meta_enc:
        return meta_enc
    if apparent and apparent not in _LATIN_ALIASES:
        return apparent
    return "utf-8"


def decode_response_text(response: requests.Response) -> str:
    enc = detect_encoding(response)
    content = response.content or b""
    try:
        text = content.decode(enc, errors="replace")
    except LookupError:
        text = content.decode("utf-8", errors="replace")
    if enc in _LATIN_ALIASES and looks_mojibake(text):
        return content.decode("utf-8", errors="replace")
    return text


def _extract_response_excerpt(response: requests.Response | None) -> str:
    if response is None:
        return ""
    try:
        return decode_response_text(response)[:MAX_RESPONSE_EXCERPT]
    except Exception:
        return ""


def fetch_text(url: str, timeout=DEFAULT_TIMEOUT, user_agent: str = DEFAULT_USER_AGENT) -> str:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
    }
    try:
        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()
    except requests.HTTPError as exc:
        response = exc.response
        raise HTTPFetchError(
            "HTTP取得失敗",
            url=url,
            status_code=response.status_code if response is not None else None,
            reason=str(exc),
            exception_type=type(exc).__name__,
            response_excerpt=_extract_response_excerpt(response),
        ) from exc
    except requests.Timeout as exc:
        raise HTTPFetchError(
            "HTTP取得タイムアウト",
            url=url,
            reason=str(exc),
            exception_type=type(exc).__name__,
        ) from exc
    except requests.TooManyRedirects as exc:
        response = getattr(exc, "response", None)
        raise HTTPFetchError(
            "HTTPリダイレクト過多",
            url=url,
            status_code=response.status_code if response is not None else None,
            reason=str(exc),
            exception_type=type(exc).__name__,
            response_excerpt=_extract_response_excerpt(response),
        ) from exc
    except requests.ConnectionError as exc:
        raise HTTPFetchError(
            "HTTP接続失敗",
            url=url,
            reason=str(exc),
            exception_type=type(exc).__name__,
        ) from exc
    except requests.RequestException as exc:
        response = getattr(exc, "response", None)
        raise HTTPFetchError(
            "HTTP取得失敗",
            url=url,
            status_code=response.status_code if response is not None else None,
            reason=str(exc),
            exception_type=type(exc).__name__,
            response_excerpt=_extract_response_excerpt(response),
        ) from exc

    return decode_response_text(response)
