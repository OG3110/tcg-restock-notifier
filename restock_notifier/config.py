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
