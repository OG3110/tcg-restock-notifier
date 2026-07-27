# TCG Restock Notifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python tool that checks configured TCG-shop product pages for restocks and sends a Telegram message on "ausverkauft → verfügbar" transitions, run every 15 minutes via GitHub Actions.

**Architecture:** A small `restock_notifier` package with one module per responsibility (config loading, HTML availability parsing, state persistence, Telegram notifications, HTTP/Playwright fetching, orchestration). Pure logic (config parsing, availability detection, message formatting, state transitions) is unit-tested without network access; network calls (`requests`, Playwright) are isolated behind thin functions injected into the orchestration layer so `main.run()` is testable with fakes.

**Tech Stack:** Python 3.12, `requests`, `beautifulsoup4` + `soupsieve` (CSS selectors), `playwright` (fallback for JS-rendered shops), `pytest`. Runs on GitHub Actions (`schedule` cron, every 15 min).

## Global Constraints

- Notification channel: Telegram Bot API only (per approved spec).
- Excluded shops: Amazon, Media Markt — never add these to `products.json`/`shops.json`.
- Hosting: GitHub Actions scheduled workflow, `cron: "*/15 * * * *"`, plus `workflow_dispatch` for manual runs.
- Config files at repo root: `shops.json` (per-shop CSS selector + mode, or `"type": "shopify"` shorthand), `products.json` (user-maintained watchlist), `state.json` (auto-managed, committed back by the workflow).
- Shopify shorthand default selector: `button[name="add"]:not([disabled])`, mode `found_means_available` — verified live against `https://fantasiacards.de/products/one-piece-card-game-op17-display-eng`.
- Telegram message only sent on `unavailable → available` transitions (never on every check, never on `available → unavailable`).
- Fetch failures alert after 3 consecutive failures for the same product (not on every single failure).
- A product stuck at `unavailable` for 480 consecutive checks (~5 days at 15-min interval) triggers one "check the selector" warning, reset when it becomes available again.
- Reference spec: `docs/superpowers/specs/2026-07-27-tcg-restock-notifier-design.md`.

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `restock_notifier/__init__.py`
- Create: `tests/__init__.py`
- Test: `tests/test_scaffolding.py`

**Interfaces:**
- Produces: an importable `restock_notifier` package on `sys.path` for all later tasks, and a working `pytest` setup (`pythonpath = ["."]`).

- [ ] **Step 1: Create `requirements.txt`**

```
requests>=2.31,<3
beautifulsoup4>=4.12,<5
soupsieve>=2.5,<3
playwright>=1.40,<2
```

- [ ] **Step 2: Create `requirements-dev.txt`**

```
-r requirements.txt
pytest>=7.4,<9
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 4: Create `.gitignore`**

```
__pycache__/
*.pyc
.venv/
.env
```

- [ ] **Step 5: Create empty package/test init files**

`restock_notifier/__init__.py`:
```python
```

`tests/__init__.py`:
```python
```

- [ ] **Step 6: Write a sanity test**

`tests/test_scaffolding.py`:
```python
import restock_notifier


def test_package_importable():
    assert restock_notifier is not None
```

- [ ] **Step 7: Install dev dependencies**

Run: `pip install -r requirements-dev.txt`

- [ ] **Step 8: Run the sanity test**

Run: `pytest -v`
Expected: `tests/test_scaffolding.py::test_package_importable PASSED`

- [ ] **Step 9: Commit**

```bash
git add requirements.txt requirements-dev.txt pyproject.toml .gitignore restock_notifier/__init__.py tests/__init__.py tests/test_scaffolding.py
git commit -m "chore: project scaffolding for restock notifier"
```

---

### Task 2: Config loader (`shops.json` + `products.json`)

**Files:**
- Create: `restock_notifier/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `ConfigError(Exception)`
  - `load_shops(shops_path) -> dict[str, {"selector": str, "mode": str, "render": str}]`
  - `load_watchlist(products_path, shops_path) -> list[dict]`, each item:
    `{"id": str, "name": str, "url": str, "shop_id": str, "selector": str, "mode": str, "render": str}`
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write failing tests**

