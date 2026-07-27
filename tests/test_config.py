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
