import html
import hashlib
import json
import os
import re
import smtplib
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ERROR_EMAIL_TO = os.environ.get("ERROR_EMAIL_TO")
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM") or SMTP_USER
AUTHORIZED_CHAT_IDS = ["2020881944"]
SEEN_FILE = Path("seen_jobs.json")
CURRENT_FILE = Path("current_jobs.json")
ROME = ZoneInfo("Europe/Rome")

LEONARDO_ENDPOINT = "https://leonardocompany.wd3.myworkdayjobs.com/wday/cxs/leonardocompany/LeonardoCareerSite/jobs"
INPA_ENDPOINT = "https://portale.inpa.gov.it/concorsi-smart/api/concorso-public-area/search-better"
EUTALIA_URL = "https://www.eutalia.eu/selezione-personale-ed-esperti/"
CONSIP_URL = "https://www.consip.it/lavora-con-noi/posizioni"
SOGEI_TRANSPARENCY_URL = "https://www.sogei.it/it/sogei-homepage/societa-trasparente/selezione-del-personale/reclutamento-del-personale/avvisi-di-selezione0.html"
AGID_ACTIVE_URL = "https://trasparenza.agid.gov.it/page/75/concorsi-attivi.html"
AGID_NOTICES_URL = "https://trasparenza.agid.gov.it/page/77/avvisi.html"
INVITALIA_JOBS_URL = "https://www.invitalia.it/lavora-con-noi/le-posizioni-aperte"
CDP_JOBS_URL = "https://www.opportunitadilavoro.cdp.it/"
CORPORATE_KEYWORDS = ["comunicazione", "communication", "marketing", "media", "social", "public affairs", "corporate affairs", "external relations", "relazioni esterne", "relazioni istituzionali", "rapporti istituzionali", "stakeholder", "brand", "content", "press", "ufficio stampa", "digital communication", "media relations", "institutional relations", "event", "events", "eventi", "partnership", "sponsorship", "sponsorizzazioni", "editorial", "editoriale", "reputation", "corporate communication", "campagne informative"]
IPZS_URL="https://www.ipzs.it/chi-siamo/lavora-con-noi/"
PAGOPA_URL="https://www.pagopa.it/it/lavora-con-noi/"
ROME_TECHNOPOLE_URL="https://www.rometechnopole.it/lavora-con-noi/"
AMA_ROMA_URL="https://www.amaroma.it/lavora-con-noi"
BMTI_URL="https://www.bmti.it/lavora-con-noi/"
SACE_URL="https://sace.wd103.myworkdayjobs.com/it-IT/Sace001"
GSE_URL="https://gse.taleo.net/careersection/ex/joblist.ftl?lang=it"
TERNA_URL="https://www.terna.it/it/persone/lavora-noi/posizioni-aperte"
ACEA_URL="https://jobs.acea.it/Acea/go/Acea-Lavora-con-noi/3482701/"
ITALO_URL="https://italospa.italotreno.it/lavorare_in_italo/posizioni_aperte/index.html"
ITALO_LEGAL_URL="https://italospa.italotreno.it/lavorare_in_italo/posizioni_aperte/direzione-legal-affairs-and-compliance.html"
FINCANTIERI_URL="https://www.fincantieri.com/it/persone/lavora-con-noi/posizioni-aperte"
ANCI_OPEN_URL="https://anci.portaletrasparenza.net/it/trasparenza/selezione-del-personale/reclutamento-del-personale/bandi-e-avvisi-di-selezione-per-i-quali-e-possibile-presentare-domanda-di-partecipazione.html?ordina_per=oggetto&dir=desc&sort=t.oggetto&direction=desc&pagina=1"
IFEL_SELECTION_URL="https://fondazioneifel.portaletrasparenza.net/it/trasparenza/selezione-del-personale.html"
IFEL_RECRUITMENT_URL="https://fondazioneifel.portaletrasparenza.net/it/trasparenza/selezione-del-personale/reclutamento-del-personale.html"
SNA_CONCORSI_URL="https://sna.gov.it/home/amministrazione-trasparente/bandi-di-concorso/"
TAGLIACARNE_OPEN_URL="https://tagliacarne.portaletrasparenza.net/it/trasparenza/selezione-del-personale/reclutamento-del-personale/bandi-e-avvisi-di-selezione-per-i-quali-e-possibile-presentare-domanda-di-partecipazione.html"
BRODOLINI_URL="https://www.fondazionebrodolini.it/vacancy"
FONDAZIONE_SUD_URL="https://www.fondazioneconilsud.it/lavora-con-noi/"
ENAV_CAREER_URL="https://enav.intervieweb.it/it/career"
SPORT_SALUTE_URL="https://areariservata.sportesalute.eu/elenco-posizioni-lavorative/"
FS_JOBS_URL="https://fscareers.gruppofs.it/jobs.php"
AUTOSTRADE_CAREER_URL="https://career55.sapsf.eu/career?company=autostrade"
INFOCAMERE_OPEN_URL="https://infocamere.it/posizioni-aperte/"
FORMEZ_BANDI_URL="https://www.formez.it/lavora-con-noi/bandi"
FORMEZ_AVVISI_URL="https://avvisi.formez.it/"
SVILUPPO_LAVORO_URL="https://lavoraconnoi.sviluppolavoroitalia.it/hr/core/StartInteraction.action?id_interaction=ST.HR.LSTAVVISI_PUBBLICATI"
CAPCOE_URL="https://capcoe.it/opportunita/avvisi/"
UNIONCAMERE_URL="https://www.unioncamere.gov.it/amministrazione-trasparente/bandi-di-concorso"
AGENAS_URL="https://www.agenas.gov.it/bandi-di-concorso/avvisi-attivi"
ICE_URL="https://www.ice.it/it/chi-siamo/lavora-con-noi/concorsi"
INAPP_URL="https://www.inapp.gov.it/amministrazione-trasparente/bandi-di-concorso/avvisi-incarico/"

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
INPA_SEARCH_TERMS = [
    "marketing",
    "comunicazione istituzionale",
    "public affairs",
    "corporate affairs",
    "relazioni esterne",
    "relazioni istituzionali",
    "rapporti istituzionali",
    "stakeholder",
    "ufficio stampa",
    "digital communication",
]

