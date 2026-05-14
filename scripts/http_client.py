#!/usr/bin/env python3
import requests

DEFAULT_TIMEOUT = 20
DEFAULT_USER_AGENT = "jica-oda-watch/0.2 (+https://github.com/kyo563/jica-oda-watch)"


class HTTPFetchError(RuntimeError):
    pass


def fetch_text(url: str, timeout: int = DEFAULT_TIMEOUT, user_agent: str = DEFAULT_USER_AGENT) -> str:
    headers = {"User-Agent": user_agent}
    try:
        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPFetchError(f"HTTP取得失敗: url={url}: {e}") from e

    # TODO: robots.txt の確認とrate limit制御を追加する
    response.encoding = response.encoding or "utf-8"
    return response.text
