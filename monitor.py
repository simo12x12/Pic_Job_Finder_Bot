import html
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
AUTHORIZED_CHAT_IDS = ["2020881944"]
SEEN_FILE = Path("seen_jobs.json")
CURRENT_FILE = Path("current_jobs.json")
ROME = ZoneInfo("Europe/Rome")

LEONARDO_ENDPOINT = "https://leonardocompany.wd3.myworkdayjobs.com/wday/cxs/leonardocompany/LeonardoCareerSite/jobs"
INPA_ENDPOINT = "https://portale.inpa.gov.it/concorsi-smart/api/concorso-public-area/search-better"
EUTALIA_URL = "https://www.eutalia.eu/selezione-personale-ed-esperti/"
CONSIP_URL = "https://www.consip.it/lavora-con-noi/posizioni?field_pos_stato_value=All&page=0"
SOGEI_TRANSPARENCY_URL = "https://www.sogei.it/it/sogei-homepage/societa-trasparente/selezione-del-personale/reclutamento-del-personale/avvisi-di-selezione0.html"
AGID_ACTIVE_URL = "https://trasparenza.agid.gov.it/page/75/concorsi-attivi.html"
AGID_NOTICES_URL = "https://trasparenza.agid.gov.it/page/77/avvisi.html"
INVITALIA_JOBS_URL = "https://www.invitalia.it/lavora-con-noi/le-posizioni-aperte"
CDP_JOBS_URL = "https://www.opportunitadilavoro.cdp.it/"
CORPORATE_KEYWORDS = ["comunicazione", "communication", "marketing", "media", "social", "public affairs", "corporate affairs", "external relations", "relazioni esterne", "relazioni istituzionali", "rapporti istituzionali", "stakeholder", "brand", "content", "press", "ufficio stampa", "digital communication"]
IPZS_URL="https://www.ipzs.it/chi-siamo/lavora-con-noi/"
PAGOPA_URL="https://www.pagopa.it/it/lavora-con-noi/"
ROME_TECHNOPOLE_URL="https://www.rometechnopole.it/lavora-con-noi/"
AMA_ROMA_URL="https://www.amaroma.it/lavora-con-noi"
BMTI_URL="https://www.bmti.it/lavora-con-noi/"

LEONARDO_FACETS = {
    "locationCountry": ["8cd04a563fd94da7b06857a79faaf815"],
    "jobFamilyGroup": [
        "8f7876e90e9c0101f751f430c4290000",
        "8f7876e90e9c0101f751e65634a60000",
    ],
}

INPA_BASE_PAYLOAD = {
    "text": "",
    "categoriaId": None,
    "regioneId": None,
    "status": ["OPEN"],
    "settoreId": None,
    "dateFrom": None,
    "dateTo": None,
    "enteRiferimentoName": "",
    "livelliAnzianitaIds": None,
    "provinciaCodice": None,
    "salaryMax": None,
    "salaryMin": None,
    "tipoImpiegoId": None,
}
INPA_COMMUNICATION_SECTOR = "b078865c126040558601"
INPA_SEARCH_TERMS = ["marketing", "comunicazione istituzionale"]

SOURCE_NAMES = ["leonardo", "inpa", "eutalia", "consip", "sogei", "agid", "invitalia", "cdp", "ipzs", "pagopa", "rome_technopole", "ama_roma", "bmti"]
SOURCE_LABELS = {
    "leonardo": "Leonardo",
    "inpa": "inPA",
    "eutalia": "Eutalia",
    "consip": "Consip",
    "sogei": "Sogei",
    "agid": "AgID",
    "invitalia": "Invitalia",
    "cdp": "CDP",
    "ipzs": "IPZS",
    "pagopa": "PagoPA",
    "rome_technopole": "Rome Technopole",
    "ama_roma": "AMA Roma",
    "bmti": "BMTI",
}
MEMORY_SCHEMA_VERSION = 7