SOURCE_NAMES = ["leonardo", "inpa", "eutalia", "consip", "sogei", "agid", "invitalia", "cdp", "ipzs", "pagopa", "rome_technopole", "ama_roma", "bmti", "sace", "gse", "terna", "acea", "italo", "fincantieri", "anci", "ifel", "sna", "tagliacarne", "brodolini", "fondazione_sud", "enav", "sport_salute", "fs", "autostrade", "infocamere", "formez", "sviluppo_lavoro", "capcoe", "unioncamere", "agenas", "ice", "inapp"]
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
    "sace": "SACE",
    "gse": "GSE",
    "terna": "Terna",
    "acea": "Acea",
    "italo": "Italo",
    "fincantieri": "Fincantieri",
    "anci": "ANCI",
    "ifel": "IFEL",
    "sna": "SNA",
    "tagliacarne": "Centro Studi Tagliacarne",
    "brodolini": "Fondazione Giacomo Brodolini",
    "fondazione_sud": "Fondazione con il Sud",
    "enav": "ENAV",
    "sport_salute": "Sport e Salute",
    "fs": "Gruppo FS Italiane",
    "autostrade": "Autostrade per l Italia",
    "infocamere": "InfoCamere",
    "formez": "Formez PA",
    "sviluppo_lavoro": "Sviluppo Lavoro Italia",
    "capcoe": "PN Capacita per la Coesione",
    "unioncamere": "Unioncamere",
    "agenas": "AGENAS",
    "ice": "Agenzia ICE",
    "inapp": "INAPP",
}
MEMORY_SCHEMA_VERSION = 23


def now_rome():
    return datetime.now(ROME).strftime("%d/%m/%Y %H:%M")


def normalize_space(text):
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def strip_tags(text):
    return normalize_space(re.sub(r"<[^>]+>", " ", text or ""))

def parse_status_date(value):
    """Parse a known date without guessing; returns None when it cannot be verified."""
    if not value:
        return None
    text = normalize_space(str(value))
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(ROME).date()
    except Exception:
        return None


def classify_item_status(item):
    """Return open, expired/closed or unknown using only explicit evidence."""
    raw = normalize_space(str(item.get("status", ""))).lower()
    if raw in {"closed", "chiuso", "chiusa", "concluso", "conclusa", "expired", "scaduto", "scaduta"}:
        return "expired/closed"
    deadline = parse_status_date(item.get("deadline"))
    if deadline:
        return "expired/closed" if deadline < datetime.now(ROME).date() else "open"
    if raw in {"open", "aperto", "aperta", "active", "attivo", "attiva"}:
        return "open"
    return "unknown"


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


