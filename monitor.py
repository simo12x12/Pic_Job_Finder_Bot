import html
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
AUTHORIZED_CHAT_IDS = ["2020881944"]
SEEN_FILE = Path("seen_jobs.json")
ROME = ZoneInfo("Europe/Rome")

# ---------- URLs ----------
LEONARDO_ENDPOINT = "https://leonardocompany.wd3.myworkdayjobs.com/wday/cxs/leonardocompany/LeonardoCareerSite/jobs"
INPA_ENDPOINT = "https://portale.inpa.gov.it/concorsi-smart/api/concorso-public-area/search-better"
EUTALIA_URL = "https://www.eutalia.eu/selezione-personale-ed-esperti/"
CONSIP_URL = "https://www.consip.it/lavora-con-noi/posizioni?field_pos_stato_value=All&page=0"
SOGEI_URL = "https://www.sogei.it/it/sogei-homepage/lavora-con-noi/avvisi-di-selezione-e-invio-candidature.html"
PRESIDENZA_URL = "https://presidenza.governo.it/AmministrazioneTrasparente/BandiConcorso/index.html"

LEONARDO_FACETS = {
    "locationCountry": ["8cd04a563fd94da7b06857a79faaf815"],
    "jobFamilyGroup": [
        "8f7876e90e9c0101f751f430c4290000",
        "8f7876e90e9c0101f751e65634a60000",
    ],
}

INPA_BASE_PAYLOAD = {
    "text": "", "categoriaId": None, "regioneId": None,
    "status": ["OPEN"], "settoreId": None,
    "dateFrom": None, "dateTo": None, "enteRiferimentoName": "",
    "livelliAnzianitaIds": None, "provinciaCodice": None,
    "salaryMax": None, "salaryMin": None, "tipoImpiegoId": None,
}
INPA_COMMUNICATION_SECTOR = "b078865c126040558601"
INPA_SEARCH_TERMS = ["marketing", "comunicazione istituzionale"]
PRESIDENZA_KEYWORDS = ["comunicazione", "communication", "marketing", "media", "social"]

# ---------- Utilities ----------
def now_rome():
    return datetime.now(ROME).strftime("%d/%m/%Y %H:%M")

def normalize_space(text):
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()

def strip_tags(text):
    return normalize_space(re.sub(r"<[^>]+>", " ", text or ""))

def fetch_html(url, timeout=30, retries=1):
    last_error = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
            })
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                print(f"Tentativo {attempt + 1}/{retries} fallito per {url}: {exc}. Riprovo...")
                time.sleep(3)
    raise last_error

def absolute_url(base, href):
    return urllib.parse.urljoin(base, html.unescape(href)).split("#", 1)[0]

def send_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "false",
    }).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()

def notify_all(text):
    errors = []
    for chat_id in AUTHORIZED_CHAT_IDS:
        try:
            send_telegram(chat_id, text)
            print(f"Notifica inviata a {chat_id}")
        except Exception as exc:
            errors.append(f"{chat_id}: {exc}")
    if errors:
        raise RuntimeError("; ".join(errors))

# ---------- Memory ----------
SOURCE_NAMES = ["leonardo", "inpa", "eutalia", "consip", "sogei", "presidenza"]
MEMORY_SCHEMA_VERSION = 2

def empty_source():
    return {"initialized": False, "seen": []}

def empty_memory():
    return {"schema_version": MEMORY_SCHEMA_VERSION, "sources": {name: empty_source() for name in SOURCE_NAMES}}

def load_memory():
    if not SEEN_FILE.exists():
        return empty_memory()
    try:
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Memoria non leggibile: {exc}")

    # Very old layout: {"seen": [...]} => Leonardo
    if "sources" not in data:
        old_seen = data.get("seen", [])
        data = empty_memory()
        data["sources"]["leonardo"] = {"initialized": True, "seen": old_seen}

    data.setdefault("sources", {})

    # Schema v2: reset only the diagnostic baselines created by the earlier
    # Consip/Presidenza parser. Leonardo, inPA and Eutalia are preserved.
    if data.get("schema_version", 1) < MEMORY_SCHEMA_VERSION:
        for name in ("consip", "presidenza"):
            data["sources"][name] = empty_source()
        data["schema_version"] = MEMORY_SCHEMA_VERSION

    for name in SOURCE_NAMES:
        if name not in data["sources"]:
            data["sources"][name] = empty_source()
        else:
            src = data["sources"][name]
            src.setdefault("seen", [])
            # Existing sources from the previous bot are already initialized,
            # even if their seen list is empty.
            if "initialized" not in src:
                src["initialized"] = name in {"leonardo", "inpa", "eutalia"}
    return data

def save_memory(memory):
    memory["last_update"] = datetime.now(timezone.utc).isoformat()
    SEEN_FILE.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")