def now_rome():
    return datetime.now(ROME).strftime("%d/%m/%Y %H:%M")


def normalize_space(text):
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def strip_tags(text):
    return normalize_space(re.sub(r"<[^>]+>", " ", text or ""))


def absolute_url(base, href):
    return urllib.parse.urljoin(base, html.unescape(href)).split("#", 1)[0]


def fetch_html(url, timeout=30, retries=1):
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                print(f"Tentativo {attempt + 1}/{retries} fallito per {url}: {exc}. Riprovo...")
                time.sleep(3)
    raise last_error


def send_telegram(chat_id, text):
    data = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": "false"}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
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


def empty_source():
    return {"initialized": False, "seen": []}


def empty_memory():
    return {
        "schema_version": MEMORY_SCHEMA_VERSION,
        "sources": {name: empty_source() for name in SOURCE_NAMES},
    }


def load_memory():
    if not SEEN_FILE.exists():
        return empty_memory()

    data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))

    if "sources" not in data:
        old_seen = data.get("seen", [])
        data = empty_memory()
        data["sources"]["leonardo"] = {"initialized": True, "seen": old_seen}

    data.setdefault("sources", {})

    if data.get("schema_version", 1) < 6:
        old_jobs = data["sources"].pop("invitalia_jobs", {"seen": []})
        old_consulting = data["sources"].pop("invitalia_consulting", {"seen": []})
        data["sources"]["invitalia"] = {
            "initialized": old_jobs.get("initialized", False)
            or old_consulting.get("initialized", False),
            "seen": sorted(
                set(old_jobs.get("seen", [])) | set(old_consulting.get("seen", []))
            ),
        }

    data["schema_version"] = MEMORY_SCHEMA_VERSION

    for name in SOURCE_NAMES:
        data["sources"].setdefault(name, empty_source())
        data["sources"][name].setdefault("seen", [])
        data["sources"][name].setdefault("initialized", False)

    return data


