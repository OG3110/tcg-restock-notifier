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