def process_items(memory, source, items, formatter):
    src = memory["sources"][source]
    current_ids = {item["id"] for item in items if item.get("id")}
    seen_ids = set(src.get("seen", []))

    if not src.get("initialized", False):
        print(f"Prima inizializzazione {source}: registro {len(current_ids)} elementi senza notificare.")
        src["initialized"] = True
        src["seen"] = sorted(current_ids)
        return 0

    new_items = [x for x in items if x.get("id") and x["id"] not in seen_ids]
    print(f"Nuovi elementi {source}: {len(new_items)}")
    for item in new_items:
        notify_all(formatter(item))

    # Keep historical IDs, so a removed/reappearing item is not re-notified.
    src["seen"] = sorted(seen_ids | current_ids)
    return len(new_items)

# ---------- Leonardo ----------
def leonardo_request(offset=0):
    payload = {"appliedFacets": LEONARDO_FACETS, "limit": 20, "offset": offset, "searchText": ""}
    request = urllib.request.Request(
        LEONARDO_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

def get_leonardo_jobs():
    jobs, offset = [], 0
    while True:
        response = leonardo_request(offset)
        batch = response.get("jobPostings", [])
        if not batch:
            break
        jobs.extend(batch)
        offset += len(batch)
        if offset >= response.get("total", len(jobs)):
            break
    return [{
        "id": job.get("externalPath") or f"{job.get('title','')}|{job.get('locationsText','')}",
        "title": job.get("title", "Titolo non disponibile"),
        "location": job.get("locationsText", "Località non disponibile"),
        "posted": job.get("postedOn", ""),
        "url": "https://leonardocompany.wd3.myworkdayjobs.com/it-IT/LeonardoCareerSite" + job.get("externalPath", ""),
    } for job in jobs]

def process_leonardo(memory):
    print("\n=== LEONARDO ===")
    items = get_leonardo_jobs()
    print(f"Offerte Leonardo trovate: {len(items)}")
    return process_items(memory, "leonardo", items, lambda x:
        "🚨 NUOVA OFFERTA LEONARDO\n\n"
        f"💼 {x['title']}\n📍 {x['location']}\n📅 Pubblicazione: {x['posted']}\n"
        f"🔔 Rilevata: {now_rome()}\n\n🏷 Communications / Sales & Marketing\n\n"
        f"🔗 {x['url']}\n\n🤖 Pic_Job_Finder_Bot")

# ---------- inPA ----------
def inpa_request(payload, page=0, size=50):
    url = f"{INPA_ENDPOINT}?page={page}&size={size}"
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0", "Origin": "https://www.inpa.gov.it", "Referer": "https://www.inpa.gov.it/"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

def get_inpa_results(payload):
    jobs, page = [], 0
    while True:
        response = inpa_request(payload, page, 50)
        jobs.extend(response.get("content", []))
        page += 1
        if page >= response.get("totalPages", 1):
            break
    return jobs

def get_inpa_jobs():
    by_id = {}
    p = dict(INPA_BASE_PAYLOAD)
    p["settoreId"] = INPA_COMMUNICATION_SECTOR
    results = get_inpa_results(p)
    print(f"inPA - Comunicazione e informazione: {len(results)}")
    for job in results:
        if job.get("id"):
            by_id[str(job["id"])] = job
    for term in INPA_SEARCH_TERMS:
        p = dict(INPA_BASE_PAYLOAD)
        p["text"] = term
        results = get_inpa_results(p)
        print(f"inPA - ricerca '{term}': {len(results)}")
        for job in results:
            if job.get("id"):
                by_id[str(job["id"])] = job
    print(f"inPA - risultati unici complessivi: {len(by_id)}")
    return list(by_id.values())

def format_inpa_date(value):
    if not value:
        return "Non disponibile"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ROME).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return value

def process_inpa(memory):
    print("\n=== INPA ===")
    jobs = get_inpa_jobs()
    items = []
    for job in jobs:
        jid = str(job.get("id", ""))
        items.append({
            "id": jid,
            "title": job.get("figuraRicercata") or job.get("titolo") or "Titolo non disponibile",
            "ente": ", ".join(job.get("entiRiferimento") or []) or "Ente non disponibile",
            "location": ", ".join(job.get("sedi") or []) or "Sede non disponibile",
            "posts": job.get("numPosti", "Non disponibile"),
            "published": format_inpa_date(job.get("dataPubblicazione")),
            "deadline": format_inpa_date(job.get("dataScadenza")),
            "sectors": ", ".join(job.get("settori") or []) or "Marketing / Comunicazione",
            "url": f"https://www.inpa.gov.it/bandi-e-avvisi/dettaglio-bando-avviso/?concorso_id={jid}",
        })
    print(f"Bandi inPA OPEN trovati: {len(items)}")
    return process_items(memory, "inpa", items, lambda x:
        "🚨 NUOVO BANDO inPA\n\n"
        f"💼 {x['title']}\n🏛 {x['ente']}\n📍 {x['location']}\n👥 Posti: {x['posts']}\n\n"
        f"📅 Pubblicato: {x['published']}\n⏳ Scadenza: {x['deadline']}\n🔔 Rilevato: {now_rome()}\n\n"
        f"🏷 {x['sectors']}\n\n🔗 {x['url']}\n\n🤖 Pic_Job_Finder_Bot")