def save_memory(memory):
    memory["last_update"] = datetime.now(timezone.utc).isoformat()
    SEEN_FILE.write_text(
        json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def process_items(memory, source, items, formatter):
    src = memory["sources"][source]
    current_ids = {item["id"] for item in items if item.get("id")}
    seen_ids = set(src.get("seen", []))

    if not src.get("initialized", False):
        print(
            f"Prima inizializzazione {source}: registro {len(current_ids)} elementi senza notificare."
        )
        src["initialized"] = True
        src["seen"] = sorted(current_ids)
        return 0

    new_items = [
        item
        for item in items
        if item.get("id") and item["id"] not in seen_ids
    ]
    print(f"Nuovi elementi {source}: {len(new_items)}")

    for item in new_items:
        notify_all(formatter(item))

    # Gli ID storici rimangono per evitare una seconda notifica
    # se un annuncio scompare e poi ricompare con lo stesso ID.
    src["seen"] = sorted(seen_ids | current_ids)
    return len(new_items)


def standard_job_message(source, title, url, published=None, deadline=None, extra=None):
    lines = [
        f"🚨 NUOVA OPPORTUNITÀ - {source.upper()}",
        "",
        f"💼 {title}",
        f"🏢 Fonte: {source}",
    ]
    if published:
        lines.append(f"📅 Pubblicata: {published}")
    if deadline:
        lines.append(f"⏳ Scadenza: {deadline}")
    if extra:
        lines.append(f"🏷 {extra}")
    lines.extend(
        [
            f"🔔 Rilevata: {now_rome()}",
            "",
            f"🔗 {url}",
            "",
            "🤖 Pic_Job_Finder_Bot",
        ]
    )
    return "\n".join(lines)


# ---------- Leonardo ----------
def leonardo_request(offset=0):
    payload = {
        "appliedFacets": LEONARDO_FACETS,
        "limit": 20,
        "offset": offset,
        "searchText": "",
    }
    req = urllib.request.Request(
        LEONARDO_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_leonardo_jobs():
    jobs = []
    offset = 0
    while True:
        response = leonardo_request(offset)
        batch = response.get("jobPostings", [])
        if not batch:
            break
        jobs.extend(batch)
        offset += len(batch)
        if offset >= response.get("total", len(jobs)):
            break

    return [
        {
            "id": job.get("externalPath") or job.get("title", ""),
            "title": job.get("title", "Titolo non disponibile"),
            "location": job.get("locationsText", "Località non disponibile"),
            "posted": job.get("postedOn", ""),
            "url": "https://leonardocompany.wd3.myworkdayjobs.com/it-IT/LeonardoCareerSite"
            + job.get("externalPath", ""),
        }
        for job in jobs
    ]


# ---------- inPA ----------
def inpa_request(payload, page=0, size=50):
    req = urllib.request.Request(
        f"{INPA_ENDPOINT}?page={page}&size={size}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://www.inpa.gov.it",
            "Referer": "https://www.inpa.gov.it/",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_inpa_results(payload):
    jobs = []
    page = 0
    while True:
        response = inpa_request(payload, page, 50)
        jobs.extend(response.get("content", []))
        page += 1
        if page >= response.get("totalPages", 1):
            break
    return jobs


def format_inpa_date(value):
    if not value:
        return "Non disponibile"
    try:
        return (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            .astimezone(ROME)
            .strftime("%d/%m/%Y %H:%M")
        )
    except Exception:
        return value


def get_inpa_items():
    by_id = {}

    payload = dict(INPA_BASE_PAYLOAD)
    payload["settoreId"] = INPA_COMMUNICATION_SECTOR
    results = get_inpa_results(payload)
    print(f"inPA - Comunicazione e informazione: {len(results)}")
    for job in results:
        if job.get("id"):
            by_id[str(job["id"])] = job

    for term in INPA_SEARCH_TERMS:
        payload = dict(INPA_BASE_PAYLOAD)
        payload["text"] = term
        results = get_inpa_results(payload)
        print(f"inPA - ricerca '{term}': {len(results)}")
        for job in results:
            if job.get("id"):
                by_id[str(job["id"])] = job

    print(f"inPA - risultati unici complessivi: {len(by_id)}")

    items = []
    for job in by_id.values():
        job_id = str(job.get("id", ""))
        items.append(
            {
                "id": job_id,
                "title": job.get("figuraRicercata")
                or job.get("titolo")
                or "Titolo non disponibile",
                "published": format_inpa_date(job.get("dataPubblicazione")),
                "deadline": format_inpa_date(job.get("dataScadenza")),
                "extra": ", ".join(job.get("entiRiferimento") or []),
                "url": f"https://www.inpa.gov.it/bandi-e-avvisi/dettaglio-bando-avviso/?concorso_id={job_id}",
            }
        )
    return items


# ---------- Eutalia ----------
def get_eutalia_open_notices():
    page = fetch_html(EUTALIA_URL, 45, 2)
    notices = {}
    marks = list(re.finditer(r"Avviso\s+(Aperto|Chiuso)", page, re.I))

    for index, mark in enumerate(marks):
        if mark.group(1).lower() != "aperto":
            continue

        end = (
            marks[index + 1].start()
            if index + 1 < len(marks)
            else min(len(page), mark.end() + 5000)
        )
        segment = page[mark.start() : end]

        link_match = re.search(
            r'href=["\'](?P<url>(?:https?://www\.eutalia\.eu)?/avvisi/[^"\']+)["\']',
            segment,
            re.I,
        )
        if not link_match:
            continue

        full = absolute_url(EUTALIA_URL, link_match.group("url")).rstrip("/")
        headings = re.findall(r"<h[2-4][^>]*>(.*?)</h[2-4]>", segment, re.I | re.S)
        title = (
            strip_tags(headings[0])
            if headings
            else full.rsplit("/", 1)[-1].replace("-", " ").title()
        )
        notices[full] = {"id": full, "title": title, "url": full + "/"}

    return list(notices.values())


# ---------- Consip ----------
def get_consip_positions():
    page = fetch_html(CONSIP_URL, 45, 2)
    items = {}

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

    return list(items.values())


# ---------- Sogei ----------
def get_sogei_positions():
    page = fetch_html(SOGEI_TRANSPARENCY_URL, 45, 2)

    start_match = re.search(r"Avvisi\s+di\s+selezione\s+in\s+corso", page, re.I)
    end_match = re.search(r"Avvisi\s+di\s+selezione\s+conclusi", page, re.I)

    if not start_match:
        raise RuntimeError("Sezione Sogei non trovata")

    end_pos = (
        end_match.start()
        if end_match and end_match.start() > start_match.end()
        else len(page)
    )
    section = page[start_match.end() : end_pos]

    if "al momento non esistono posizioni disponibili" in strip_tags(section).lower():
        return []

    items = {}
    for href, label_html in re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        section,
        re.I | re.S,
    ):
        label = strip_tags(label_html)
        if not label:
            continue

        full = absolute_url(SOGEI_TRANSPARENCY_URL, href)
        code_match = re.search(r"\((20\d{2}/\d+[A-Z]?)\)", label, re.I)
        item_id = (
            "sogei:" + code_match.group(1).upper()
            if code_match
            else "sogei:" + hashlib.sha256(full.encode("utf-8")).hexdigest()[:24]
        )
        items[item_id] = {"id": item_id, "title": label, "url": full}

    return list(items.values())


# ---------- AgID ----------
def parse_it_date(value):
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except Exception:
        return None


def get_agid_table_items(url, nonexpired=False):
    page = fetch_html(url, 45, 2)
    today = datetime.now(ROME).date()
    items = {}

    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.I | re.S):
        link_match = re.search(
            r'<a[^>]+href=["\'](?P<href>[^"\']+/details/[^"\']+)["\'][^>]*>(?P<title>.*?)</a>',
            row,
            re.I | re.S,
        )
        if not link_match:
            continue

        full = absolute_url(url, link_match.group("href"))
        dates = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", strip_tags(row))
        deadline = dates[1] if len(dates) > 1 else ""
        deadline_date = parse_it_date(deadline)

        if nonexpired and (not deadline_date or deadline_date < today):
            continue

        item_id = "agid:" + hashlib.sha256(full.encode("utf-8")).hexdigest()[:24]
        items[item_id] = {
            "id": item_id,
            "title": strip_tags(link_match.group("title")),
            "url": full,
            "published": dates[0] if dates else "",
            "deadline": deadline,
        }

    return list(items.values())


def get_agid_positions():
    active = get_agid_table_items(AGID_ACTIVE_URL)
    print(f"AgID - Concorsi attivi: {len(active)}")

    notices = get_agid_table_items(AGID_NOTICES_URL, True)
    print(f"AgID - Avvisi non scaduti: {len(notices)}")

    return list({item["id"]: item for item in active + notices}.values())


# ---------- Invitalia ----------
def get_invitalia_jobs():
    page = fetch_html(INVITALIA_JOBS_URL, 45, 2)
    start = page.lower().find("le ricerche in corso")
    end = page.lower().find("vedi le selezioni chiuse")
    section = page[start : end if end > start else len(page)] if start >= 0 else page
    items = {}

    for href, label_html in re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        section,
        re.I | re.S,
    ):
        label = strip_tags(label_html)
        full = absolute_url(INVITALIA_JOBS_URL, href)
        low = (label + full).lower()

        if not label:
            continue
        if "ingate.invitalia.it" in full.lower():
            continue
        if "/lavora-con-noi/" not in full.lower():
            continue
        if "selezioni-chiuse" in low or "candidatura-spontanea" in low:
            continue
        if full.rstrip("/") == INVITALIA_JOBS_URL.rstrip("/"):
            continue

        item_id = "invitalia-job:" + hashlib.sha256(full.encode("utf-8")).hexdigest()[:24]
        items[item_id] = {"id": item_id, "title": label, "url": full}

    return list(items.values())


