from unittest.mock import Mock, patch

import pytest
import requests

from scripts.http_client import HTTPFetchError, fetch_text


@patch("scripts.http_client.requests.get")
def test_fetch_text_sets_timeout_and_headers(mock_get):
    response = Mock()
    response.raise_for_status.return_value = None
    response.encoding = "utf-8"
    response.apparent_encoding = "utf-8"
    response.text = "ok"
    mock_get.return_value = response

    text = fetch_text("https://example.com", timeout=12)

    assert text == "ok"
    _, kwargs = mock_get.call_args
    assert kwargs["timeout"] == 12
    assert kwargs["headers"]["User-Agent"]
    assert "Accept" in kwargs["headers"]
    assert "Accept-Language" in kwargs["headers"]


@patch("scripts.http_client.requests.get")
def test_fetch_text_http_error_keeps_status_and_excerpt(mock_get):
    response = Mock()
    response.status_code = 404
    response.encoding = "utf-8"
    response.apparent_encoding = "utf-8"
    response.text = "x" * 800
    response.raise_for_status.side_effect = requests.HTTPError("not found", response=response)
    mock_get.return_value = response

    with pytest.raises(HTTPFetchError) as excinfo:
        fetch_text("https://example.com/missing")

    err = excinfo.value
    assert err.status_code == 404
    assert err.exception_type == "HTTPError"
    assert len(err.response_excerpt) <= 500
    assert "status=404" in str(err)


@patch("scripts.http_client.requests.get")
def test_fetch_text_timeout_keeps_exception_type(mock_get):
    mock_get.side_effect = requests.Timeout("slow")
    with pytest.raises(HTTPFetchError) as excinfo:
        fetch_text("https://example.com")
    assert excinfo.value.exception_type == "Timeout"


@patch("scripts.http_client.requests.get")
def test_fetch_text_connection_error_keeps_exception_type(mock_get):
    mock_get.side_effect = requests.ConnectionError("down")
    with pytest.raises(HTTPFetchError) as excinfo:
        fetch_text("https://example.com")
    assert excinfo.value.exception_type == "ConnectionError"


def test_http_fetch_error_to_dict_is_json_friendly():
    err = HTTPFetchError(
        "fail",
        url="https://example.com",
        status_code=500,
        reason="ng",
        exception_type="HTTPError",
        response_excerpt="body",
    )
    assert err.to_dict() == {
        "message": "fail",
        "url": "https://example.com",
        "status_code": 500,
        "reason": "ng",
        "exception_type": "HTTPError",
        "response_excerpt": "body",
    }