# ---------- Eutalia ----------
def get_eutalia_open_notices():
    page = fetch_html(EUTALIA_URL, timeout=45, retries=2)
    notices = {}

    # Split around explicit status labels. Each status segment represents the
    # following Eutalia card much more reliably than inspecting a fixed window.
    status_pattern = re.compile(r'Avviso\s+(Aperto|Chiuso)', re.I)
    marks = list(status_pattern.finditer(page))

    for i, mark in enumerate(marks):
        if mark.group(1).lower() != "aperto":
            continue

        end = marks[i + 1].start() if i + 1 < len(marks) else min(len(page), mark.end() + 5000)
        segment = page[mark.start():end]

        link_match = re.search(
            r'href=["\'](?P<url>(?:https?://www\.eutalia\.eu)?/avvisi/[^"\']+)["\']',
            segment,
            re.I,
        )
        if not link_match:
            continue

        full = absolute_url(EUTALIA_URL, link_match.group("url")).rstrip("/")
        headings = re.findall(r'<h[2-4][^>]*>(.*?)</h[2-4]>', segment, re.I | re.S)
        title = ""
        for heading in headings:
            candidate = strip_tags(heading)
            if candidate and "selezione del personale" not in candidate.lower():
                title = candidate
                break
        if not title:
            slug = urllib.parse.urlparse(full).path.rstrip("/").rsplit("/", 1)[-1]
            title = slug.replace("-", " ").replace("_", " ").strip().title()

        notices[full] = {"id": full, "title": title, "url": full + "/"}

    return list(notices.values())

def process_eutalia(memory):
    print("\n=== EUTALIA ===")
    items = get_eutalia_open_notices()
    print(f"Avvisi Eutalia aperti trovati: {len(items)}")
    return process_items(memory, "eutalia", items, lambda x:
        "🚨 NUOVO AVVISO EUTALIA\n\n"
        f"📋 {x['title']}\n\n🏢 Eutalia\n🟢 Avviso Aperto\n🔔 Rilevato: {now_rome()}\n\n"
        f"🔗 {x['url']}\n\n🤖 Pic_Job_Finder_Bot")

# ---------- Consip: all listed job positions ----------
def get_consip_positions():
    # We deliberately monitor only the first page of the current listing.
    # Following pagination was pulling older/archive-like records into memory.
    page = fetch_html(CONSIP_URL, timeout=45, retries=2)
    items = {}

    # Pair each explicit position heading with its detail link.
    cards = re.findall(
        r'<h3[^>]*>(?P<title>.*?)</h3>.*?<a[^>]+href=["\'](?P<href>/posizioni/[^"\'?/#]+)["\'][^>]*>.*?</a>',
        page,
        re.I | re.S,
    )
    for title_html, href in cards:
        full = absolute_url("https://www.consip.it", href).rstrip("/")
        title = strip_tags(title_html)
        if title:
            items[full] = {"id": full, "title": title, "url": full}

    # Markup fallback, still restricted to detail pages and page 0 only.
    if not items:
        for href in re.findall(r'href=["\'](/posizioni/[^"\'?/#]+)["\']', page, re.I):
            full = absolute_url("https://www.consip.it", href).rstrip("/")
            slug = full.rsplit("/", 1)[-1]
            items[full] = {"id": full, "title": slug.replace("-", " ").title(), "url": full}

    return list(items.values())

def process_consip(memory):
    print("\n=== CONSIP ===")
    items = get_consip_positions()
    print(f"Posizioni Consip trovate: {len(items)}")
    return process_items(memory, "consip", items, lambda x:
        "🚨 NUOVA POSIZIONE CONSIP\n\n"
        f"💼 {x['title']}\n🏢 Consip\n🔔 Rilevata: {now_rome()}\n\n"
        f"🔗 {x['url']}\n\n🤖 Pic_Job_Finder_Bot")

# ---------- Sogei: all positions ----------
def get_sogei_positions():
    page = fetch_html(SOGEI_URL)
    text = strip_tags(page).lower()
    if "al momento non esistono posizioni disponibili" in text:
        return []

    # Capture links inside the current positions page, while excluding navigation/history.
    links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, re.I | re.S)
    items = {}
    for href, label in links:
        title = strip_tags(label)
        full = absolute_url(SOGEI_URL, href).rstrip("/")
        low = (title + " " + full).lower()
        if not title or len(title) < 4:
            continue
        if "avvisi-di-selezione0" in low or "criteri" in low or "lavorare-da-noi" in low:
            continue
        # Job links, when present, are expected inside the Lavora con Noi area.
        if "/lavora-con-noi/" not in full:
            continue
        if full.rstrip("/") == SOGEI_URL.rstrip("/"):
            continue
        items[full] = {"id": full, "title": title, "url": full}
    return list(items.values())