def send_error_email(subject, body):
    # Optional SMTP error channel. Telegram is intentionally never used here.
    # If SMTP is not configured, GitHub Actions can still notify by email when
    # the workflow exits with code 1.
    if not (ERROR_EMAIL_TO and SMTP_HOST and SMTP_USER and SMTP_PASSWORD and SMTP_FROM):
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = ERROR_EMAIL_TO
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    return True


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

    if data.get("schema_version", 1) < 8:
        # The corporate keyword set was expanded. Re-baseline CDP once so the
        # newly discovered existing matches are not sent as fresh alerts.
        data["sources"]["cdp"] = empty_source()

    if data.get("schema_version", 1) < 9:
        # The inPA search vocabulary was expanded. Re-baseline inPA once so
        # existing vacancies uncovered by the new queries are not sent as new.
        data["sources"]["inpa"] = empty_source()

    if data.get("schema_version", 1) < 11:
        # Parser refinements for Block 2: re-baseline these sources once.
        for name in ("terna", "italo", "fincantieri"):
            data["sources"][name] = empty_source()

    if data.get("schema_version", 1) < 12:
        for name in ("bmti", "italo", "fincantieri"):
            data["sources"][name] = empty_source()

    if data.get("schema_version", 1) < 13:
        for name in ("italo", "fincantieri"):
            data["sources"][name] = empty_source()

    if data.get("schema_version", 1) < 14:
        for name in ("italo", "fincantieri"):
            data["sources"][name] = empty_source()

    if data.get("schema_version", 1) < 15:
        data["sources"]["bmti"] = empty_source()

    if data.get("schema_version", 1) < 17:
        for name in ("anci", "ifel", "tagliacarne", "brodolini", "fondazione_sud"):
            data["sources"][name] = empty_source()

    if data.get("schema_version", 1) < 18:
        for name in ("anci", "tagliacarne", "brodolini", "fondazione_sud"):
            data["sources"][name] = empty_source()

    if data.get("schema_version", 1) < 19:
        for name in ("anci", "tagliacarne", "sport_salute", "fs", "autostrade", "infocamere", "formez", "sviluppo_lavoro", "capcoe", "unioncamere"):
            data["sources"][name] = empty_source()

    if data.get("schema_version", 1) < 20:
        # The corporate vocabulary was expanded in the previous release.
        # Re-baseline Terna once so pre-existing matches are not notified as new.
        data["sources"]["terna"] = empty_source()

    if data.get("schema_version", 1) < 21:
        for name in ("agenas", "ice"):
            data["sources"][name] = empty_source()

    if data.get("schema_version", 1) < 22:
        data["sources"]["inapp"] = empty_source()

    if data.get("schema_version", 1) < 23:
        for name in ("inpa", "consip", "invitalia", "rome_technopole", "terna", "sport_salute", "infocamere"):
            data["sources"][name] = empty_source()

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
    classified = [(item, classify_item_status(item)) for item in items]
    excluded = sum(1 for _, status in classified if status == "expired/closed")
    if excluded:
        print(f"Elementi esclusi per stato/scadenza verificata {source}: {excluded}")
    items = [item for item, status in classified if status != "expired/closed"]
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
        f"🚨 {source.upper()}",
        "",
        normalize_space(title).upper(),
        "",
        url,
    ]
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
        title = job.get("figuraRicercata") or job.get("titolo") or "Titolo non disponibile"
        title_low = normalize_space(title).lower()
        relevant_terms = ("comunic", "ufficio stampa", "relazioni istituzionali", "rapporti istituzionali", "public affairs", "corporate affairs", "media relation", "marketing", "stakeholder")
        if not any(term in title_low for term in relevant_terms):
            continue
        items.append(
            {
                "id": job_id,
                "title": title,
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
    blacklist = {'chi siamo','category','lavora con noi','scopri','approfondisci','leggi di più','leggi di piu'}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>/posizioni/[^"\'?/#]+)["\'][^>]*>(?P<label>.*?)</a>', page, re.I|re.S):
        full=absolute_url('https://www.consip.it',m.group('href')).rstrip('/')
        slug=urllib.parse.unquote(full.rsplit('/',1)[-1])
        if slug in {'category','posizioni'}: continue
        label=strip_tags(m.group('label'))
        title=label if label and label.lower() not in blacklist else slug.replace('-',' ').strip().title()
        if not title or title.lower() in blacklist: continue
        # Avoid archive/navigation entries: keep the corporate-professional perimeter only.
        if not matches_corporate_keywords(title): continue
        iid='consip:'+hashlib.sha256(full.encode()).hexdigest()[:24]
        items[iid]={'id':iid,'title':title,'url':full,'status':'open'}
    return list(items.values())


# ---------- Sogei ----------
def get_sogei_positions():
    page = fetch_html(SOGEI_TRANSPARENCY_URL, 15, 1)

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
        if label.lower().startswith("consulta anche gli avvisi"):
            continue
        if not any(word in low for word in ("consulenza", "esperti", "specialisti", "profession")):
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
        if not matches_corporate_keywords(text): continue
        heads=[strip_tags(h) for h in re.findall(r'<h[2-6][^>]*>(.*?)</h[2-6]>',seg,re.I|re.S)]
        title=next((h for h in heads if h and 'avviso pubblico n.' not in h.lower()),'')
        if not title:
            role=re.search(r'(Avviso pubblico per l.individuazione[^.]{20,260}|n\.\s*1\s+[^.]{10,220})',text,re.I)
            title=role.group(1).strip() if role else text[:220].strip()
        title=re.sub(r'\s+È indetta.*$','',title,flags=re.I).strip()
        hrefs=[h for h in re.findall(r'href=["\']([^"\']+)["\']',seg,re.I) if not h.lower().startswith('mailto:')]
        url=absolute_url(ROME_TECHNOPOLE_URL,hrefs[0]) if hrefs else ROME_TECHNOPOLE_URL
        iid=f'rome-technopole:2026-{m.group(1)}';items[iid]={'id':iid,'title':title,'url':url,'extra':f'Avviso {m.group(1)}/2026'}
    return list(items.values())


def get_ama_roma_positions():
    page=fetch_html(AMA_ROMA_URL,15,1);items={};a=page.lower().find('procedure selettive aperte');b=page.lower().find('procedure selettive chiuse');sec=page[a:b if b>a else len(page)] if a>=0 else page
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>(?:https?://www\.amaroma\.it)?/lavora-con-noi/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',sec,re.I|re.S):
        full=absolute_url(AMA_ROMA_URL,m.group('href')).rstrip('/');label=strip_tags(m.group('label'));context=strip_tags(sec[max(0,m.start()-700):m.end()])
        if not matches_corporate_keywords(label+' '+context):continue
        title=re.split(r'Consulta gli aggiornamenti',context,maxsplit=1,flags=re.I)[0].strip() or label;iid='ama:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'Procedura aperta'}
    return list(items.values())


def get_bmti_positions():
    page = fetch_html(BMTI_URL, 45, 2)
    items = {}

    for href, label_html in re.findall(
        r'<a[^>]+href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\'][^>]*>(.*?)</a>',
        page,
        re.I | re.S,
    ):
        label = strip_tags(label_html)
        full = absolute_url(BMTI_URL, href)
        low = (label + " " + full).lower()

        # Exclude generic documentation; BMTI recruitment notices use Avviso/Proc naming.
        if not label:
            continue
        if any(x in low for x in ("privacy", "nota-informativa", "informativa-privacy")):
            continue
        if not any(x in low for x in ("avviso", "proc_", "proc-", "proc.")):
            continue

        iid = "bmti:" + hashlib.sha256(full.encode("utf-8")).hexdigest()[:24]
        items[iid] = {
            "id": iid,
            "title": label,
            "url": full,
            "extra": "Posizione aperta BMTI",
        }

    return list(items.values())


# ---------- Block 2 corporate sources ----------
def _extract_job_links(page, base_url, host_hint=None):
    items = {}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>', page, re.I | re.S):
        label = strip_tags(m.group("label"))
        full = absolute_url(base_url, m.group("href")).rstrip("/")
        if not label:
            continue
        if host_hint and host_hint not in full.lower():
            continue
        items[full] = label
    return items


def get_sace_positions():
    page = fetch_html(SACE_URL, 45, 2); items = {}
    for full, title in _extract_job_links(page, SACE_URL, "sace.wd103.myworkdayjobs.com").items():
        if "/job/" not in full.lower() or "spontaneous" in full.lower(): continue
        context = title
        if not matches_corporate_keywords(context): continue
        iid='sace:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'Corporate keywords'}
    return list(items.values())


def get_gse_positions():
    page=fetch_html(GSE_URL,45,2);items={}
    # Taleo page exposes headings even when links use fragments; title is sufficient for filtering.
    for title_html in re.findall(r'<h[1-4][^>]*>(.*?)</h[1-4]>',page,re.I|re.S):
        title=strip_tags(title_html)
        if not title or title.lower() in {'candidatura spontanea','stage e tirocini','categorie protette'}:continue
        if not matches_corporate_keywords(title):continue
        iid='gse:'+hashlib.sha256(title.lower().encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':GSE_URL,'extra':'Corporate keywords'}
    return list(items.values())


def get_terna_positions():
    page=fetch_html(TERNA_URL,45,2);items={}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>https?://jobs\.terna\.it/job/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        full=m.group('href').rstrip('/')
        parsed=urllib.parse.urlparse(full)
        parts=[urllib.parse.unquote(x) for x in parsed.path.split('/') if x]
        title=''
        if 'job' in parts:
            idx=parts.index('job')
            if idx+1<len(parts): title=parts[idx+1].replace('-',' ').replace('&amp;','&').strip()
        if not title: title=strip_tags(m.group('label'))
        context=strip_tags(page[max(0,m.start()-900):min(len(page),m.end()+900)])
        if not matches_corporate_keywords(title+' '+context): continue
        iid='terna:'+hashlib.sha256(full.split('?',1)[0].encode()).hexdigest()[:24]
        items[iid]={'id':iid,'title':title,'url':full,'extra':'Corporate keywords'}
    return list(items.values())


def get_acea_positions():
    page=fetch_html(ACEA_URL,45,2);items={}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+/Acea/job/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        title=strip_tags(m.group('label'));full=absolute_url(ACEA_URL,m.group('href')).rstrip('/')
        if not title or not matches_corporate_keywords(title):continue
        iid='acea:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'Corporate keywords'}
    return list(items.values())


def get_italo_positions():
    pages = []
    fetch_errors = []

    for base in (ITALO_URL, ITALO_LEGAL_URL):
        try:
            pages.append((base, fetch_html(base, 30, 1)))
        except Exception as exc:
            fetch_errors.append(str(exc))

    if not pages:
        raise RuntimeError("Italo non disponibile: " + "; ".join(fetch_errors))

    items = {}
    saw_corporate_phrase = False

    for base, page in pages:
        plain = strip_tags(page)
        if "corporate affairs" in plain.lower():
            saw_corporate_phrase = True

        candidates = [
            strip_tags(x)
            for x in re.findall(r'<h[1-6][^>]*>(.*?)</h[1-6]>', page, re.I | re.S)
        ]
        # Capture compact all-caps job labels when the site renders positions outside H tags.
        candidates += [
            normalize_space(x)
            for x in re.findall(
                r'([A-Z][A-Z0-9 &/\-]{0,90}(?:CORPORATE AFFAIRS|COMMUNICATION|MARKETING|MEDIA RELATIONS)[A-Z0-9 &/\-]{0,90})',
                plain,
            )
        ]

        for title in candidates:
            title = normalize_space(title)
            if not title or len(title) > 130 or not matches_corporate_keywords(title):
                continue
            if title.lower() in {
                "legal affairs and compliance",
                "lavora con noi",
                "candidatura spontanea",
            }:
                continue
            title = re.sub(r'\s+Italia(?:\s*/\s*Roma)?\s*\(RM\).*$','',title,flags=re.I).strip()
            iid = "italo:" + hashlib.sha256(title.lower().encode("utf-8")).hexdigest()[:24]
            items[iid] = {"id": iid, "title": title, "url": base, "extra": "Corporate keywords"}

    # If the official pages visibly contain Corporate Affairs but parser extraction failed,
    # do not report a misleading operational zero.
    if saw_corporate_phrase and not items:
        raise RuntimeError("Italo: pagina raggiungibile ma vacancy Corporate Affairs non estraibile in modo affidabile")

    return list(items.values())


def get_fincantieri_positions():
    page = fetch_html(FINCANTIERI_URL, 45, 2)
    items = {}

    blacklist = {
        "media center",
        "social media",
        "press kit",
        "persone",
        "lavora con noi",
        "posizioni aperte",
        "scopri",
        "approfondisci",
    }

    for m in re.finditer(
        r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',
        page,
        re.I | re.S,
    ):
        title = strip_tags(m.group("label"))
        full = absolute_url(FINCANTIERI_URL, m.group("href")).rstrip("/")
        low_title = title.lower()
        low_url = full.lower()

        if not title or low_title in blacklist:
            continue
        if len(title) > 180 or not matches_corporate_keywords(title):
            continue
        # Accept only links that look like actual vacancy/recruiting destinations.
        if not any(token in low_url for token in ("/job/", "/jobs/", "career", "recruit", "vacanc")):
            continue

        iid = "fincantieri:" + hashlib.sha256(full.encode("utf-8")).hexdigest()[:24]
        items[iid] = {"id": iid, "title": title, "url": full, "extra": "Corporate keywords"}

    # The official page may be client-rendered. A zero here is not proof of no openings,
    # so signal non-availability instead of polluting current_jobs with false results.
    if not items:
        raise RuntimeError("Fincantieri: pagina ufficiale raggiungibile ma vacancy non estraibili in modo affidabile")

    return list(items.values())


# ---------- Block 3 ----------
def _portal_open_selection_items(url, prefix):
    page=fetch_html(url,45,2);items={}
    # Transparency portals expose detail links and row text with dates.
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        title=strip_tags(m.group('label'));full=absolute_url(url,m.group('href')).rstrip('/')
        if not title or len(title)<15:continue
        low=(title+' '+full).lower()
        if not any(x in low for x in ('avviso','selezione','concorso','esperto','long list','incarico')):continue
        if any(x in low for x in ('privacy','esito','graduatoria','archivio')):continue
        iid=prefix+':'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full}
    return list(items.values())


def get_anci_positions():
    page = fetch_html(ANCI_OPEN_URL, 45, 2)
    today = datetime.now(ROME).date()
    items = {}

    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.I | re.S):
        text = strip_tags(row)
        dates = re.findall(r'\b(\d{2}/\d{2}/\d{4})\b', text)
        if len(dates) < 2:
            continue

        deadline = parse_it_date(dates[-1])
        if not deadline or deadline < today:
            continue

        detail = re.search(
            r'<a[^>]+href=["\'](?P<href>[^"\']*/dettagli/concorsi/[^"\']+)["\'][^>]*>(?P<title>.*?)</a>',
            row,
            re.I | re.S,
        )
        if not detail:
            continue

        title = strip_tags(detail.group('title'))
        full = absolute_url(ANCI_OPEN_URL, detail.group('href')).rstrip('/')
        iid = 'anci:' + hashlib.sha256(full.encode('utf-8')).hexdigest()[:24]
        items[iid] = {
            'id': iid,
            'title': title,
            'url': full,
            'deadline': dates[-1],
        }

    return list(items.values())


def get_ifel_positions():
    page = fetch_html(IFEL_RECRUITMENT_URL, 20, 1)
    today = datetime.now(ROME).date()
    items = {}

    # Parse the recruitment listing directly. Do not open every detail page.
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.I | re.S):
        text = strip_tags(row)
        links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', row, re.I | re.S)
        if not links:
            continue
        dates = re.findall(r'\b(\d{2}/\d{2}/\d{4})\b', text)
        if len(dates) < 2:
            continue
        deadline = parse_it_date(dates[-1])
        if not deadline or deadline < today:
            continue
        href, label_html = max(links, key=lambda x: len(strip_tags(x[1])))
        title = strip_tags(label_html)
        full = absolute_url(IFEL_RECRUITMENT_URL, href).rstrip('/')
        low = (title + ' ' + full).lower()
        if not any(x in low for x in ('avviso', 'selezione', 'concorso', 'assunzione')):
            continue
        iid = 'ifel:' + hashlib.sha256(full.encode('utf-8')).hexdigest()[:24]
        items[iid] = {'id': iid, 'title': title, 'url': full, 'deadline': dates[-1]}

    return list(items.values())


def get_sna_positions():
    page=fetch_html(SNA_CONCORSI_URL,45,2);today=datetime.now(ROME).date();items={}
    # SNA page contains current and historic notices; require an explicit future/non-expired deadline.
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        title=strip_tags(m.group('label'))
        if not title or not matches_corporate_keywords(title):continue
        context=strip_tags(page[max(0,m.start()-300):min(len(page),m.end()+300)]);dm=re.search(r'scadenza\s+(\d{1,2})/(\d{1,2})/(\d{4})',context,re.I)
        if not dm:continue
        deadline=datetime(int(dm.group(3)),int(dm.group(2)),int(dm.group(1))).date()
        if deadline<today:continue
        full=absolute_url(SNA_CONCORSI_URL,m.group('href'));iid='sna:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'deadline':deadline.strftime('%d/%m/%Y')}
    return list(items.values())


def get_tagliacarne_positions():
    page = fetch_html(TAGLIACARNE_OPEN_URL, 45, 2)
    page_text = strip_tags(page).lower()

    if 'nessun elemento presente' in page_text:
        return []

    today = datetime.now(ROME).date()
    items = {}
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.I | re.S):
        text = strip_tags(row)
        dates = re.findall(r'\b(\d{2}/\d{2}/\d{4})\b', text)
        if len(dates) < 2:
            continue
        deadline = parse_it_date(dates[-1])
        if not deadline or deadline < today:
            continue
        detail = re.search(
            r'<a[^>]+href=["\'](?P<href>[^"\']*/dettagli/concorsi/[^"\']+)["\'][^>]*>(?P<title>.*?)</a>',
            row,
            re.I | re.S,
        )
        if not detail:
            continue
        title = strip_tags(detail.group('title'))
        full = absolute_url(TAGLIACARNE_OPEN_URL, detail.group('href')).rstrip('/')
        iid = 'tagliacarne:' + hashlib.sha256(full.encode('utf-8')).hexdigest()[:24]
        items[iid] = {'id': iid, 'title': title, 'url': full, 'deadline': dates[-1]}
    return list(items.values())


