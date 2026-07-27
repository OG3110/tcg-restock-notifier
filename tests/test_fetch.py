import pytest
import requests

from restock_notifier.fetch import FetchError, fetch_html_http


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, headers, timeout):
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_fetch_html_http_returns_text_on_success():
    session = FakeSession([FakeResponse("<html>ok</html>")])

    html = fetch_html_http("https://example.com", session=session)

    assert html == "<html>ok</html>"
    assert session.calls == 1


def test_fetch_html_http_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("restock_notifier.fetch.time.sleep", lambda seconds: None)
    session = FakeSession([
        requests.ConnectionError("boom"),
        requests.ConnectionError("boom again"),
        FakeResponse("<html>ok</html>"),
    ])

    html = fetch_html_http("https://example.com", retries=3, session=session)

    assert html == "<html>ok</html>"
    assert session.calls == 3


def test_fetch_html_http_raises_fetch_error_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr("restock_notifier.fetch.time.sleep", lambda seconds: None)
    session = FakeSession([
        requests.ConnectionError("boom"),
        requests.ConnectionError("boom"),
        requests.ConnectionError("boom"),
    ])

    with pytest.raises(FetchError):
        fetch_html_http("https://example.com", retries=3, session=session)