def process_sogei(memory):
    print("\n=== SOGEI ===")
    try:
        items = get_sogei_positions()
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            print("Sogei ha risposto HTTP 403: controllo saltato senza bloccare il workflow.")
            return 0
        raise
    print(f"Posizioni Sogei trovate: {len(items)}")
    return process_items(memory, "sogei", items, lambda x:
        "🚨 NUOVA POSIZIONE SOGEI\n\n"
        f"💼 {x['title']}\n🏢 Sogei\n🔔 Rilevata: {now_rome()}\n\n"
        f"🔗 {x['url']}\n\n🤖 Pic_Job_Finder_Bot")

# ---------- Presidenza: communication/marketing only ----------
def get_presidenza_relevant_items():
    page = fetch_html(PRESIDENZA_URL, timeout=60, retries=2)
    text = strip_tags(page)

    # Split the page into procedure-sized textual blocks. This avoids treating
    # every PDF, commission notice or exam update as a separate vacancy.
    starts = re.compile(
        r'(?=(?:Avviso pubblico|Concorso pubblico|Procedura selettiva|Avviso di mobilità|Procedura di mobilità))',
        re.I,
    )
    parts = starts.split(text)
    candidates = []

    # Build an index of useful destination links from the original HTML.
    links = []
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, re.I | re.S):
        label = strip_tags(m.group(2))
        full = absolute_url(PRESIDENZA_URL, m.group(1))
        links.append((label, full))

    for block in parts:
        block = normalize_space(block)
        low = block.lower()
        if not block or not any(k in low for k in PRESIDENZA_KEYWORDS):
            continue
        if low.startswith(("graduatoria", "scorrimento", "nomina", "aggiornamento")):
            continue

        title = block[:900]
        # Prefer an inPA link when the relevant procedure has one; otherwise use
        # the Presidency listing itself. Matching is conservative on distinctive words.
        words = [w for w in re.findall(r'[a-zà-ù0-9]+', low) if len(w) >= 7][:8]
        url = PRESIDENZA_URL
        for label, full in links:
            hay = (label + " " + full).lower()
            if "inpa" in hay and any(w in hay for w in words):
                url = full
                break

        stable = "presidenza:" + hashlib.sha256(title.lower().encode("utf-8")).hexdigest()[:24]
        candidates.append({"id": stable, "title": title, "url": url})

    # Deduplicate identical titles.
    unique = {}
    for item in candidates:
        key = normalize_space(item["title"]).lower()
        unique[key] = item
    return list(unique.values())

def process_presidenza(memory):
    print("\n=== PRESIDENZA DEL CONSIGLIO ===")
    try:
        items = get_presidenza_relevant_items()
    except (TimeoutError, urllib.error.URLError) as exc:
        print(f"Presidenza non raggiungibile ({exc}): controllo saltato senza bloccare il workflow.")
        return 0
    print(f"Procedure Presidenza pertinenti trovate: {len(items)}")
    return process_items(memory, "presidenza", items, lambda x:
        "🚨 NUOVA OPPORTUNITÀ PRESIDENZA DEL CONSIGLIO\n\n"
        f"💼 {x['title']}\n🏛 Presidenza del Consiglio dei ministri\n"
        f"🔔 Rilevata: {now_rome()}\n\n"
        f"🔗 {x['url']}\n\n🤖 Pic_Job_Finder_Bot")

# ---------- Main ----------
def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERRORE: TELEGRAM_BOT_TOKEN non configurato.")
        sys.exit(1)

    print("Pic_Job_Finder_Bot")
    print("Avvio controllo sorgenti...")
    memory = load_memory()
    errors = []

    processors = [
        ("Leonardo", process_leonardo),
        ("inPA", process_inpa),
        ("Eutalia", process_eutalia),
        ("Consip", process_consip),
        ("Sogei", process_sogei),
        ("Presidenza", process_presidenza),
    ]

    for name, processor in processors:
        try:
            processor(memory)
        except Exception as exc:
            print(f"ERRORE monitor {name}: {exc}")
            errors.append(f"{name}: {exc}")

    save_memory(memory)
    print("\n=== RIEPILOGO ===")
    if errors:
        print("Controllo completato con errori:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    print("Leonardo + inPA + Eutalia + Consip + Sogei + Presidenza controllati correttamente.")
    print("Controllo completato.")

if __name__ == "__main__":
    main()