def get_brodolini_positions():
    page = fetch_html(BRODOLINI_URL, 45, 2)
    items = {}

    for m in re.finditer(
        r'<a[^>]+href=["\'](?P<href>[^"\']*/vacancy/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',
        page,
        re.I | re.S,
    ):
        full = absolute_url(BRODOLINI_URL, m.group('href')).rstrip('/')
        if full == BRODOLINI_URL.rstrip('/'):
            continue
        title = strip_tags(m.group('label'))
        if not title:
            # Prefer the closest heading before the vacancy link.
            before = page[max(0, m.start() - 800):m.start()]
            heads = re.findall(r'<h[2-5][^>]*>(.*?)</h[2-5]>', before, re.I | re.S)
            title = strip_tags(heads[-1]) if heads else 'Vacancy Fondazione Giacomo Brodolini'
        iid = 'brodolini:' + hashlib.sha256(full.encode('utf-8')).hexdigest()[:24]
        items[iid] = {'id': iid, 'title': title, 'url': full}

    return list(items.values())


def get_fondazione_sud_positions():
    page = fetch_html(FONDAZIONE_SUD_URL, 45, 2)
    items = {}

    for m in re.finditer(
        r'<a[^>]+href=["\'](?P<href>https?://www\.fondazioneconilsud\.it/2026/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',
        page,
        re.I | re.S,
    ):
        full = m.group('href').rstrip('/')
        title = strip_tags(m.group('label'))
        context = strip_tags(page[max(0, m.start() - 500):min(len(page), m.end() + 500)])
        if not title:
            continue
        combined = (title + ' ' + context).lower()
        if not any(x in combined for x in ('comunicazione', 'communication', 'ufficio stampa', 'media relations')):
            continue
        iid = 'fondazione-sud:' + hashlib.sha256(full.encode('utf-8')).hexdigest()[:24]
        items[iid] = {'id': iid, 'title': title, 'url': full}

    return list(items.values())


