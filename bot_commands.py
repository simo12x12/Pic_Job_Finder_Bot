import json
import re
from pathlib import Path

CURRENT_FILE = Path("current_jobs.json")
SAFE_PART_LIMIT = 3800


def normalize(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def load_current():
    if not CURRENT_FILE.exists():
        return {"sources": {}}
    return json.loads(CURRENT_FILE.read_text(encoding="utf-8"))


def source_matches(source_key, source_data, query):
    q = normalize(query).lower().replace("_", " ")
    key = source_key.lower().replace("_", " ")
    label = normalize(source_data.get("label")).lower()
    return q in {key, label} or q == key.replace(" ", "") or q == label.replace(" ", "")


def find_source(sources, query):
    exact = [(k, v) for k, v in sources.items() if source_matches(k, v, query)]
    if exact:
        return exact[0]
    q = normalize(query).lower()
    partial = [(k, v) for k, v in sources.items() if q in k.lower() or q in normalize(v.get("label")).lower()]
    return partial[0] if len(partial) == 1 else None


def job_matches(item, field, query):
    q = normalize(query).lower()
    if not q:
        return True
    if field == "localita":
        return q in normalize(item.get("location")).lower()
    if field == "lavoro":
        return q in normalize(item.get("title")).lower()
    return q in (normalize(item.get("title")) + " " + normalize(item.get("location"))).lower()


def build_database_text(args):
    data = load_current()
    sources = data.get("sources", {})
    args = normalize(args)
    if not args:
        lines = ["DATABASE - POSIZIONI APERTE", ""]
        for _, src in sources.items():
            items = src.get("items", [])
            if items:
                lines.append(f"{normalize(src.get('label'))}: {len(items)}")
        return "\n".join(lines).rstrip()

    tokens = args.split()
    source = find_source(sources, tokens[0])
    # Support labels made of multiple words, e.g. "ama roma" / "rome technopole".
    consumed = 1
    if source is None:
        for n in range(min(4, len(tokens)), 1, -1):
            candidate = find_source(sources, " ".join(tokens[:n]))
            if candidate:
                source, consumed = candidate, n
                break
    if source is None:
        return "Fonte non trovata. Usa /database oppure /database <fonte>."

    source_key, src = source
    rest = tokens[consumed:]
    field = None
    query = ""
    if rest and rest[0].lower() in {"localita", "località", "lavoro"}:
        field = "localita" if rest[0].lower() in {"localita", "località"} else "lavoro"
        query = " ".join(rest[1:])
    else:
        query = " ".join(rest)

    items = [item for item in src.get("items", []) if job_matches(item, field, query)]
    label = normalize(src.get("label")) or source_key
    lines = [f"DATABASE - {label.upper()}"]
    if query:
        lines += [f"Filtro {field or 'ricerca'}: {query.upper()}"]
    lines.append("")
    if not items:
        lines.append("Nessuna posizione aperta trovata.")
        return "\n".join(lines)
    for item in items:
        lines.append(normalize(item.get("title")).upper())
        location = normalize(item.get("location"))
        if location:
            lines.append(location)
        lines.append(normalize(item.get("url")))
        lines.append("")
    return "\n".join(lines).rstrip()


def split_message(text, limit=SAFE_PART_LIMIT):
    parts, current = [], ""
    for block in text.split("\n\n"):
        candidate = block if not current else current + "\n\n" + block
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                parts.append(current)
            current = block
    if current:
        parts.append(current)
    return parts


def handle_database_command(message_text):
    """Return Telegram-ready message parts for /database commands."""
    text = normalize(message_text)
    args = re.sub(r"^/database(?:@\w+)?\s*", "", text, flags=re.I)
    return split_message(build_database_text(args))


# Integration hook for an existing Telegram command dispatcher:
# if command == "/database":
#     for part in handle_database_command(message_text):
#         send_telegram(chat_id, part)