def get_invitalia_consulting():
    page = fetch_html(INVITALIA_JOBS_URL, 45, 2)
    items = {}

    for href, label_html in re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        page,
        re.I | re.S,
    ):
        full = absolute_url(INVITALIA_JOBS_URL, href)
        label = strip_tags(label_html)
        low = label.lower()

        if "ingate.invitalia.it" not in full.lower():
            continue
        if not any(
            word in low
            for word in ("consulenza", "esperti", "specialisti", "profession")
        ):
            continue
        if any(word in low for word in ("gara", "fornitura", "lavori", "appalto")):
            continue

        query = urllib.parse.parse_qs(urllib.parse.urlparse(full).query)
        opportunity_id = (query.get("opportunityId") or [full])[0]
        item_id = "invitalia-consulting:" + str(opportunity_id)
        items[item_id] = {"id": item_id, "title": label, "url": full}

    return list(items.values())


def get_invitalia_positions():
    jobs = get_invitalia_jobs()
    consulting = get_invitalia_consulting()

    print(f"Invitalia - posizioni: {len(jobs)}")
    print(f"Invitalia - consulenze/esperti: {len(consulting)}")

    items = []
    for item in jobs:
        enriched = dict(item)
        enriched["extra"] = "Posizione"
        items.append(enriched)
    for item in consulting:
        enriched = dict(item)
        enriched["extra"] = "Consulenza / Esperti / Specialisti"
        items.append(enriched)

    items = list({item["id"]: item for item in items}.values())
    print(f"Invitalia - opportunita uniche complessive: {len(items)}")
    return items