def get_enav_positions():
    page=fetch_html(ENAV_CAREER_URL,45,2);items={}
    # Intervieweb career page contains vacancy cards. Filter large-company listings by corporate dictionary.
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        title=strip_tags(m.group('label'));full=absolute_url(ENAV_CAREER_URL,m.group('href')).rstrip('/')
        if not title or not matches_corporate_keywords(title):continue
        if 'candidatura spontanea' in title.lower():continue
        iid='enav:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'Corporate keywords'}
    return list(items.values())


# ---------- Block 4 and 5 ----------
def get_sport_salute_positions():
    page=fetch_html(SPORT_SALUTE_URL,30,1);items={}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+/posizione/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        raw=strip_tags(m.group('label')).lstrip(': ').strip();full=absolute_url(SPORT_SALUTE_URL,m.group('href')).rstrip('/')
        title=re.sub(r'^(?:Sport e Salute S\.p\.A\.|Comitato Italiano Paralimpico)\s*-\s*','',raw,flags=re.I).strip()
        if not title or not matches_corporate_keywords(title): continue
        iid='sport-salute:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'Corporate keywords'}
    return list(items.values())


def get_fs_positions():
    page=fetch_html(FS_JOBS_URL,35,1);items={}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']*view-job\.php[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        title=strip_tags(m.group('label'));full=absolute_url(FS_JOBS_URL,m.group('href'))
        if not title or not matches_corporate_keywords(title):continue
        iid='fs:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'Corporate keywords'}
    return list(items.values())


