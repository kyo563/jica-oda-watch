#!/usr/bin/env python3
from __future__ import annotations

import requests

DEFAULT_TIMEOUT = (10, 30)
DEFAULT_USER_AGENT = "jica-oda-watch/0.2 (+https://github.com/kyo563/jica-oda-watch)"
MAX_RESPONSE_EXCERPT = 500


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


def _resolve_encoding(response: requests.Response) -> str:
    return response.encoding or response.apparent_encoding or "utf-8"


def _extract_response_excerpt(response: requests.Response | None) -> str:
    if response is None:
        return ""
    try:
        enc = _resolve_encoding(response)
        response.encoding = enc
        text = response.text or ""
        return text[:MAX_RESPONSE_EXCERPT]
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

    # TODO: robots.txt の確認とrate limit制御を追加する
    response.encoding = _resolve_encoding(response)
    return response.text
