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