def get_autostrade_positions():
    page=fetch_html(AUTOSTRADE_CAREER_URL,35,1);items={}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        title=strip_tags(m.group('label'));full=absolute_url(AUTOSTRADE_CAREER_URL,m.group('href')).rstrip('/')
        if not title or len(title)>180 or not matches_corporate_keywords(title):continue
        if any(x in title.lower() for x in ('privacy','cookie','candidatura spontanea')):continue
        iid='autostrade:'+hashlib.sha256((title+'|'+full).encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'Corporate keywords'}
    return list(items.values())


def get_infocamere_positions():
    page=fetch_html(INFOCAMERE_OPEN_URL,30,1);items={}
    blacklist=('ufficio stampa','social media policy','privacy','cookie','posizioni chiuse','candidatura spontanea')
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        title=strip_tags(m.group('label'));full=absolute_url(INFOCAMERE_OPEN_URL,m.group('href')).rstrip('/');low=(title+' '+full).lower()
        if not title or any(x in low for x in blacklist): continue
        if full.lower().endswith('.pdf'): continue
        if not matches_corporate_keywords(title): continue
        # Require a recruitment-shaped destination, not normal site navigation.
        if not any(x in full.lower() for x in ('posizion','lavora-con-noi','career','job')): continue
        iid='infocamere:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'Corporate keywords'}
    return list(items.values())


def get_formez_positions():
    page = fetch_html(FORMEZ_AVVISI_URL, 30, 2)
    plain = strip_tags(page)
    if re.search(r"Attualmente\s+non\s+ci\s+sono\s+avvisi", plain, re.I):
        return []
    items = {}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>', page, re.I | re.S):
        title=strip_tags(m.group('label')); full=absolute_url(FORMEZ_AVVISI_URL,m.group('href')).rstrip('/')
        if not title or len(title)<8: continue
        context=strip_tags(page[max(0,m.start()-500):min(len(page),m.end()+800)]); low=(title+' '+context).lower()
        if not any(x in low for x in ('avviso','selezione','reclutamento','incarico','esperto','personale')): continue
        if any(x in low for x in ('chiuso','chiusa','archivio','graduatoria','esito')): continue
        if not matches_corporate_keywords(title+' '+context) and not any(x in low for x in ('assistenza tecnica','capacita istituzionale','capacità istituzionale','eventi di lavoro')): continue
        iid='formez:'+hashlib.sha256(full.encode()).hexdigest()[:24]; items[iid]={'id':iid,'title':title,'url':full,'extra':'Avviso Formez PA','status':'open'}
    return list(items.values())


def get_sviluppo_lavoro_positions():
    page=fetch_html(SVILUPPO_LAVORO_URL,30,1);items={}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        title=strip_tags(m.group('label'));full=absolute_url(SVILUPPO_LAVORO_URL,m.group('href')).rstrip('/')
        if not title or not matches_corporate_keywords(title):continue
        iid='sviluppo-lavoro:'+hashlib.sha256((title+'|'+full).encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'Corporate / PA keywords'}
    return list(items.values())


