import argparse
import os
import sys
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


def run(products_path, shops_path, state_path, send_fn, fetch_fn=fetch_for_product, persist_state=True):
    watchlist = load_watchlist(products_path, shops_path)
    state = load_state(state_path)

    for product in watchlist:
        try:
            process_product(product, state, send_fn, fetch_fn)
        except Exception as exc:
            print(f"Error processing product {product['id']}: {exc}", file=sys.stderr)

    if persist_state:
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
    run(
        root / "products.json",
        root / "shops.json",
        root / "state.json",
        send_fn,
        persist_state=not args.dry_run,
    )


if __name__ == "__main__":
    main()