`tests/test_config.py`:
```python
import json

import pytest

from restock_notifier.config import ConfigError, load_shops, load_watchlist


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_load_shops_resolves_shopify_shorthand(tmp_path):
    shops_path = tmp_path / "shops.json"
    write_json(shops_path, {"fantasiacards": {"type": "shopify"}})

    shops = load_shops(shops_path)

    assert shops["fantasiacards"] == {
        "selector": 'button[name="add"]:not([disabled])',
        "mode": "found_means_available",
        "render": "http",
    }


def test_load_shops_custom_selector(tmp_path):
    shops_path = tmp_path / "shops.json"
    write_json(shops_path, {
        "sapphire-cards": {
            "selector": ".stock-status--sold-out",
            "mode": "found_means_unavailable",
        }
    })

    shops = load_shops(shops_path)

    assert shops["sapphire-cards"]["selector"] == ".stock-status--sold-out"
    assert shops["sapphire-cards"]["mode"] == "found_means_unavailable"
    assert shops["sapphire-cards"]["render"] == "http"


def test_load_shops_missing_selector_raises(tmp_path):
    shops_path = tmp_path / "shops.json"
    write_json(shops_path, {"broken-shop": {"mode": "found_means_available"}})

    with pytest.raises(ConfigError, match="broken-shop"):
        load_shops(shops_path)


def test_load_shops_invalid_mode_raises(tmp_path):
    shops_path = tmp_path / "shops.json"
    write_json(shops_path, {
        "weird-shop": {"selector": ".x", "mode": "not_a_real_mode"}
    })

    with pytest.raises(ConfigError, match="not_a_real_mode"):
        load_shops(shops_path)


def test_load_shops_invalid_css_selector_raises(tmp_path):
    shops_path = tmp_path / "shops.json"
    write_json(shops_path, {
        "bad-css": {"selector": "[[[not-valid", "mode": "found_means_available"}
    })

    with pytest.raises(ConfigError, match="bad-css"):
        load_shops(shops_path)


def test_load_watchlist_merges_product_and_shop(tmp_path):
    shops_path = tmp_path / "shops.json"
    products_path = tmp_path / "products.json"
    write_json(shops_path, {"fantasiacards": {"type": "shopify"}})
    write_json(products_path, [{
        "id": "op17-display-fantasiacards",
        "name": "One Piece OP17 Display",
        "shop": "fantasiacards",
        "url": "https://fantasiacards.de/products/one-piece-card-game-op17-display-eng",
    }])

    watchlist = load_watchlist(products_path, shops_path)

    assert watchlist == [{
        "id": "op17-display-fantasiacards",
        "name": "One Piece OP17 Display",
        "url": "https://fantasiacards.de/products/one-piece-card-game-op17-display-eng",
        "shop_id": "fantasiacards",
        "selector": 'button[name="add"]:not([disabled])',
        "mode": "found_means_available",
        "render": "http",
    }]


def test_load_watchlist_unknown_shop_raises(tmp_path):
    shops_path = tmp_path / "shops.json"
    products_path = tmp_path / "products.json"
    write_json(shops_path, {})
    write_json(products_path, [{
        "id": "x", "name": "X", "shop": "ghost-shop", "url": "https://example.com",
    }])

    with pytest.raises(ConfigError, match="ghost-shop"):
        load_watchlist(products_path, shops_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'restock_notifier.config'`

- [ ] **Step 3: Implement `restock_notifier/config.py`**