def get_capcoe_positions():
    page=fetch_html(CAPCOE_URL,30,1);today=datetime.now(ROME).date();items={}
    plain=strip_tags(page)
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        title=strip_tags(m.group('label'));full=absolute_url(CAPCOE_URL,m.group('href')).rstrip('/')
        if not title or not matches_corporate_keywords(title):continue
        # dedupe sources already monitored directly
        if any(host in full.lower() for host in ('eutalia.eu','anci.portaletrasparenza.net','inpa.gov.it')):continue
        context=strip_tags(page[m.end():min(len(page),m.end()+350)]);dm=re.search(r'(?:Scadenza|Data chiusura candidature):\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})|(?:Scadenza|Data chiusura candidature):\s*(\d{1,2})/(\d{1,2})/(\d{4})',context,re.I)
        # Keep only entries where expiry can be verified as current; otherwise skip.
        if not dm:continue
        months={'gennaio':1,'febbraio':2,'marzo':3,'aprile':4,'maggio':5,'giugno':6,'luglio':7,'agosto':8,'settembre':9,'ottobre':10,'novembre':11,'dicembre':12}
        try:
            if dm.group(1): deadline=datetime(int(dm.group(3)),months[dm.group(2).lower()],int(dm.group(1))).date()
            else: deadline=datetime(int(dm.group(6)),int(dm.group(5)),int(dm.group(4))).date()
        except Exception:continue
        if deadline<today:continue
        iid='capcoe:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'deadline':deadline.strftime('%d/%m/%Y')}
    return list(items.values())


def get_unioncamere_positions():
    page=fetch_html(UNIONCAMERE_URL,30,1);items={}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+/bandi-di-concorso/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        title=strip_tags(m.group('label'));full=absolute_url(UNIONCAMERE_URL,m.group('href')).rstrip('/')
        if not title or not matches_corporate_keywords(title):continue
        if any(x in full.lower() for x in ('bandi-scaduti','archivio')):continue
        iid='unioncamere:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'PA / Corporate keywords'}
    return list(items.values())


# ---------- AGENAS and Agenzia ICE ----------
def get_agenas_positions():
    page=fetch_html(AGENAS_URL,30,1);today=datetime.now(ROME).date();items={}
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>',page,re.I|re.S):
        text=strip_tags(row)
        if not matches_corporate_keywords(text):continue
        links=re.findall(r'<a[^>]+href=["\']([^"\']+/bandi-di-concorso/avvisi-attivi/[^"\']+)["\'][^>]*>(.*?)</a>',row,re.I|re.S)
        if not links:continue
        href,label_html=max(links,key=lambda x:len(strip_tags(x[1])));title=strip_tags(label_html)
        # Italian numeric deadline or textual month deadline.
        dm=re.search(r'(\d{2})/(\d{2})/(\d{4})',text)
        if dm:
            deadline=datetime(int(dm.group(3)),int(dm.group(2)),int(dm.group(1))).date()
        else:
            months={'gennaio':1,'febbraio':2,'marzo':3,'aprile':4,'maggio':5,'giugno':6,'luglio':7,'agosto':8,'settembre':9,'ottobre':10,'novembre':11,'dicembre':12}
            tm=re.search(r'(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})',text,re.I)
            deadline=datetime(int(tm.group(3)),months[tm.group(2).lower()],int(tm.group(1))).date() if tm else None
        if not deadline or deadline<today:continue
        full=absolute_url(AGENAS_URL,href).rstrip('/');iid='agenas:'+hashlib.sha256(full.encode()).hexdigest()[:24]
        items[iid]={'id':iid,'title':title,'url':full,'deadline':deadline.strftime('%d/%m/%Y')}
    return list(items.values())


def get_ice_positions():
    page=fetch_html(ICE_URL,30,1);items={}
    # ICE mixes live procedures and their subsequent documents on one page. Keep only
    # primary notices that match our professional dictionary, excluding explicit concluded items.
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
        title=strip_tags(m.group('label'));full=absolute_url(ICE_URL,m.group('href')).rstrip('/')
        if not title or len(title)>500 or not matches_corporate_keywords(title):continue
        context=strip_tags(page[max(0,m.start()-180):min(len(page),m.end()+180)]).lower()
        low=title.lower()
        if any(x in low for x in ('elenco candidature','commissione','graduatoria','candidati ammessi','calendario','esito','verbale','scorrimento')):continue
        if any(x in context for x in ('(concluso)','(conclusa)','scaduto','scaduta')):continue
        if not any(x in low for x in ('avviso','selezione','concorso','incarico','mobilità','mobilita')):continue
        iid='ice:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'PA / Corporate keywords'}
    return list(items.values())


