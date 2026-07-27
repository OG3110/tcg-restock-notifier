import time

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class FetchError(Exception):
    pass


def fetch_html_http(url, retries=3, backoff_seconds=2, session=None):
    http = session or requests
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = http.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(backoff_seconds)
    raise FetchError(f"Failed to fetch {url} after {retries} attempts: {last_error}")
