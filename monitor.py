import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


# =========================================================
# CONFIGURAZIONE GENERALE
# =========================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

AUTHORIZED_CHAT_IDS = [
    "2020881944",
    # In futuro aggiungeremo qui la seconda persona.
]

SEEN_FILE = Path("seen_jobs.json")


# =========================================================
# LEONARDO
# Italia + Communications + Sales & Marketing
# =========================================================

LEONARDO_ENDPOINT = (
    "https://leonardocompany.wd3.myworkdayjobs.com/"
    "wday/cxs/leonardocompany/LeonardoCareerSite/jobs"
)

LEONARDO_FACETS = {
    "locationCountry": [
        "8cd04a563fd94da7b06857a79faaf815"
    ],
    "jobFamilyGroup": [
        "8f7876e90e9c0101f751f430c4290000",
        "8f7876e90e9c0101f751e65634a60000",
    ],
}


# =========================================================
# INPA
# OPEN + Comunicazione e informazione
# =========================================================

INPA_ENDPOINT = (
    "https://portale.inpa.gov.it/"
    "concorsi-smart/api/concorso-public-area/search-better"
)

INPA_PAYLOAD = {
    "text": "",
    "categoriaId": None,
    "regioneId": None,
    "status": ["OPEN"],
    "settoreId": "b078865c126040558601",
    "dateFrom": None,
    "dateTo": None,
    "enteRiferimentoName": "",
    "livelliAnzianitaIds": None,
    "provinciaCodice": None,
    "regioneId": None,
    "salaryMax": None,
    "salaryMin": None,
    "tipoImpiegoId": None,
}


# =========================================================
# EUTALIA
# Tutti gli Avvisi Aperti
# =========================================================

EUTALIA_URL = (
    "https://www.eutalia.eu/"
    "selezione-personale-ed-esperti/"
)


# =========================================================
# TELEGRAM
# =========================================================

def send_telegram(chat_id, text):
    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "false",
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:
        response.read()


def notify_all(text):
    for chat_id in AUTHORIZED_CHAT_IDS:
        try:
            send_telegram(chat_id, text)
            print(
                f"Notifica inviata a {chat_id}"
            )

        except Exception as exc:
            print(
                f"Errore Telegram per "
                f"{chat_id}: {exc}"
            )


# =========================================================
# MEMORIA
# =========================================================

def empty_memory():
    return {
        "sources": {
            "leonardo": {
                "seen": []
            },
            "inpa": {
                "seen": []
            },
            "eutalia": {
                "seen": []
            },
        }
    }


