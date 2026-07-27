from unittest.mock import MagicMock

from restock_notifier.fetch_playwright import fetch_html_playwright


def make_fake_factory(html):
    page = MagicMock()
    page.content.return_value = html

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
