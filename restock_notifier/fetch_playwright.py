from restock_notifier.fetch import FetchError


def fetch_html_playwright(url, sync_playwright_factory=None):
    try:
        if sync_playwright_factory is None:
            from playwright.sync_api import sync_playwright as sync_playwright_factory

        with sync_playwright_factory() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=30000)
                html = page.content()
            finally:
                browser.close()
    except Exception as exc:
        raise FetchError(f"Failed to fetch {url} via Playwright: {exc}") from exc
    return html
