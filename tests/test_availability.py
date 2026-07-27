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