```python
import json

import soupsieve

SHOPIFY_DEFAULT_SELECTOR = 'button[name="add"]:not([disabled])'
SHOPIFY_DEFAULT_MODE = "found_means_available"
VALID_MODES = ("found_means_available", "found_means_unavailable")


class ConfigError(Exception):
    pass


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_shops(shops_path):
    raw = _load_json(shops_path)

    shops = {}
    for shop_id, entry in raw.items():
        if entry.get("type") == "shopify":
            selector = entry.get("selector", SHOPIFY_DEFAULT_SELECTOR)
            mode = entry.get("mode", SHOPIFY_DEFAULT_MODE)
        else:
            if "selector" not in entry or "mode" not in entry:
                raise ConfigError(
                    f"Shop '{shop_id}' must define 'selector' and 'mode' "
                    f"unless 'type' is 'shopify'"
                )
            selector = entry["selector"]
            mode = entry["mode"]

        if mode not in VALID_MODES:
            raise ConfigError(
                f"Shop '{shop_id}' has invalid mode {mode!r}, expected one of {VALID_MODES}"
            )

        try:
            soupsieve.compile(selector)
        except Exception as exc:
            raise ConfigError(
                f"Shop '{shop_id}' has invalid CSS selector {selector!r}: {exc}"
            ) from exc

        shops[shop_id] = {
            "selector": selector,
            "mode": mode,
            "render": entry.get("render", "http"),
        }
    return shops


def load_watchlist(products_path, shops_path):
    shops = load_shops(shops_path)
    products = _load_json(products_path)

    watchlist = []
    for product in products:
        shop_id = product["shop"]
        if shop_id not in shops:
            raise ConfigError(
                f"Product '{product['id']}' references unknown shop '{shop_id}'"
            )
        shop = shops[shop_id]
        watchlist.append({
            "id": product["id"],
            "name": product["name"],
            "url": product["url"],
            "shop_id": shop_id,
            "selector": shop["selector"],
            "mode": shop["mode"],
            "render": shop["render"],
        })
    return watchlist
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: all 7 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add restock_notifier/config.py tests/test_config.py
git commit -m "feat: config loader for shops.json/products.json"
```

---

### Task 3: Availability detection

**Files:**
- Create: `restock_notifier/availability.py`
- Test: `tests/test_availability.py`

**Interfaces:**
- Produces: `determine_status(html: str, selector: str, mode: str) -> "available" | "unavailable"`
- Consumes: nothing from earlier tasks (pure function on raw HTML strings).

- [ ] **Step 1: Write failing tests**

`tests/test_availability.py`:
```python
import pytest

from restock_notifier.availability import determine_status

# Real markup captured from fantasiacards.de (Shopify) on 2026-07-27.
SOLD_OUT_BUTTON_HTML = """
<form action="/cart/add" method="post">
  <button type="submit" name="add" data-add-to-cart=""
          class="btn btn--full add-to-cart add-to-cart--secondary" disabled="disabled">
    <span>In den Einkaufswagen</span>
  </button>
</form>
"""

AVAILABLE_BUTTON_HTML = """
<form action="/cart/add" method="post">
  <button type="submit" name="add" data-add-to-cart=""
          class="btn btn--full add-to-cart add-to-cart--secondary">
    <span>In den Einkaufswagen</span>
  </button>
</form>
"""

SOLD_OUT_BADGE_HTML = """
<div class="product">
  <div class="stock-status--sold-out">Ausverkauft</div>
</div>
"""

IN_STOCK_BADGE_HTML = """
<div class="product">
  <div class="stock-status--in-stock">Auf Lager</div>
</div>
"""

SHOPIFY_SELECTOR = 'button[name="add"]:not([disabled])'


def test_shopify_sold_out_button_is_unavailable():
    status = determine_status(SOLD_OUT_BUTTON_HTML, SHOPIFY_SELECTOR, "found_means_available")
    assert status == "unavailable"


def test_shopify_enabled_button_is_available():
    status = determine_status(AVAILABLE_BUTTON_HTML, SHOPIFY_SELECTOR, "found_means_available")
    assert status == "available"


def test_sold_out_badge_present_is_unavailable():
    status = determine_status(
        SOLD_OUT_BADGE_HTML, ".stock-status--sold-out", "found_means_unavailable"
    )
    assert status == "unavailable"


def test_sold_out_badge_absent_is_available():
    status = determine_status(
        IN_STOCK_BADGE_HTML, ".stock-status--sold-out", "found_means_unavailable"
    )
    assert status == "available"


def test_unknown_mode_raises():
    with pytest.raises(ValueError, match="mode"):
        determine_status(AVAILABLE_BUTTON_HTML, SHOPIFY_SELECTOR, "bogus_mode")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_availability.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'restock_notifier.availability'`

