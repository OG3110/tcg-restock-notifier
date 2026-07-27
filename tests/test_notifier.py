import pytest
import requests

from restock_notifier import notifier


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


def test_send_message_posts_to_telegram_api(monkeypatch):
    captured = {}

    def fake_post(url, data, timeout):
        captured["url"] = url
        captured["data"] = data
        captured["timeout"] = timeout
        return FakeResponse({"ok": True})

    monkeypatch.setattr(notifier.requests, "post", fake_post)

    result = notifier.send_message("TOKEN123", "CHAT456", "Hallo Welt")

    assert captured["url"] == "https://api.telegram.org/botTOKEN123/sendMessage"
    assert captured["data"]["chat_id"] == "CHAT456"
    assert captured["data"]["text"] == "Hallo Welt"
    assert result == {"ok": True}


def test_send_message_raises_on_http_error(monkeypatch):
    def fake_post(url, data, timeout):
        return FakeResponse({"ok": False}, status_code=500)

    monkeypatch.setattr(notifier.requests, "post", fake_post)

    with pytest.raises(RuntimeError):
        notifier.send_message("TOKEN123", "CHAT456", "Hallo Welt")


def test_send_message_masks_bot_token_on_http_error(monkeypatch):
    token = "TOKENSECRET123"

    class HttpErrorResponse:
        status_code = 500

        def raise_for_status(self):
            raise requests.HTTPError(
                f"500 Server Error: Internal Server Error for url: "
                f"https://api.telegram.org/bot{token}/sendMessage",
                response=self,
            )

    def fake_post(url, data, timeout):
        return HttpErrorResponse()

    monkeypatch.setattr(notifier.requests, "post", fake_post)

    with pytest.raises(requests.HTTPError) as excinfo:
        notifier.send_message(token, "CHAT456", "Hallo Welt")

    assert token not in str(excinfo.value)
    assert "***" in str(excinfo.value)
    # Verify exception chain is suppressed to fully mask the token in tracebacks
    assert excinfo.value.__cause__ is None


def test_format_restock_message():
    text = notifier.format_restock_message(
        "One Piece OP17 Display", "fantasiacards", "https://fantasiacards.de/x"
    )
    assert "One Piece OP17 Display" in text
    assert "fantasiacards" in text
    assert "https://fantasiacards.de/x" in text
    assert text.startswith("🟢")


def test_format_down_message():
    text = notifier.format_down_message("One Piece OP17 Display", "fantasiacards")
    assert "One Piece OP17 Display" in text
    assert "fantasiacards" in text


def test_format_stale_message():
    text = notifier.format_stale_message("One Piece OP17 Display", "fantasiacards")
    assert "One Piece OP17 Display" in text
    assert "shops.json" in text