# ---------- INAPP ----------
def get_inapp_positions():
    page = fetch_html(INAPP_URL, 30, 1)
    today = datetime.now(ROME).date()
    items = {}

    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.I | re.S):
        text = strip_tags(row)
        low = text.lower()

        # Only actual professional assignments, not generic notices or disposals.
        if not any(x in low for x in ('incarico di lavoro autonomo', 'esperto', 'esperta', 'progetto di comunicazione')):
            continue
        if not matches_corporate_keywords(text):
            continue

        # The INAPP table exposes the application deadline in the row.
        dates = re.findall(r'\b(\d{2}/\d{2}/\d{4})\b', text)
        if not dates:
            continue
        deadline = parse_it_date(dates[-1])
        if not deadline or deadline < today:
            continue

        links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', row, re.I | re.S)
        if not links:
            continue
        href, label_html = max(links, key=lambda x: len(strip_tags(x[1])))
        title = strip_tags(label_html) or text
        full = absolute_url(INAPP_URL, href).rstrip('/')

        iid = 'inapp:' + hashlib.sha256(full.encode('utf-8')).hexdigest()[:24]
        items[iid] = {
            'id': iid,
            'title': title,
            'url': full,
            'deadline': dates[-1],
            'extra': 'Incarico / esperto INAPP',
        }

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
    warnings = []
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
        ("sace", get_sace_positions, lambda x: standard_job_message("SACE", x["title"], x["url"], extra=x.get("extra"))),
        ("gse", get_gse_positions, lambda x: standard_job_message("GSE", x["title"], x["url"], extra=x.get("extra"))),
        ("terna", get_terna_positions, lambda x: standard_job_message("Terna", x["title"], x["url"], extra=x.get("extra"))),
        ("acea", get_acea_positions, lambda x: standard_job_message("Acea", x["title"], x["url"], extra=x.get("extra"))),
        ("italo", get_italo_positions, lambda x: standard_job_message("Italo", x["title"], x["url"], extra=x.get("extra"))),
        ("fincantieri", get_fincantieri_positions, lambda x: standard_job_message("Fincantieri", x["title"], x["url"], extra=x.get("extra"))),
        ("anci", get_anci_positions, lambda x: standard_job_message("ANCI", x["title"], x["url"], deadline=x.get("deadline"))),
        ("ifel", get_ifel_positions, lambda x: standard_job_message("IFEL", x["title"], x["url"], deadline=x.get("deadline"))),
        ("sna", get_sna_positions, lambda x: standard_job_message("SNA", x["title"], x["url"], deadline=x.get("deadline"))),
        ("tagliacarne", get_tagliacarne_positions, lambda x: standard_job_message("Centro Studi Tagliacarne", x["title"], x["url"], deadline=x.get("deadline"))),
        ("brodolini", get_brodolini_positions, lambda x: standard_job_message("Fondazione Giacomo Brodolini", x["title"], x["url"])),
        ("fondazione_sud", get_fondazione_sud_positions, lambda x: standard_job_message("Fondazione con il Sud", x["title"], x["url"])),
        ("enav", get_enav_positions, lambda x: standard_job_message("ENAV", x["title"], x["url"], extra=x.get("extra"))),
        ("sport_salute", get_sport_salute_positions, lambda x: standard_job_message("Sport e Salute", x["title"], x["url"], extra=x.get("extra"))),
        ("fs", get_fs_positions, lambda x: standard_job_message("Gruppo FS Italiane", x["title"], x["url"], extra=x.get("extra"))),
        ("autostrade", get_autostrade_positions, lambda x: standard_job_message("Autostrade per l Italia", x["title"], x["url"], extra=x.get("extra"))),
        ("infocamere", get_infocamere_positions, lambda x: standard_job_message("InfoCamere", x["title"], x["url"], extra=x.get("extra"))),
        ("formez", get_formez_positions, lambda x: standard_job_message("Formez PA", x["title"], x["url"], extra=x.get("extra"))),
        ("sviluppo_lavoro", get_sviluppo_lavoro_positions, lambda x: standard_job_message("Sviluppo Lavoro Italia", x["title"], x["url"], extra=x.get("extra"))),
        ("capcoe", get_capcoe_positions, lambda x: standard_job_message("PN Capacita per la Coesione", x["title"], x["url"], deadline=x.get("deadline"))),
        ("unioncamere", get_unioncamere_positions, lambda x: standard_job_message("Unioncamere", x["title"], x["url"], extra=x.get("extra"))),
        ("agenas", get_agenas_positions, lambda x: standard_job_message("AGENAS", x["title"], x["url"], deadline=x.get("deadline"))),
        ("ice", get_ice_positions, lambda x: standard_job_message("Agenzia ICE", x["title"], x["url"], extra=x.get("extra"))),
        ("inapp", get_inapp_positions, lambda x: standard_job_message("INAPP", x["title"], x["url"], deadline=x.get("deadline"), extra=x.get("extra"))),
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
                        "open_status": classify_item_status(item),
                    }
                    for item in items
                ],
            }

        except urllib.error.HTTPError as exc:
            if source in {"sogei", "ama_roma"} and exc.code == 403:
                label = SOURCE_LABELS[source]
                print(f"{label}: HTTP 403. Controllo non disponibile in questo run.")
                snapshot["sources"][source] = {
                    "label": label,
                    "status": "unavailable",
                    "items": [],
                }
                warnings.append(f"{label}: HTTP 403")
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
            if source in {"italo", "fincantieri", "formez"}:
                print(f"{SOURCE_LABELS[source]}: controllo non disponibile in questo run. Dettaglio: {exc}")
                snapshot["sources"][source] = {
                    "label": SOURCE_LABELS[source],
                    "status": "unavailable",
                    "items": [],
                }
                warnings.append(f"{SOURCE_LABELS[source]}: {exc}")
                continue

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

    if warnings or errors:
        lines = [f"Pic_Job_Finder_Bot - anomalie {now_rome()}", ""]
        if warnings:
            lines.append("Sorgenti non disponibili:")
            lines.extend(f"- {item}" for item in warnings)
        if errors:
            if warnings:
                lines.append("")
            lines.append("Errori:")
            lines.extend(f"- {item}" for item in errors)
        try:
            sent = send_error_email("Pic_Job_Finder_Bot - anomalie monitor", "\n".join(lines))
            if sent:
                print("Email anomalie inviata.")
            else:
                print("Email anomalie non configurata: nessuna notifica Telegram inviata per errori.")
        except Exception as mail_exc:
            print(f"ERRORE invio email anomalie: {mail_exc}")

    print("\n=== RIEPILOGO ===")
    if errors:
        print("Controllo completato con anomalie non bloccanti:")
        for error in errors:
            print(f"- {error}")
        # IMPORTANT: technical source errors must never fail the GitHub workflow.
        # This prevents any external `if: failure()` Telegram notifier from firing.
        # Error reporting is handled only by send_error_email() when SMTP is configured.
        return

    print(
        "Leonardo + inPA + Eutalia + Consip + Sogei + AgID + "
        "Invitalia + IPZS + PagoPA + Rome Technopole + AMA Roma + BMTI + SACE + GSE + Terna + Acea + Italo + Fincantieri + ANCI + IFEL + SNA + Centro Studi Tagliacarne + Fondazione Giacomo Brodolini + Fondazione con il Sud + ENAV + Sport e Salute + Gruppo FS Italiane + Autostrade per l Italia + InfoCamere + Formez PA + Sviluppo Lavoro Italia + PN Capacita per la Coesione + Unioncamere + AGENAS + Agenzia ICE + INAPP + CDP controllati."
    )
    print("Controllo completato.")


if __name__ == "__main__":
    main()