def matches_corporate_keywords(text):
    low = normalize_space(text).lower()
    return any(k in low for k in CORPORATE_KEYWORDS)


def get_ipzs_positions():
    page=fetch_html(IPZS_URL,45,2);items={}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>https?://www\.recruiting\.ipzs\.it/job/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        full=absolute_url(IPZS_URL,m.group('href')).rstrip('/');label=strip_tags(m.group('label'));context=strip_tags(page[max(0,m.start()-1200):min(len(page),m.end()+1200)])
        if not matches_corporate_keywords(label+' '+context): continue
        title=label
        if not title or title.lower() in {'scopri','candidati'}:
            heads=re.findall(r'<h[2-5][^>]*>(.*?)</h[2-5]>',page[max(0,m.start()-1200):m.start()],re.I|re.S);title=strip_tags(heads[-1]) if heads else context[:300]
        iid='ipzs:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'Corporate keywords'}
    return list(items.values())


def get_pagopa_positions():
    page=fetch_html(PAGOPA_URL,45,2);items={};a=page.lower().find('posizioni aperte');b=page.lower().find('posizioni chiuse');sec=page[a:b if b>a else len(page)] if a>=0 else page
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>(?:https?://www\.pagopa\.it)?/it/lavora-con-noi/jobposition-[^"\']+/)["\'][^>]*>(?P<label>.*?)</a>',sec,re.I|re.S):
        full=absolute_url(PAGOPA_URL,m.group('href'));title=strip_tags(m.group('label'));context=strip_tags(sec[max(0,m.start()-400):min(len(sec),m.end()+400)])
        if not matches_corporate_keywords(title+' '+context):continue
        iid='pagopa:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'Corporate keywords'}
    return list(items.values())


def get_rome_technopole_positions():
    page=fetch_html(ROME_TECHNOPOLE_URL,45,2);items={};ms=list(re.finditer(r'AVVISO\s+PUBBLICO\s+N\.\s*(\d+)/2026',page,re.I))
    for i,m in enumerate(ms):
        seg=page[m.start():(ms[i+1].start() if i+1<len(ms) else min(len(page),m.end()+5000))];text=strip_tags(seg)
        if not matches_corporate_keywords(text):continue
        heads=re.findall(r'<h[2-6][^>]*>(.*?)</h[2-6]>',seg,re.I|re.S);title=next((strip_tags(h) for h in heads if 'avviso pubblico n.' not in strip_tags(h).lower()),text[:400]);hrefs=re.findall(r'href=["\']([^"\']+)["\']',seg,re.I);url=absolute_url(ROME_TECHNOPOLE_URL,hrefs[0]) if hrefs else ROME_TECHNOPOLE_URL;iid=f'rome-technopole:2026-{m.group(1)}';items[iid]={'id':iid,'title':title,'url':url,'extra':f'Avviso {m.group(1)}/2026'}
    return list(items.values())


def get_ama_roma_positions():
    page=fetch_html(AMA_ROMA_URL,45,2);items={};a=page.lower().find('procedure selettive aperte');b=page.lower().find('procedure selettive chiuse');sec=page[a:b if b>a else len(page)] if a>=0 else page
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>(?:https?://www\.amaroma\.it)?/lavora-con-noi/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',sec,re.I|re.S):
        full=absolute_url(AMA_ROMA_URL,m.group('href')).rstrip('/');label=strip_tags(m.group('label'));context=strip_tags(sec[max(0,m.start()-700):m.end()])
        if not matches_corporate_keywords(label+' '+context):continue
        title=re.split(r'Consulta gli aggiornamenti',context,maxsplit=1,flags=re.I)[0].strip() or label;iid='ama:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'Procedura aperta'}
    return list(items.values())


def get_bmti_positions():
    page=fetch_html(BMTI_URL,45,2);items={};a=page.lower().find('posizioni aperte');b=page.lower().find('per tutte le posizioni',a+1);sec=page[a:b if b>a else len(page)] if a>=0 else page
    for href,label_html in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',sec,re.I|re.S):
        label=strip_tags(label_html);full=absolute_url(BMTI_URL,href)
        if not label or not full.lower().endswith('.pdf'):continue
        iid='bmti:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':label,'url':full,'extra':'Posizione aperta'}
    return list(items.values())


# ---------- CDP ----------
def get_cdp_positions():
    items = {}

    for term in CORPORATE_KEYWORDS:
        query = urllib.parse.urlencode(
            {"createNewAlert": "false", "q": term, "locationsearch": ""}
        )
        url = f"{CDP_JOBS_URL.rstrip('/')}/search/?{query}"
        page = fetch_html(url, 45, 2)
        found = {}

        for match in re.finditer(
            r'<a[^>]+href=["\'](?P<href>[^"\']*/job/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',
            page,
            re.I | re.S,
        ):
            full = absolute_url(url, match.group("href")).rstrip("/")
            label = strip_tags(match.group("label"))
            if not label:
                continue

            item_id = "cdp:" + hashlib.sha256(full.encode("utf-8")).hexdigest()[:24]
            found[item_id] = {
                "id": item_id,
                "title": label,
                "url": full,
                "extra": "Comunicazione / Marketing",
            }

        print(f"CDP - ricerca '{term}': {len(found)}")
        items.update(found)

    print(f"CDP - posizioni uniche complessive: {len(items)}")
    return list(items.values())


def save_current(snapshot):
    CURRENT_FILE.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERRORE: TELEGRAM_BOT_TOKEN non configurato.")
        sys.exit(1)

    print("Pic_Job_Finder_Bot")
    print("Avvio controllo sorgenti...")

    memory = load_memory()
    errors = []
    snapshot = {"last_check": now_rome(), "sources": {}}

    specs = [
        (
            "leonardo",
            get_leonardo_jobs,
            lambda x: standard_job_message(
                "Leonardo",
                x["title"],
                x["url"],
                published=x.get("posted"),
                extra=x.get("location"),
            ),
        ),
        (
            "inpa",
            get_inpa_items,
            lambda x: standard_job_message(
                "inPA",
                x["title"],
                x["url"],
                published=x.get("published"),
                deadline=x.get("deadline"),
                extra=x.get("extra"),
            ),
        ),
        (
            "eutalia",
            get_eutalia_open_notices,
            lambda x: standard_job_message(
                "Eutalia", x["title"], x["url"], extra="Avviso Aperto"
            ),
        ),
        (
            "consip",
            get_consip_positions,
            lambda x: standard_job_message("Consip", x["title"], x["url"]),
        ),
        (
            "sogei",
            get_sogei_positions,
            lambda x: standard_job_message("Sogei", x["title"], x["url"]),
        ),
        (
            "agid",
            get_agid_positions,
            lambda x: standard_job_message(
                "AgID",
                x["title"],
                x["url"],
                published=x.get("published"),
                deadline=x.get("deadline"),
            ),
        ),
        (
            "invitalia",
            get_invitalia_positions,
            lambda x: standard_job_message(
                "Invitalia", x["title"], x["url"], extra=x.get("extra")
            ),
        ),
        ("ipzs", get_ipzs_positions, lambda x: standard_job_message("IPZS", x["title"], x["url"], extra=x.get("extra"))),
        ("pagopa", get_pagopa_positions, lambda x: standard_job_message("PagoPA", x["title"], x["url"], extra=x.get("extra"))),
        ("rome_technopole", get_rome_technopole_positions, lambda x: standard_job_message("Rome Technopole", x["title"], x["url"], extra=x.get("extra"))),
        ("ama_roma", get_ama_roma_positions, lambda x: standard_job_message("AMA Roma", x["title"], x["url"], extra=x.get("extra"))),
        ("bmti", get_bmti_positions, lambda x: standard_job_message("BMTI", x["title"], x["url"], extra=x.get("extra"))),
        (
            "cdp",
            get_cdp_positions,
            lambda x: standard_job_message(
                "CDP - Cassa Depositi e Prestiti",
                x["title"],
                x["url"],
                extra=x.get("extra"),
            ),
        ),
    ]

    for source, getter, formatter in specs:
        print(f"\n=== {SOURCE_LABELS[source].upper()} ===")

        try:
            items = getter()
            print(f"Elementi correnti {SOURCE_LABELS[source]}: {len(items)}")
            process_items(memory, source, items, formatter)

            snapshot["sources"][source] = {
                "label": SOURCE_LABELS[source],
                "status": "ok",
                "items": [
                    {
                        "title": item.get("title", "Titolo non disponibile"),
                        "url": item.get("url", ""),
                    }
                    for item in items
                ],
            }

        except urllib.error.HTTPError as exc:
            if source == "sogei" and exc.code == 403:
                print(
                    "Sogei: HTTP 403. Controllo non disponibile in questo run."
                )
                snapshot["sources"][source] = {
                    "label": "Sogei",
                    "status": "unavailable",
                    "items": [],
                }
                continue

            print(
                f"ERRORE monitor {SOURCE_LABELS[source]}: "
                f"HTTP {exc.code} - {exc.reason}"
            )
            errors.append(f"{SOURCE_LABELS[source]}: {exc}")
            snapshot["sources"][source] = {
                "label": SOURCE_LABELS[source],
                "status": "error",
                "items": [],
                "error": str(exc),
            }

        except Exception as exc:
            print(f"ERRORE monitor {SOURCE_LABELS[source]}: {exc}")
            errors.append(f"{SOURCE_LABELS[source]}: {exc}")
            snapshot["sources"][source] = {
                "label": SOURCE_LABELS[source],
                "status": "error",
                "items": [],
                "error": str(exc),
            }

    save_memory(memory)
    save_current(snapshot)

    print("\n=== RIEPILOGO ===")
    if errors:
        print("Controllo completato con errori:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    print(
        "Leonardo + inPA + Eutalia + Consip + Sogei + AgID + "
        "Invitalia + IPZS + PagoPA + Rome Technopole + AMA Roma + BMTI + CDP controllati."
    )
    print("Controllo completato.")


if __name__ == "__main__":
    main()