- [ ] **Step 3: Implement `restock_notifier/availability.py`**

```python
from bs4 import BeautifulSoup


def determine_status(html, selector, mode):
    soup = BeautifulSoup(html, "html.parser")
    found = soup.select_one(selector) is not None

    if mode == "found_means_available":
        return "available" if found else "unavailable"
    if mode == "found_means_unavailable":
        return "unavailable" if found else "available"

    raise ValueError(f"Unknown mode: {mode!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_availability.py -v`
Expected: all 5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add restock_notifier/availability.py tests/test_availability.py
git commit -m "feat: CSS-selector-based availability detection"
```

---

### Task 4: State persistence

**Files:**
- Create: `restock_notifier/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces:
  - `DEFAULT_ENTRY: dict` (status="unavailable", consecutive_errors=0, consecutive_unavailable_checks=0, stale_warned=False)
  - `load_state(state_path) -> dict`
  - `save_state(state_path, state: dict) -> None`
  - `get_entry(state: dict, product_id: str) -> dict`
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write failing tests**

`tests/test_state.py`:
```python
import json

from restock_notifier.state import DEFAULT_ENTRY, get_entry, load_state, save_state


def test_load_state_missing_file_returns_empty_dict(tmp_path):
    state = load_state(tmp_path / "state.json")
    assert state == {}


def test_save_then_load_round_trip(tmp_path):
    state_path = tmp_path / "state.json"
    data = {"product-a": {"status": "available", "consecutive_errors": 0,
                           "consecutive_unavailable_checks": 0, "stale_warned": False}}

    save_state(state_path, data)
    loaded = load_state(state_path)

    assert loaded == data


def test_save_state_writes_readable_json(tmp_path):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"a": 1})

    raw = state_path.read_text(encoding="utf-8")
    assert json.loads(raw) == {"a": 1}


def test_get_entry_returns_default_for_unknown_product():
    entry = get_entry({}, "unknown-id")
    assert entry == DEFAULT_ENTRY


def test_get_entry_does_not_mutate_default():
    state = {}
    entry = get_entry(state, "unknown-id")
    entry["status"] = "available"

    assert DEFAULT_ENTRY["status"] == "unavailable"


def test_get_entry_returns_existing_entry():
    state = {"known-id": {"status": "available", "consecutive_errors": 1,
                           "consecutive_unavailable_checks": 0, "stale_warned": True}}
    entry = get_entry(state, "known-id")
    assert entry["status"] == "available"
    assert entry["stale_warned"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'restock_notifier.state'`

- [ ] **Step 3: Implement `restock_notifier/state.py`**

```python
import json
from pathlib import Path

DEFAULT_ENTRY = {
    "status": "unavailable",
    "consecutive_errors": 0,
    "consecutive_unavailable_checks": 0,
    "stale_warned": False,
}


def load_state(state_path):
    path = Path(state_path)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state_path, state):
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def get_entry(state, product_id):
    return dict(state.get(product_id, DEFAULT_ENTRY))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_state.py -v`
