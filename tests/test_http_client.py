from unittest.mock import Mock, patch

import pytest
import requests

from scripts.http_client import HTTPFetchError, fetch_text, looks_mojibake


@patch("scripts.http_client.requests.get")
def test_fetch_text_sets_timeout_and_headers(mock_get):
    response = Mock()
    response.raise_for_status.return_value = None
    response.headers = {"Content-Type": "text/html; charset=utf-8"}
    response.content = "ok".encode("utf-8")
    response.apparent_encoding = "utf-8"
    mock_get.return_value = response

    text = fetch_text("https://example.com", timeout=12)

    assert text == "ok"
    _, kwargs = mock_get.call_args
    assert kwargs["timeout"] == 12


@patch("scripts.http_client.requests.get")
def test_fetch_text_prefers_meta_utf8_over_latin1(mock_get):
    response = Mock()
    response.raise_for_status.return_value = None
    response.headers = {"Content-Type": "text/html; charset=ISO-8859-1"}
    response.apparent_encoding = "ISO-8859-1"
    body = '<meta charset="utf-8"><h1>コンサルタント</h1>'
    response.content = body.encode("utf-8")
    mock_get.return_value = response

    text = fetch_text("https://example.com")
    assert "コンサルタント" in text


def test_looks_mojibake_detects_common_pattern():
    assert looks_mojibake("ã³ã³ãµ") is True
    assert looks_mojibake("正常な日本語") is False


@patch("scripts.http_client.requests.get")
def test_fetch_text_http_error_keeps_status_and_excerpt(mock_get):
    response = Mock()
    response.status_code = 404
    response.headers = {"Content-Type": "text/html; charset=utf-8"}
    response.apparent_encoding = "utf-8"
    response.content = ("x" * 800).encode("utf-8")
    response.raise_for_status.side_effect = requests.HTTPError("not found", response=response)
    mock_get.return_value = response

    with pytest.raises(HTTPFetchError) as excinfo:
        fetch_text("https://example.com/missing")

    err = excinfo.value
    assert err.status_code == 404
    assert err.exception_type == "HTTPError"
    assert len(err.response_excerpt) <= 500
