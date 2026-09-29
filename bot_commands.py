import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
AUTHORIZED_CHAT_IDS = {"2020881944"}
CURRENT_FILE = Path("current_jobs.json")
STATE_FILE = Path("bot_state.json")

# Telegram sendMessage accepts messages up to 4096 characters.
# We deliberately stay below the hard limit to leave room for the Part X/Y header.
TELEGRAM_LIMIT = 4096
SAFE_PART_LIMIT = 3800

SOURCE_ORDER = [
    "leonardo",
    "inpa",
    "eutalia",
    "consip",
    "sogei",
    "agid",
    "invitalia",
    "cdp",
]


def telegram_api(method, data=None):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    body = urllib.parse.urlencode(data or {}).encode("utf-8") if data else None
    request = urllib.request.Request(
        url,
        data=body,
        method="POST" if body else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(chat_id, text):
    if len(text) > TELEGRAM_LIMIT:
        raise ValueError(
            f"Messaggio Telegram troppo lungo: {len(text)} caratteri"
        )

    telegram_api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        },
    )


def load_current_jobs():
    try:
        return json.loads(CURRENT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_check": "Non disponibile", "sources": {}}


def build_status(data):
    lines = [
        "🤖 PIC JOB FINDER - STATO",
        "",
        f"🕐 Ultimo controllo: {data.get('last_check', 'Non disponibile')}",
        "",
    ]

    total = 0
    sources = data.get("sources", {})

    for key in SOURCE_ORDER:
        source = sources.get(
            key,
            {"label": key, "status": "unavailable", "items": []},
        )
        items = source.get("items", [])
        label = source.get("label", key)

        if source.get("status") == "ok":
            count = len(items)
            total += count
            lines.append(f"✅ {label} — {count}")
        else:
            lines.append(f"⚠️ {label} — non disponibile")

    lines.extend(["", f"📊 Totale annunci: {total}"])
    return "\n".join(lines)


def make_job_block(item):
    """Title + URL are one indivisible block."""
    title = item.get("title", "Titolo non disponibile").strip()
    url = item.get("url", "").strip()

    if url:
        return f"• {title}\n  {url}\n"
    return f"• {title}\n"


def build_summary_parts(data):
    """
    Build the full summary in multiple Telegram messages.

    Crucially, a job block (title + URL) is never split. Before adding it to the
    current part, the complete block is measured. If it would exceed the safe
    limit, a new message part is started and the whole job goes there.
    """
    last_check = data.get("last_check", "Non disponibile")
    sources = data.get("sources", {})

    parts = []
    current = ""
    total = 0

    def flush():
        nonlocal current
        if current.strip():
            parts.append(current.rstrip())
            current = ""

    for key in SOURCE_ORDER:
        source = sources.get(
            key,
            {"label": key, "status": "unavailable", "items": []},
        )
        label = source.get("label", key)
        status = source.get("status")
        items = source.get("items", [])

        if status != "ok":
            block = f"⚠️ {label.upper()} — controllo non disponibile\n\n"
            if current and len(current) + len(block) > SAFE_PART_LIMIT:
                flush()
            current += block
            continue

        total += len(items)
        source_header = f"{label.upper()} — {len(items)} annunci\n"

        # Avoid leaving an isolated source heading at the bottom of a part.
        # If there is at least one job, reserve enough room for the first full
        # title+URL block as well as the heading.
        first_job = make_job_block(items[0]) if items else ""
        minimum_source_block = source_header + first_job

        if current and len(current) + len(minimum_source_block) > SAFE_PART_LIMIT:
            flush()

        current += source_header

        if not items:
            current += "\n"
            continue

        for item in items:
            job_block = make_job_block(item)

            # Title + link are tested and appended as one indivisible unit.
            if current and len(current) + len(job_block) > SAFE_PART_LIMIT:
                flush()
                # Repeat the source heading so the next part stays understandable.
                current = f"{label.upper()} — continua\n"

            # An individual title+URL should never realistically exceed the
            # Telegram limit. If it does, keep the URL and shorten only the title,
            # never split the pair across messages.
            if len(current) + len(job_block) > SAFE_PART_LIMIT:
                url = item.get("url", "").strip()
                overhead = len(current) + len("• …\n  \n") + len(url)
                available_title = max(40, SAFE_PART_LIMIT - overhead)
                title = item.get("title", "Titolo non disponibile").strip()
                shortened = title[: max(1, available_title - 1)] + "…"
                job_block = (
                    f"• {shortened}\n  {url}\n"
                    if url
                    else f"• {shortened}\n"
                )

            current += job_block

        current += "\n"

    # Keep the total in the final part. If it does not fit, start a new part.
    footer = f"📊 Totale: {total} annunci\n\n🤖 Pic_Job_Finder_Bot"
    if current and len(current) + len(footer) > SAFE_PART_LIMIT:
        flush()
    current += footer
    flush()

    if not parts:
        parts = [footer]

    # Add the global header after knowing the final number of parts.
    final_parts = []
    part_count = len(parts)

    for index, content in enumerate(parts, start=1):
        header = (
            "📋 PIC JOB FINDER - RIEPILOGO\n"
            f"Parte {index}/{part_count}\n"
            f"🕐 Ultimo controllo: {last_check}\n\n"
        )
        message = header + content

        # SAFE_PART_LIMIT leaves ample margin, but fail clearly rather than
        # silently truncating if a future formatting change breaks the budget.
        if len(message) > TELEGRAM_LIMIT:
            raise ValueError(
                f"Parte {index}/{part_count} troppo lunga: {len(message)} caratteri"
            )

        final_parts.append(message)

    return final_parts


HELP_TEXT = """🤖 PIC JOB FINDER

Comandi disponibili:

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
    STATE_FILE.write_text(
        json.dumps({"last_update_id": last_update_id}, indent=2),
        encoding="utf-8",
    )


def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN non configurato")

    state = load_state()
    last_update_id = state.get("last_update_id", 0)

    result = telegram_api(
        "getUpdates",
        {
            "offset": last_update_id + 1,
            "timeout": 0,
            "allowed_updates": json.dumps(["message"]),
        },
    )

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
                send_message(chat_id, part)

    save_state(last_update_id)


if __name__ == "__main__":
    main()