Expected: all 6 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add restock_notifier/state.py tests/test_state.py
git commit -m "feat: JSON state persistence for product availability"
```

---

### Task 5: Telegram notifier

**Files:**
- Create: `restock_notifier/notifier.py`
- Test: `tests/test_notifier.py`

**Interfaces:**
- Produces:
  - `send_message(bot_token: str, chat_id: str, text: str) -> dict`
  - `format_restock_message(product_name: str, shop_name: str, url: str) -> str`
  - `format_down_message(product_name: str, shop_name: str) -> str`
  - `format_stale_message(product_name: str, shop_name: str) -> str`
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write failing tests**

`tests/test_notifier.py`:
```python
import pytest

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_notifier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'restock_notifier.notifier'`

- [ ] **Step 3: Implement `restock_notifier/notifier.py`**

```python
import requests

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_message(bot_token, chat_id, text):
    url = TELEGRAM_API_URL.format(token=bot_token)
    response = requests.post(
        url,
        data={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def format_restock_message(product_name, shop_name, url):
    return f"🟢 {product_name} ist wieder verfügbar bei {shop_name}!\n{url}"


def format_down_message(product_name, shop_name):
    return (
        f"⚠️ {shop_name} ({product_name}) ist seit mehreren Versuchen "
        f"nicht erreichbar."
    )


def format_stale_message(product_name, shop_name):
    return (
        f"🕵️ {product_name} bei {shop_name} ist schon ungewöhnlich lange "
        f"'ausverkauft' — evtl. hat sich die Shop-Seite geändert. "
        f"Bitte Selector in shops.json prüfen."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_notifier.py -v`
Expected: all 5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add restock_notifier/notifier.py tests/test_notifier.py
git commit -m "feat: Telegram notifier and message formatting"
```

---

### Task 6: HTTP fetcher with retries

**Files:**
- Create: `restock_notifier/fetch.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Produces:
  - `FetchError(Exception)`
  - `fetch_html_http(url: str, retries: int = 3, backoff_seconds: int = 2, session=None) -> str`
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write failing tests**

`tests/test_fetch.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fetch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'restock_notifier.fetch'`

- [ ] **Step 3: Implement `restock_notifier/fetch.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fetch.py -v`
Expected: all 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add restock_notifier/fetch.py tests/test_fetch.py
git commit -m "feat: HTTP fetcher with retry/backoff"
```

---

### Task 7: Playwright fetcher (fallback for JS-rendered shops)

**Files:**
- Create: `restock_notifier/fetch_playwright.py`
- Test: `tests/test_fetch_playwright.py`

**Interfaces:**
- Produces: `fetch_html_playwright(url: str, sync_playwright_factory=None) -> str`
- Consumes: nothing from earlier tasks. The real `playwright` package is only imported when `sync_playwright_factory` is not supplied, so unit tests don't require Playwright's browser binaries to be installed.

- [ ] **Step 1: Write failing tests**

`tests/test_fetch_playwright.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fetch_playwright.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'restock_notifier.fetch_playwright'`

- [ ] **Step 3: Implement `restock_notifier/fetch_playwright.py`**

```python
def fetch_html_playwright(url, sync_playwright_factory=None):
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
    return html
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fetch_playwright.py -v`
Expected: both tests PASSED (no Playwright browser install needed — the fake factory bypasses the real import)

- [ ] **Step 5: Commit**

```bash
git add restock_notifier/fetch_playwright.py tests/test_fetch_playwright.py
git commit -m "feat: Playwright fallback fetcher for JS-rendered shops"
```

---

### Task 8: Orchestration (`main.py`)

**Files:**
- Create: `restock_notifier/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes:
  - `restock_notifier.config.load_watchlist` (Task 2)
  - `restock_notifier.availability.determine_status` (Task 3)
  - `restock_notifier.state.load_state`, `save_state`, `get_entry` (Task 4)
  - `restock_notifier.notifier.send_message`, `format_restock_message`, `format_down_message`, `format_stale_message` (Task 5)
  - `restock_notifier.fetch.fetch_html_http`, `FetchError` (Task 6)
  - `restock_notifier.fetch_playwright.fetch_html_playwright` (Task 7)
- Produces:
  - `ERROR_ALERT_THRESHOLD = 3`, `STALE_THRESHOLD = 480` (module constants)
  - `fetch_for_product(product: dict) -> str` (dispatches to HTTP or Playwright based on `product["render"]`)
  - `process_product(product: dict, state: dict, send_fn, fetch_fn) -> None` (mutates `state` in place)
  - `run(products_path, shops_path, state_path, send_fn, fetch_fn=fetch_for_product) -> None`
  - `build_send_fn(bot_token: str, chat_id: str, dry_run: bool) -> callable`
  - `main() -> None` (CLI entry point, reads `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` env vars and `--dry-run` flag)

- [ ] **Step 1: Write failing tests for `process_product`**

`tests/test_main.py`:
```python
import json

import pytest

from restock_notifier.fetch import FetchError
from restock_notifier.main import ERROR_ALERT_THRESHOLD, STALE_THRESHOLD, process_product, run
from restock_notifier.state import get_entry

PRODUCT = {
    "id": "op17-display-fantasiacards",
    "name": "One Piece OP17 Display",
    "url": "https://fantasiacards.de/products/one-piece-card-game-op17-display-eng",
    "shop_id": "fantasiacards",
    "selector": 'button[name="add"]:not([disabled])',
    "mode": "found_means_available",
    "render": "http",
}

AVAILABLE_HTML = '<button type="submit" name="add">In den Warenkorb</button>'
SOLD_OUT_HTML = '<button type="submit" name="add" disabled="disabled">Ausverkauft</button>'


def make_fetch_fn(html_or_error):
    def fetch_fn(product):
        if isinstance(html_or_error, Exception):
            raise html_or_error
        return html_or_error
    return fetch_fn


def test_process_product_sends_restock_message_on_transition():
    state = {"op17-display-fantasiacards": {
        "status": "unavailable", "consecutive_errors": 0,
        "consecutive_unavailable_checks": 5, "stale_warned": False,
    }}
    sent = []

    process_product(PRODUCT, state, sent.append, make_fetch_fn(AVAILABLE_HTML))

    assert len(sent) == 1
    assert "wieder verfügbar" in sent[0]
    entry = state["op17-display-fantasiacards"]
    assert entry["status"] == "available"
    assert entry["consecutive_unavailable_checks"] == 0
    assert entry["stale_warned"] is False


def test_process_product_no_message_when_still_unavailable():
    state = {}
    sent = []

    process_product(PRODUCT, state, sent.append, make_fetch_fn(SOLD_OUT_HTML))

    assert sent == []
    entry = state["op17-display-fantasiacards"]
    assert entry["status"] == "unavailable"
    assert entry["consecutive_unavailable_checks"] == 1


def test_process_product_no_message_when_still_available():
    state = {"op17-display-fantasiacards": {
        "status": "available", "consecutive_errors": 0,
        "consecutive_unavailable_checks": 0, "stale_warned": False,
    }}
    sent = []

    process_product(PRODUCT, state, sent.append, make_fetch_fn(AVAILABLE_HTML))

    assert sent == []


def test_process_product_alerts_after_threshold_consecutive_errors():
    state = {}
    sent = []
    fetch_fn = make_fetch_fn(FetchError("boom"))

    for _ in range(ERROR_ALERT_THRESHOLD):
        process_product(PRODUCT, state, sent.append, fetch_fn)

    assert len(sent) == 1
    assert "nicht erreichbar" in sent[0]
    assert state["op17-display-fantasiacards"]["consecutive_errors"] == ERROR_ALERT_THRESHOLD


def test_process_product_does_not_alert_before_threshold():
    state = {}
    sent = []
    fetch_fn = make_fetch_fn(FetchError("boom"))

    for _ in range(ERROR_ALERT_THRESHOLD - 1):
        process_product(PRODUCT, state, sent.append, fetch_fn)

    assert sent == []


def test_process_product_resets_error_count_on_success():
    state = {"op17-display-fantasiacards": {
        "status": "unavailable", "consecutive_errors": 2,
        "consecutive_unavailable_checks": 0, "stale_warned": False,
    }}
    sent = []

    process_product(PRODUCT, state, sent.append, make_fetch_fn(SOLD_OUT_HTML))

    assert state["op17-display-fantasiacards"]["consecutive_errors"] == 0


def test_process_product_sends_stale_warning_at_threshold():
    state = {"op17-display-fantasiacards": {
        "status": "unavailable", "consecutive_errors": 0,
        "consecutive_unavailable_checks": STALE_THRESHOLD - 1, "stale_warned": False,
    }}
    sent = []

    process_product(PRODUCT, state, sent.append, make_fetch_fn(SOLD_OUT_HTML))

    assert len(sent) == 1
    assert "shops.json" in sent[0]
    assert state["op17-display-fantasiacards"]["stale_warned"] is True


def test_process_product_does_not_repeat_stale_warning():
    state = {"op17-display-fantasiacards": {
        "status": "unavailable", "consecutive_errors": 0,
        "consecutive_unavailable_checks": STALE_THRESHOLD + 10, "stale_warned": True,
    }}
    sent = []

    process_product(PRODUCT, state, sent.append, make_fetch_fn(SOLD_OUT_HTML))

    assert sent == []


def test_run_end_to_end_with_fakes(tmp_path):
    shops_path = tmp_path / "shops.json"
    products_path = tmp_path / "products.json"
    state_path = tmp_path / "state.json"

    shops_path.write_text(json.dumps({"fantasiacards": {"type": "shopify"}}), encoding="utf-8")
    products_path.write_text(json.dumps([{
        "id": "op17-display-fantasiacards",
        "name": "One Piece OP17 Display",
        "shop": "fantasiacards",
        "url": "https://fantasiacards.de/products/one-piece-card-game-op17-display-eng",
    }]), encoding="utf-8")

    sent = []
    run(
        products_path, shops_path, state_path,
        send_fn=sent.append,
        fetch_fn=make_fetch_fn(AVAILABLE_HTML),
    )

    assert len(sent) == 1
    saved_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved_state["op17-display-fantasiacards"]["status"] == "available"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'restock_notifier.main'`

- [ ] **Step 3: Implement `restock_notifier/main.py`**

```python
import argparse
import os
from pathlib import Path

from restock_notifier.availability import determine_status
from restock_notifier.config import load_watchlist
from restock_notifier.fetch import FetchError, fetch_html_http
from restock_notifier.fetch_playwright import fetch_html_playwright
from restock_notifier.notifier import (
    format_down_message,
    format_restock_message,
    format_stale_message,
    send_message,
)
from restock_notifier.state import get_entry, load_state, save_state

ERROR_ALERT_THRESHOLD = 3
STALE_THRESHOLD = 480  # ~5 Tage bei 15-Minuten-Takt


def fetch_for_product(product):
    if product["render"] == "playwright":
        return fetch_html_playwright(product["url"])
    return fetch_html_http(product["url"])


def process_product(product, state, send_fn, fetch_fn):
    entry = get_entry(state, product["id"])

    try:
        html = fetch_fn(product)
    except FetchError:
        entry["consecutive_errors"] += 1
        if entry["consecutive_errors"] == ERROR_ALERT_THRESHOLD:
            send_fn(format_down_message(product["name"], product["shop_id"]))
        state[product["id"]] = entry
        return

    entry["consecutive_errors"] = 0
    new_status = determine_status(html, product["selector"], product["mode"])

    if entry["status"] == "unavailable" and new_status == "available":
        send_fn(format_restock_message(product["name"], product["shop_id"], product["url"]))

    if new_status == "unavailable":
        entry["consecutive_unavailable_checks"] += 1
    else:
        entry["consecutive_unavailable_checks"] = 0
        entry["stale_warned"] = False

    if entry["consecutive_unavailable_checks"] >= STALE_THRESHOLD and not entry["stale_warned"]:
        send_fn(format_stale_message(product["name"], product["shop_id"]))
        entry["stale_warned"] = True

    entry["status"] = new_status
    state[product["id"]] = entry


def run(products_path, shops_path, state_path, send_fn, fetch_fn=fetch_for_product):
    watchlist = load_watchlist(products_path, shops_path)
    state = load_state(state_path)

    for product in watchlist:
        process_product(product, state, send_fn, fetch_fn)

    save_state(state_path, state)


def build_send_fn(bot_token, chat_id, dry_run):
    if dry_run:
        def send_fn(text):
            print(f"[DRY RUN] {text}")
        return send_fn

    def send_fn(text):
        send_message(bot_token, chat_id, text)
    return send_fn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not args.dry_run and (not bot_token or not chat_id):
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN und TELEGRAM_CHAT_ID müssen gesetzt sein "
            "(oder --dry-run verwenden)"
        )

    root = Path(__file__).resolve().parent.parent
    send_fn = build_send_fn(bot_token, chat_id, args.dry_run)
    run(root / "products.json", root / "shops.json", root / "state.json", send_fn)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: all 9 tests PASSED

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests across all modules PASSED

- [ ] **Step 6: Commit**

```bash
git add restock_notifier/main.py tests/test_main.py
git commit -m "feat: orchestration entry point with error/stale alerting"
```

---

### Task 9: Real config files, GitHub Actions workflow, and setup docs

**Files:**
- Create: `shops.json`
- Create: `products.json`
- Create: `state.json`
- Create: `.github/workflows/restock-check.yml`
- Create: `SETUP.md`

**Interfaces:**
- Consumes: `restock_notifier.main` (Task 8) as the workflow's execution entry point.
- Produces: a working GitHub Actions schedule once the repo is pushed to GitHub and secrets are set (manual steps documented in `SETUP.md`).

- [ ] **Step 1: Create the real `shops.json`**

```json
{
  "fantasiacards": {
    "type": "shopify"
  }
}
```

- [ ] **Step 2: Create the real `products.json`**

```json
[
  {
    "id": "op17-display-fantasiacards",
    "name": "One Piece OP17 Display",
    "shop": "fantasiacards",
    "url": "https://fantasiacards.de/products/one-piece-card-game-op17-display-eng"
  }
]
```

- [ ] **Step 3: Create the initial `state.json`**

```json
{}
```

- [ ] **Step 4: Create `.github/workflows/restock-check.yml`**

```yaml
name: TCG Restock Check

on:
  schedule:
    - cron: "*/15 * * * *"
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Install Playwright browser
        run: playwright install --with-deps chromium

      - name: Run restock check
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python -m restock_notifier.main

      - name: Commit updated state
        run: |
          git config user.name "restock-bot"
          git config user.email "actions@users.noreply.github.com"
          git add state.json
          git diff --staged --quiet || git commit -m "chore: update state.json [skip ci]"
          git push
```

- [ ] **Step 5: Write `SETUP.md`**

```markdown
# Setup

## 1. Telegram-Bot erstellen

1. Öffne Telegram, suche `@BotFather`, sende `/newbot` und folge den Anweisungen.
2. BotFather gibt dir einen **Bot-Token** (Format `123456789:ABC...`). Kopieren.
3. Suche deinen neuen Bot in Telegram und sende ihm eine beliebige Nachricht
   (z.B. "hi") — sonst kann er dir nicht antworten.
4. Rufe im Browser auf (TOKEN ersetzen):
   `https://api.telegram.org/botTOKEN/getUpdates`
5. In der JSON-Antwort steht `"chat":{"id": 123456789, ...}` — das ist deine
   **Chat-ID**.

## 2. GitHub-Repository

1. Erstelle ein neues (privates) GitHub-Repository und pushe dieses Projekt dorthin.
2. Unter Settings → Secrets and variables → Actions → "New repository secret"
   zwei Secrets anlegen:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

## 3. Lokaler Test (optional, ohne Telegram-Zugangsdaten)

```bash
pip install -r requirements-dev.txt
python -m restock_notifier.main --dry-run
```

Gibt Nachrichten auf der Konsole statt via Telegram aus — gut, um die
Konfiguration zu prüfen, bevor der Bot eingerichtet ist.

## 4. Workflow manuell testen

Nach dem Push: im GitHub-Repo unter "Actions" → "TCG Restock Check" →
"Run workflow" — löst einen sofortigen Testlauf aus, ohne auf den
15-Minuten-Cron zu warten.

## 5. Neue Produkte hinzufügen

Trage in `products.json` einen neuen Eintrag ein (siehe bestehendes Beispiel).
Falls der Shop noch nicht in `shops.json` steht, meinen Selector für den
neuen Shop erst ermitteln (bei Shopify-Shops reicht meist `"type": "shopify"`).
```

- [ ] **Step 6: Run the full test suite once more to confirm nothing broke**

Run: `pytest -v`
Expected: all tests PASSED

- [ ] **Step 7: Commit**

```bash
git add shops.json products.json state.json .github/workflows/restock-check.yml SETUP.md
git commit -m "feat: seed config, GitHub Actions workflow, setup docs"
```

---

## Manual Follow-Ups (not automatable by an agent)

- Create the Telegram bot via `@BotFather` and note the token + chat ID (`SETUP.md` step 1).
- Create the GitHub repository and push this project to it.
- Add `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` as GitHub Actions secrets.
- Trigger one manual `workflow_dispatch` run to confirm the Telegram message actually arrives.
