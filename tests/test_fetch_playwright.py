from unittest.mock import MagicMock

import pytest

from restock_notifier.fetch import FetchError
from restock_notifier.fetch_playwright import fetch_html_playwright


def make_fake_factory(html, goto_error=None):
    page = MagicMock()
    page.content.return_value = html
    if goto_error is not None:
        page.goto.side_effect = goto_error

    browser = MagicMock()
    browser.new_page.return_value = page

    playwright_instance = MagicMock()
    playwright_instance.chromium.launch.return_value = browser

    context_manager = MagicMock()
    context_manager.__enter__.return_value = playwright_instance
    context_manager.__exit__.return_value = False

    factory = MagicMock(return_value=context_manager)
    return factory, page, browser


def test_fetch_html_playwright_returns_page_content():
    factory, page, browser = make_fake_factory("<html>rendered</html>")

    html = fetch_html_playwright("https://example.com", sync_playwright_factory=factory)

    assert html == "<html>rendered</html>"
    page.goto.assert_called_once_with(
        "https://example.com", wait_until="networkidle", timeout=30000
    )


def test_fetch_html_playwright_closes_browser():
    factory, page, browser = make_fake_factory("<html>x</html>")

    fetch_html_playwright("https://example.com", sync_playwright_factory=factory)

    browser.close.assert_called_once()


def test_fetch_html_playwright_raises_fetch_error_on_goto_failure():
    factory, page, browser = make_fake_factory(
        "<html>unused</html>", goto_error=TimeoutError("navigation timed out")
    )

    with pytest.raises(FetchError) as excinfo:
        fetch_html_playwright("https://example.com", sync_playwright_factory=factory)

    assert "https://example.com" in str(excinfo.value)
    assert "navigation timed out" in str(excinfo.value)


def test_fetch_html_playwright_closes_browser_even_on_goto_failure():
    factory, page, browser = make_fake_factory(
        "<html>unused</html>", goto_error=TimeoutError("navigation timed out")
    )

    with pytest.raises(FetchError):
        fetch_html_playwright("https://example.com", sync_playwright_factory=factory)

    browser.close.assert_called_once()
