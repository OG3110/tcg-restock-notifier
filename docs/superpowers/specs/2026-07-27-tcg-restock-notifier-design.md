# TCG Restock Notifier — Design

**Datum:** 2026-07-27
**Status:** Genehmigt

## Ziel

Ein automatisierter Watcher, der ausgewählte One-Piece- und Pokémon-TCG-Produktseiten
(deutsche/europäische Online-Shops, explizit **ohne** Amazon und Media Markt) periodisch
auf Wiederverfügbarkeit prüft und den Nutzer per Telegram benachrichtigt, sobald ein
Produkt vom Status "ausverkauft" zu "verfügbar" wechselt.

## Architektur

```
GitHub Actions Cron (alle 15 Min)
        │
        ▼
Python-Script liest products.json + shops.json
        │
        ▼
Für jedes Produkt: HTTP-Request → CSS-Selektor auswerten → Status (verfügbar/ausverkauft)
        │
        ▼
Vergleich mit letztem bekannten Status (state.json)
        │
        ▼
Bei Wechsel "ausverkauft → verfügbar": Telegram-Nachricht senden
        │
        ▼
state.json aktualisieren & zurück ins Repo committen
```

**Warum GitHub Actions:** kostenlos, cron-fähig bis auf 15-Minuten-Takt, kein Server-Betrieb
nötig. `products.json` dient gleichzeitig als Verwaltungsoberfläche (auch per GitHub-App am
Handy editierbar). `state.json` im Repo ersetzt eine externe Datenbank.

**Tech-Stack:** Python, `requests` + `BeautifulSoup` (`soupsieve`-CSS-Selektoren) als
Standardweg. Für Shops, die serverseitig kein vollständiges HTML liefern (JS-gerendert),
Fallback auf Playwright (Headless-Browser) — pro Shop einzeln aktivierbar über
`"render": "playwright"` in `shops.json`.

## Konfiguration

### `shops.json` — Shop-Definitionen

```json
{
  "fantasiacards": {
    "type": "shopify",
    "selector": "button[name=\"add\"]:not([disabled])",
    "mode": "found_means_available"
  },
  "sapphire-cards": {
    "selector": ".stock-status--sold-out",
    "mode": "found_means_unavailable"
  }
}
```

- `type: "shopify"` ist eine Kurzform, die automatisch den Standard-Selektor
  `button[name="add"]:not([disabled])` (verifiziert live an fantasiacards.de) verwendet —
  deckt vermutlich die Mehrzahl der Shops ab, da viele deutsche TCG-Shops auf Shopify
  laufen. Für Shops mit anderem System wird `selector` + `mode` individuell festgelegt.
- `mode`: `found_means_available` (Selektor matcht ein Element, das nur bei Verfügbarkeit
  existiert/aktiv ist, z.B. aktiver Warenkorb-Button) oder `found_means_unavailable`
  (Selektor matcht ein "Ausverkauft"-Badge o.ä.).
- `render`: optional, `"playwright"` für JS-gerenderte Shops (Default: einfacher HTTP-Request).

### `products.json` — Watchlist (vom Nutzer gepflegt)

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

Neue Produkte werden vom Nutzer direkt in dieser Datei ergänzt (Commit ins Repo).

### `state.json` — automatisch verwaltet

```json
{ "op17-display-fantasiacards": "unavailable" }
```

Wird bei jedem Lauf vom Script aktualisiert und zurückcommittet. Nicht von Hand editieren.

## Erkennungslogik

1. Für jedes Produkt in `products.json`: zugehörigen Shop-Eintrag aus `shops.json` laden.
2. Seite abrufen (HTTP oder Playwright, je nach `render`).
3. CSS-Selektor auswerten, Status gemäß `mode` ableiten (`available` / `unavailable`).
4. Mit `state.json` vergleichen:
   - `unavailable → available`: Telegram-Nachricht senden, State aktualisieren.
   - `available → unavailable`: nur State aktualisieren, keine Nachricht.
   - unverändert: nichts tun.

## Fehlerbehandlung

- **Timeout/Verbindungsfehler:** Retry (2–3 Versuche). Bei anhaltendem Fehler über mehrere
  Läufe hinweg (z.B. 3 aufeinanderfolgende Cron-Durchläufe) eine einmalige
  "Shop X nicht erreichbar"-Nachricht — kein Spam bei jedem einzelnen Fehlversuch.
- **Selektor liefert kein Ergebnis:** einmalige Warnung "Selector für Produkt Y liefert
  kein Ergebnis, bitte prüfen" (deutet meist auf Theme-Änderung des Shops hin).
- **Bot-Blocking (403/429, Cloudflare o.ä.):** wird geloggt; spätere Gegenmaßnahmen
  (realistischer User-Agent, Header-Rotation) sind ein möglicher Folgeschritt, kein
  Teil des initialen Scopes.

## Benachrichtigungsformat (Telegram)

```
🟢 One Piece OP17 Display ist wieder verfügbar bei FantasiaCards!
https://fantasiacards.de/products/one-piece-card-game-op17-display-eng
```

## Setup-Voraussetzungen (Teil der Implementierung)

1. Telegram-Bot über @BotFather erstellen, Bot-Token erhalten.
2. Eigene Chat-ID ermitteln (z.B. via `getUpdates`-Endpoint nach erster Nachricht an den Bot).
3. Bot-Token + Chat-ID als GitHub Actions Secrets hinterlegen (`TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_CHAT_ID`).
4. GitHub-Repository für dieses Projekt anlegen (aktuell noch kein Git-Repo vorhanden).

## Out of Scope (für spätere Iterationen)

- Automatische Erkennung/Vorschlag neuer Produkte über Kategorie-Seiten.
- Verwaltung der Watchlist per Telegram-Bot-Befehl statt Config-Datei.
- Anti-Bot-Umgehung (Header-Rotation, Proxies) über einfache Retries hinaus.
- Amazon, Media Markt (explizit ausgeschlossen).