def load_memory():
    """
    Supporta automaticamente sia il vecchio formato:

    {
        "seen": [...]
    }

    sia il nuovo formato:

    {
        "sources": {
            "leonardo": {"seen": [...]},
            "inpa": {"seen": [...]},
            "eutalia": {"seen": [...]}
        }
    }

    Gli ID del vecchio formato vengono attribuiti
    automaticamente a Leonardo.
    """

    if not SEEN_FILE.exists():
        return empty_memory()

    try:
        data = json.loads(
            SEEN_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:
        print(
            f"Errore lettura memoria: {exc}"
        )

        return empty_memory()

    # =====================================================
    # MIGRAZIONE DEL VECCHIO FORMATO
    # =====================================================

    if "sources" not in data:
        old_seen = data.get(
            "seen",
            [],
        )

        print(
            f"Migrazione memoria Leonardo: "
            f"{len(old_seen)} ID esistenti."
        )

        data = {
            "sources": {
                "leonardo": {
                    "seen": old_seen
                },
                "inpa": {
                    "seen": []
                },
                "eutalia": {
                    "seen": []
                },
            }
        }

    # =====================================================
    # GARANTIAMO CHE ESISTANO TUTTE LE SORGENTI
    # =====================================================

    data.setdefault(
        "sources",
        {},
    )

    data["sources"].setdefault(
        "leonardo",
        {"seen": []},
    )

    data["sources"].setdefault(
        "inpa",
        {"seen": []},
    )

    data["sources"].setdefault(
        "eutalia",
        {"seen": []},
    )

    return data


def save_memory(memory):
    memory["last_update"] = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    SEEN_FILE.write_text(
        json.dumps(
            memory,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# =========================================================
# LEONARDO
# =========================================================

def leonardo_request(offset=0):
    payload = {
        "appliedFacets": LEONARDO_FACETS,
        "limit": 20,
        "offset": offset,
        "searchText": "",
    }

    request = urllib.request.Request(
        LEONARDO_ENDPOINT,
        data=json.dumps(
            payload
        ).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type":
                "application/json",

            "Accept":
                "application/json",

            "User-Agent":
                "Mozilla/5.0",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:
        return json.loads(
            response.read().decode(
                "utf-8"
            )
        )


def get_leonardo_jobs():
    jobs = []
    offset = 0

    while True:
        response = leonardo_request(
            offset
        )

        batch = response.get(
            "jobPostings",
            [],
        )

        if not batch:
            break

        jobs.extend(batch)

        total = response.get(
            "total",
            len(jobs),
        )

        offset += len(batch)

        if offset >= total:
            break

    return jobs


def leonardo_job_id(job):
    external_path = job.get(
        "externalPath"
    )

    if external_path:
        return external_path

    return (
        f"{job.get('title', '')}|"
        f"{job.get('locationsText', '')}"
    )


def leonardo_job_url(job):
    external_path = job.get(
        "externalPath",
        "",
    )

    return (
        "https://leonardocompany."
        "wd3.myworkdayjobs.com/"
        "it-IT/LeonardoCareerSite"
        f"{external_path}"
    )


def process_leonardo(memory):
    print("")
    print("=== LEONARDO ===")

    jobs = get_leonardo_jobs()

    print(
        f"Offerte Leonardo trovate: "
        f"{len(jobs)}"
    )

    current_ids = {
        leonardo_job_id(job)
        for job in jobs
    }

    seen_ids = set(
        memory["sources"]
        ["leonardo"]
        .get("seen", [])
    )

    # Prima inizializzazione
    if not seen_ids:
        print(
            "Leonardo non inizializzato."
        )

        print(
            f"Registro {len(current_ids)} "
            "offerte senza notificare."
        )

        memory["sources"][
            "leonardo"
        ]["seen"] = sorted(
            current_ids
        )

        return

    new_jobs = [
        job
        for job in jobs
        if (
            leonardo_job_id(job)
            not in seen_ids
        )
    ]

    print(
        f"Nuove offerte Leonardo: "
        f"{len(new_jobs)}"
    )

    for job in new_jobs:
        title = job.get(
            "title",
            "Titolo non disponibile",
        )

        location = job.get(
            "locationsText",
            "Località non disponibile",
        )

        posted = job.get(
            "postedOn",
            "",
        )

        url = leonardo_job_url(job)

        detected = datetime.now().strftime(
            "%d/%m/%Y %H:%M"
        )

        message = (
            "🚨 NUOVA OFFERTA LEONARDO\n\n"
            f"💼 {title}\n"
            f"📍 {location}\n"
            f"📅 Pubblicazione: {posted}\n"
            f"🔔 Rilevata: {detected}\n\n"
            "🏷 Communications / "
            "Sales & Marketing\n\n"
            f"🔗 {url}\n\n"
            "🤖 Pic_Job_Finder_Bot"
        )

        notify_all(message)

    updated_seen = (
        seen_ids | current_ids
    )

    memory["sources"][
        "leonardo"
    ]["seen"] = sorted(
        updated_seen
    )


# =========================================================
# INPA
# =========================================================

def inpa_request(page=0, size=50):
    url = (
        f"{INPA_ENDPOINT}"
        f"?page={page}&size={size}"
    )

    request = urllib.request.Request(
        url,
        data=json.dumps(
            INPA_PAYLOAD
        ).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type":
                "application/json",

            "Accept":
                "application/json",

            "User-Agent":
                "Mozilla/5.0",

            "Origin":
                "https://www.inpa.gov.it",

            "Referer":
                "https://www.inpa.gov.it/",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:

        return json.loads(
            response.read().decode(
                "utf-8"
            )
        )


def get_inpa_jobs():
    jobs = []
    page = 0

    while True:
        response = inpa_request(
            page=page,
            size=50,
        )

        batch = response.get(
            "content",
            [],
        )

        jobs.extend(batch)

        total_pages = response.get(
            "totalPages",
            1,
        )

        page += 1

        if page >= total_pages:
            break

    return jobs


def inpa_job_id(job):
    return str(
        job.get(
            "id",
            "",
        )
    )


def inpa_job_url(job):
    job_id = inpa_job_id(job)

    return (
        "https://www.inpa.gov.it/"
        "bandi-e-avvisi/"
        "dettaglio-bando-avviso/"
        f"?concorso_id={job_id}"
    )


def format_inpa_date(value):
    if not value:
        return "Non disponibile"

    try:
        dt = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        # Ora italiana.
        local_dt = dt.astimezone()

        return local_dt.strftime(
            "%d/%m/%Y %H:%M"
        )

    except Exception:
        return value


def process_inpa(memory):
    print("")
    print("=== INPA ===")

    jobs = get_inpa_jobs()

    print(
        f"Bandi inPA OPEN trovati: "
        f"{len(jobs)}"
    )

    current_ids = {
        inpa_job_id(job)
        for job in jobs
        if inpa_job_id(job)
    }

    seen_ids = set(
        memory["sources"]
        ["inpa"]
        .get("seen", [])
    )

    # Prima inizializzazione inPA
    if not seen_ids:
        print(
            "Prima inizializzazione inPA."
        )

        print(
            f"Registro {len(current_ids)} "
            "bandi esistenti "
            "senza notificare."
        )

        memory["sources"][
            "inpa"
        ]["seen"] = sorted(
            current_ids
        )

        return

    new_jobs = [
        job
        for job in jobs
        if (
            inpa_job_id(job)
            and
            inpa_job_id(job)
            not in seen_ids
        )
    ]

    print(
        f"Nuovi bandi inPA: "
        f"{len(new_jobs)}"
    )

    for job in new_jobs:
        title = (
            job.get(
                "figuraRicercata"
            )
            or
            job.get(
                "titolo"
            )
            or
            "Titolo non disponibile"
        )

        enti = (
            job.get(
                "entiRiferimento"
            )
            or []
        )

        ente = (
            ", ".join(enti)
            if enti
            else
            "Ente non disponibile"
        )

        sedi = (
            job.get(
                "sedi"
            )
            or []
        )

        location = (
            ", ".join(sedi)
            if sedi
            else
            "Sede non disponibile"
        )

        num_posti = job.get(
            "numPosti",
            "Non disponibile",
        )

        published = format_inpa_date(
            job.get(
                "dataPubblicazione"
            )
        )

        deadline = format_inpa_date(
            job.get(
                "dataScadenza"
            )
        )

        url = inpa_job_url(job)

        detected = datetime.now().strftime(
            "%d/%m/%Y %H:%M"
        )

        message = (
            "🚨 NUOVO BANDO inPA\n\n"
            f"💼 {title}\n"
            f"🏛 {ente}\n"
            f"📍 {location}\n"
            f"👥 Posti: {num_posti}\n\n"
            f"📅 Pubblicato: {published}\n"
            f"⏳ Scadenza: {deadline}\n"
            f"🔔 Rilevato: {detected}\n\n"
            "🏷 Comunicazione e "
            "informazione\n\n"
            f"🔗 {url}\n\n"
            "🤖 Pic_Job_Finder_Bot"
        )

        notify_all(message)

    updated_seen = (
        seen_ids | current_ids
    )

    memory["sources"][
        "inpa"
    ]["seen"] = sorted(
        updated_seen
    )


# =========================================================
# EUTALIA
# =========================================================

def get_eutalia_open_notices():
    request = urllib.request.Request(
        EUTALIA_URL,
        headers={
            "User-Agent":
                "Mozilla/5.0",

            "Accept":
                "text/html,"
                "application/xhtml+xml",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:

        page = response.read().decode(
            "utf-8",
            errors="replace",
        )

    notices = []

    # Cerchiamo tutti i link che puntano
    # alle pagine degli avvisi Eutalia.
    link_pattern = re.compile(
        r'<a[^>]+href=["\']'
        r'(https?://www\.eutalia\.eu/'
        r'avvisi/[^"\']+)'
        r'["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    matches = list(
        link_pattern.finditer(page)
    )

    seen_urls = set()

    for match in matches:
        url = html.unescape(
            match.group(1)
        ).rstrip("/")

        if url in seen_urls:
            continue

        seen_urls.add(url)

        # Esaminiamo la zona immediatamente
        # precedente al link. In ogni card Eutalia
        # appare lo stato dell'avviso.
        start = max(
            0,
            match.start() - 2500,
        )

        end = min(
            len(page),
            match.end() + 500,
        )

        context = page[
            start:end
        ]

        context_text = re.sub(
            r"<[^>]+>",
            " ",
            context,
        )

        context_text = html.unescape(
            context_text
        )

        context_text = re.sub(
            r"\s+",
            " ",
            context_text,
        ).strip()

        # Ci interessano esclusivamente
        # gli Avvisi Aperti.
        if (
            "Avviso Aperto"
            not in context_text
        ):
            continue

        title_html = match.group(2)

        title = re.sub(
            r"<[^>]+>",
            "",
            title_html,
        )

        title = html.unescape(
            title
        )

        title = re.sub(
            r"\s+",
            " ",
            title,
        ).strip()

        # A volte il link contiene solamente
        # "Leggi di più".
        # In quel caso recuperiamo il titolo
        # dall'heading della card.
        if (
            not title
            or
            "leggi di" in title.lower()
        ):
            headings = re.findall(
                r"<h[1-6][^>]*>"
                r"(.*?)"
                r"</h[1-6]>",
                context,
                re.IGNORECASE |
                re.DOTALL,
            )

            if headings:
                title = re.sub(
                    r"<[^>]+>",
                    "",
                    headings[-1],
                )

                title = html.unescape(
                    title
                )

                title = re.sub(
                    r"\s+",
                    " ",
                    title,
                ).strip()

        if not title:
            title = (
                "Nuovo avviso Eutalia"
            )

        notices.append({
            "id": url,
            "title": title,
            "url": url + "/",
        })

    return notices


def process_eutalia(memory):
    print("")
    print("=== EUTALIA ===")

    notices = (
        get_eutalia_open_notices()
    )

    print(
        f"Avvisi Eutalia aperti trovati: "
        f"{len(notices)}"
    )

    current_ids = {
        notice["id"]
        for notice in notices
    }

    seen_ids = set(
        memory["sources"]
        ["eutalia"]
        .get("seen", [])
    )

    # Prima inizializzazione Eutalia.
    # Memorizziamo quelli già presenti
    # senza inviare notifiche.
    if not seen_ids:
        print(
            "Prima inizializzazione Eutalia."
        )

        print(
            f"Registro {len(current_ids)} "
            "avvisi aperti senza notificare."
        )

        memory["sources"][
            "eutalia"
        ]["seen"] = sorted(
            current_ids
        )

        return

    new_notices = [
        notice
        for notice in notices
        if (
            notice["id"]
            not in seen_ids
        )
    ]

    print(
        f"Nuovi avvisi Eutalia: "
        f"{len(new_notices)}"
    )

    for notice in new_notices:
        detected = datetime.now().strftime(
            "%d/%m/%Y %H:%M"
        )

        message = (
            "🚨 NUOVO AVVISO EUTALIA\n\n"
            f"📋 {notice['title']}\n\n"
            "🏢 Eutalia\n"
            "🟢 Avviso Aperto\n"
            f"🔔 Rilevato: {detected}\n\n"
            f"🔗 {notice['url']}\n\n"
            "🤖 Pic_Job_Finder_Bot"
        )

        notify_all(message)

    updated_seen = (
        seen_ids | current_ids
    )

    memory["sources"][
        "eutalia"
    ]["seen"] = sorted(
        updated_seen
    )


# =========================================================
# MAIN
# =========================================================

def main():
    if not TELEGRAM_BOT_TOKEN:
        print(
            "ERRORE: TELEGRAM_BOT_TOKEN "
            "non configurato."
        )

        sys.exit(1)

    print("Pic_Job_Finder_Bot")

    print(
        "Avvio controllo sorgenti..."
    )

    memory = load_memory()

    errors = []

    # =====================================================
    # LEONARDO
    # =====================================================

    try:
        process_leonardo(
            memory
        )

    except Exception as exc:
        print(
            f"ERRORE monitor Leonardo: "
            f"{exc}"
        )

        errors.append(
            f"Leonardo: {exc}"
        )

    # =====================================================
    # INPA
    # =====================================================

    try:
        process_inpa(
            memory
        )

    except Exception as exc:
        print(
            f"ERRORE monitor inPA: "
            f"{exc}"
        )

        errors.append(
            f"inPA: {exc}"
        )

    # =====================================================
    # EUTALIA
    # =====================================================

    try:
        process_eutalia(
            memory
        )

    except Exception as exc:
        print(
            f"ERRORE monitor Eutalia: "
            f"{exc}"
        )

        errors.append(
            f"Eutalia: {exc}"
        )

    # =====================================================
    # SALVATAGGIO MEMORIA
    # =====================================================

    save_memory(
        memory
    )

    print("")
    print("=== RIEPILOGO ===")

    if errors:
        print(
            "Controllo completato "
            "con errori:"
        )

        for error in errors:
            print(
                f"- {error}"
            )

        # Facciamo fallire GitHub Actions.
        # Lo step di alert che abbiamo aggiunto
        # a monitor.yml ci notificherà su Telegram.
        sys.exit(1)

    print(
        "Leonardo + inPA + Eutalia "
        "controllati correttamente."
    )

    print(
        "Controllo completato."
    )


if __name__ == "__main__":
    main()
