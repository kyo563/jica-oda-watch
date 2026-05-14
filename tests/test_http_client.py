from unittest.mock import Mock, patch

from scripts.http_client import fetch_text


@patch("scripts.http_client.requests.get")
def test_fetch_text_sets_timeout_and_user_agent(mock_get):
    response = Mock()
    response.raise_for_status.return_value = None
    response.encoding = "utf-8"
    response.text = "ok"
    mock_get.return_value = response

    text = fetch_text("https://example.com", timeout=12)

    assert text == "ok"
    _, kwargs = mock_get.call_args
    assert kwargs["timeout"] == 12
    assert "User-Agent" in kwargs["headers"]
