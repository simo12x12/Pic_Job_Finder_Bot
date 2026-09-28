import html
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

def empty_source():
    return {"initialized": False, "seen": []}

def empty_memory():
    return {"sources": {name: empty_source() for name in SOURCE_NAMES}}

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

    # Eutalia renders cards server-side. Detect each avviso URL, then inspect the
    # local card/block preceding the URL for the explicit status "Avviso Aperto".
    pattern = re.compile(
        r'<a[^>]+href=["\'](?P<url>(?:https?://www\.eutalia\.eu)?/avvisi/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',
        re.I | re.S,
    )
    matches = list(pattern.finditer(page))
    for i, m in enumerate(matches):
        raw_url = m.group("url")
        full = absolute_url(EUTALIA_URL, raw_url).rstrip("/")
        if full in notices:
            continue

        # The card begins after the previous avviso-link/card area. Limiting the
        # context this way avoids inheriting "Avviso Aperto" from an earlier card.
        prev_end = matches[i - 1].end() if i > 0 else max(0, m.start() - 1800)
        context_html = page[prev_end:m.end() + 600]
        context_text = strip_tags(context_html).lower()
        if "avviso aperto" not in context_text:
            continue
        if "avviso chiuso" in context_text and context_text.rfind("avviso chiuso") > context_text.rfind("avviso aperto"):
            continue

        # Prefer an h2/h3 title in the local card; link labels are often "Leggi di più".
        headings = re.findall(r'<h[2-4][^>]*>(.*?)</h[2-4]>', context_html, re.I | re.S)
        title = strip_tags(headings[-1]) if headings else strip_tags(m.group("label"))
        if not title or "leggi di" in title.lower():
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
    items = {}
    # Consip's page=0 is the current-jobs listing. We read pagination pages but
    # accept only explicit detail links /posizioni/<slug>.
    for page_num in range(0, 10):
        url = f"https://www.consip.it/lavora-con-noi/posizioni?field_pos_stato_value=All&page={page_num}"
        page = fetch_html(url, timeout=45, retries=2)

        cards = re.findall(
            r'<h3[^>]*>(?P<title>.*?)</h3>.*?<a[^>]+href=["\'](?P<href>/posizioni/[^"\'?/#]+)["\'][^>]*>.*?</a>',
            page,
            re.I | re.S,
        )
        before = len(items)
        for title_html, href in cards:
            full = absolute_url("https://www.consip.it", href).rstrip("/")
            title = strip_tags(title_html)
            if title:
                items[full] = {"id": full, "title": title, "url": full}

        # Fallback for markup variants, still restricted to detail URLs.
        if not cards:
            for href in re.findall(r'href=["\'](/posizioni/[^"\'?/#]+)["\']', page, re.I):
                full = absolute_url("https://www.consip.it", href).rstrip("/")
                slug = full.rsplit("/", 1)[-1]
                items[full] = {"id": full, "title": slug.replace("-", " ").title(), "url": full}

        if page_num > 0 and len(items) == before:
            break

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
    items = get_sogei_positions()
    print(f"Posizioni Sogei trovate: {len(items)}")
    return process_items(memory, "sogei", items, lambda x:
        "🚨 NUOVA POSIZIONE SOGEI\n\n"
        f"💼 {x['title']}\n🏢 Sogei\n🔔 Rilevata: {now_rome()}\n\n"
        f"🔗 {x['url']}\n\n🤖 Pic_Job_Finder_Bot")

# ---------- Presidenza: communication/marketing only ----------
def get_presidenza_relevant_items():
    page = fetch_html(PRESIDENZA_URL, timeout=60, retries=2)
    # Split around heading/paragraph-like blocks. We only accept contexts containing
    # one of the user-selected keywords and at least one recruitment/candidacy signal.
    candidates = []
    anchors = list(re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, re.I | re.S))
    recruitment_signals = ["bando", "concorso", "avviso pubblico", "selezione", "reclutamento", "assunzione", "incarico"]
    exclude_signals = ["graduatoria", "commissione", "diario d'esame", "esito", "scorrimento", "nomina"]

    for m in anchors:
        href, label_html = m.group(1), m.group(2)
        full = absolute_url(PRESIDENZA_URL, href)
        # Analyze a local block before the anchor; this usually contains the procedure title.
        context_html = page[max(0, m.start()-1800):min(len(page), m.end()+300)]
        context = strip_tags(context_html)
        low = context.lower()
        if not any(k in low for k in PRESIDENZA_KEYWORDS):
            continue
        if not any(s in low for s in recruitment_signals):
            continue
        # Avoid links that are clearly downstream updates rather than the vacancy/bando itself.
        label = strip_tags(label_html)
        if any(s in label.lower() for s in exclude_signals):
            continue
        # Prefer the nearby sentence/paragraph containing our keyword as title.
        title = label
        chunks = [normalize_space(x) for x in re.split(r"[\r\n]+|(?<=[.!?])\s+", context) if normalize_space(x)]
        keyword_chunks = [c for c in chunks if any(k in c.lower() for k in PRESIDENZA_KEYWORDS)]
        if keyword_chunks:
            title = max(keyword_chunks, key=len)[:700]
        if not title:
            continue
        # Stable key is the destination URL; inPA-linked PCM vacancies are okay because
        # separate source memories keep source-level traceability.
        candidates.append({"id": full, "title": title, "url": full})

    # Deduplicate by URL.
    return list({x["id"]: x for x in candidates}.values())

def process_presidenza(memory):
    print("\n=== PRESIDENZA DEL CONSIGLIO ===")
    items = get_presidenza_relevant_items()
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
