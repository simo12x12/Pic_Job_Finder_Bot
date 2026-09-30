import html
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
AUTHORIZED_CHAT_IDS = {"2020881944"}
CURRENT_FILE = Path("current_jobs.json")
STATE_FILE = Path("bot_state.json")

TELEGRAM_LIMIT = 4096
SAFE_PART_LIMIT = 3800

SOURCE_ORDER = [
    "leonardo", "inpa", "eutalia", "consip", "sogei", "agid", "invitalia",
    "ipzs", "pagopa", "rome_technopole", "ama_roma", "bmti", "sace", "gse",
    "terna", "acea", "italo", "fincantieri", "anci", "ifel", "sna",
    "tagliacarne", "brodolini", "fondazione_sud", "enav", "sport_salute",
    "fs", "autostrade", "infocamere", "formez", "sviluppo_lavoro", "capcoe",
    "unioncamere", "agenas", "ice", "inapp", "cdp",
]


def telegram_api(method, data=None):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    body = urllib.parse.urlencode(data or {}).encode("utf-8") if data else None
    request = urllib.request.Request(url, data=body, method="POST" if body else "GET")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(chat_id, text, parse_mode=None):
    if len(text) > TELEGRAM_LIMIT:
        raise ValueError(f"Messaggio Telegram troppo lungo: {len(text)} caratteri")
    data = {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    if parse_mode:
        data["parse_mode"] = parse_mode
    telegram_api("sendMessage", data)


def load_current_jobs():
    try:
        return json.loads(CURRENT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_check": "Non disponibile", "sources": {}}


def build_status(data):
    # Intentionally unchanged from the previous version.
    lines = [
        "PIC JOB FINDER - STATO", "",
        f"{data.get('last_check', 'Non disponibile')}", "",
    ]
    total = 0
    sources = data.get("sources", {})
    for key in SOURCE_ORDER:
        source = sources.get(key, {"label": key, "status": "unavailable", "items": []})
        items = source.get("items", [])
        label = source.get("label", key)
        if source.get("status") == "ok":
            count = len(items)
            total += count
            lines.append(f"✅ {label} — {count}")
        else:
            lines.append(f"⚠️ {label} — non disponibile")
    lines.extend(["", f"Totale: {total} annunci"])
    return "\n".join(lines)


def clean_title(title):
    title = html.unescape(str(title or "Titolo non disponibile"))
    title = " ".join(title.split()).strip(" :-")
    # Source-specific cosmetic prefixes, without inventing a different job title.
    if title.startswith(":"):
        title = title[1:].strip()
    return title.upper()


def make_job_block(item):
    """Compact HTML title + clickable link, kept as one indivisible block."""
    title = html.escape(clean_title(item.get("title")))
    url = str(item.get("url", "")).strip()
    if url:
        safe_url = html.escape(url, quote=True)
        return f"• <b>{title}</b>\n  <a href=\"{safe_url}\">Link</a>\n"
    return f"• <b>{title}</b>\n"


def source_header(label, status, count=0):
    safe = html.escape(str(label).upper())
    if status != "ok":
        return f"🟡 <b>{safe}</b>\n"
    dot = "⚪" if count == 0 else "🔵"
    return f"{dot} <b>{safe}</b> · {count} annunci\n"


def build_summary_parts(data):
    """Build silent multipart summary. No Part X/Y and no '<source> continua'."""
    last_check = html.escape(str(data.get("last_check", "Non disponibile")))
    sources = data.get("sources", {})
    parts = []
    current = (
        "<b>PIC JOB FINDER - RIEPILOGO</b>\n"
        f"{last_check}\n\n"
    )
    total = 0

    def flush():
        nonlocal current
        if current.strip():
            parts.append(current.rstrip())
            current = ""

    for key in SOURCE_ORDER:
        source = sources.get(key, {"label": key, "status": "unavailable", "items": []})
        label = source.get("label", key)
        status = source.get("status")
        items = source.get("items", [])
        total += len(items) if status == "ok" else 0
        header = source_header(label, status, len(items))

        # If source starts in a fresh Telegram message, repeat only its real heading,
        # never a 'continua' marker.
        first = make_job_block(items[0]) if status == "ok" and items else ""
        if current and len(current) + len(header) + len(first) > SAFE_PART_LIMIT:
            flush()
        current += header

        if status != "ok" or not items:
            current += "\n"
            continue

        for item in items:
            block = make_job_block(item)
            if current and len(current) + len(block) > SAFE_PART_LIMIT:
                flush()
                current = source_header(label, status, len(items))
            if len(current) + len(block) > SAFE_PART_LIMIT:
                # Very long source titles: shorten display text only. URL remains intact.
                title = clean_title(item.get("title"))
                url = str(item.get("url", "")).strip()
                reserve = len(current) + len(url) + 80
                available = max(80, SAFE_PART_LIMIT - reserve)
                title = html.escape(title[:available].rstrip() + "…")
                if url:
                    block = f"• <b>{title}</b>\n  <a href=\"{html.escape(url, quote=True)}\">Link</a>\n"
                else:
                    block = f"• <b>{title}</b>\n"
            current += block
        current += "\n"

    footer = f"<b>Totale: {total} annunci</b>"
    if current and len(current) + len(footer) > SAFE_PART_LIMIT:
        flush()
    current += footer
    flush()
    return parts or [footer]


HELP_TEXT = """PIC JOB FINDER

/riepilogo
Mostra tutti gli annunci dell'ultimo controllo, dividendoli automaticamente in più messaggi se necessario.

/status
Mostra stato e conteggi delle fonti.

/help
Mostra questo messaggio."""


def load_state():
    if not STATE_FILE.exists():
        return {"last_update_id": 0}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_update_id": 0}


def save_state(last_update_id):
    STATE_FILE.write_text(json.dumps({"last_update_id": last_update_id}, indent=2), encoding="utf-8")


def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN non configurato")
    state = load_state()
    last_update_id = state.get("last_update_id", 0)
    result = telegram_api("getUpdates", {
        "offset": last_update_id + 1,
        "timeout": 0,
        "allowed_updates": json.dumps(["message"]),
    })
    current_jobs = load_current_jobs()
    for update in result.get("result", []):
        last_update_id = max(last_update_id, update.get("update_id", 0))
        message = update.get("message") or {}
        chat_id = str((message.get("chat") or {}).get("id", ""))
        text = (message.get("text") or "").split("@", 1)[0].strip().lower()
        if chat_id not in AUTHORIZED_CHAT_IDS:
            continue
        if text == "/help":
            send_message(chat_id, HELP_TEXT)
        elif text == "/status":
            send_message(chat_id, build_status(current_jobs))
        elif text == "/riepilogo":
            for part in build_summary_parts(current_jobs):
                send_message(chat_id, part, parse_mode="HTML")
    save_state(last_update_id)


if __name__ == "__main__":
    main()
