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
