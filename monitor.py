import json
import os
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
    "salaryMax": None,
    "salaryMin": None,
    "tipoImpiegoId": None,
}


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

    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def notify_all(text):
    for chat_id in AUTHORIZED_CHAT_IDS:
        try:
            send_telegram(chat_id, text)
            print(f"Notifica inviata a {chat_id}")
        except Exception as exc:
            print(f"Errore Telegram per {chat_id}: {exc}")


# =========================================================
# MEMORIA
# =========================================================

def load_memory():
    """
    Supporta sia il vecchio formato:

    {
        "seen": [...]
    }

    sia il nuovo formato:

    {
        "sources": {
            "leonardo": {"seen": [...]},
            "inpa": {"seen": []}
        }
    }

    Gli ID presenti nel vecchio formato vengono attribuiti
    automaticamente a Leonardo.
    """

    if not SEEN_FILE.exists():
        return {
            "sources": {
                "leonardo": {"seen": []},
                "inpa": {"seen": []},
            }
        }

    try:
        data = json.loads(
            SEEN_FILE.read_text(encoding="utf-8")
        )
    except Exception:
        return {
            "sources": {
                "leonardo": {"seen": []},
                "inpa": {"seen": []},
            }
        }

    # Migrazione automatica del vecchio formato Leonardo.
    if "sources" not in data:
        old_seen = data.get("seen", [])

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
            }
        }

    data.setdefault("sources", {})
    data["sources"].setdefault("leonardo", {"seen": []})
    data["sources"].setdefault("inpa", {"seen": []})

    return data


def save_memory(memory):
    memory["last_update"] = (
        datetime.now(timezone.utc).isoformat()
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
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def get_leonardo_jobs():
    jobs = []
    offset = 0

    while True:
        response = leonardo_request(offset)
        batch = response.get("jobPostings", [])

        if not batch:
            break

        jobs.extend(batch)

        total = response.get("total", len(jobs))
        offset += len(batch)

        if offset >= total:
            break

    return jobs


def leonardo_job_id(job):
    external_path = job.get("externalPath")

    if external_path:
        return external_path

    return (
        f"{job.get('title', '')}|"
        f"{job.get('locationsText', '')}"
    )


def leonardo_job_url(job):
    external_path = job.get("externalPath", "")

    return (
        "https://leonardocompany.wd3.myworkdayjobs.com/"
        "it-IT/LeonardoCareerSite"
        f"{external_path}"
    )


def process_leonardo(memory):
    print("")
    print("=== LEONARDO ===")

    jobs = get_leonardo_jobs()

    print(
        f"Offerte Leonardo trovate: {len(jobs)}"
    )

    current_ids = {
        leonardo_job_id(job)
        for job in jobs
    }

    seen_ids = set(
        memory["sources"]["leonardo"].get("seen", [])
    )

    # Solo nel caso di installazione completamente nuova.
    if not seen_ids:
        print(
            "Leonardo non inizializzato: "
            "registro le offerte esistenti."
        )

        memory["sources"]["leonardo"]["seen"] = sorted(
            current_ids
        )

        return

    new_jobs = [
        job
        for job in jobs
        if leonardo_job_id(job) not in seen_ids
    ]

    print(
        f"Nuove offerte Leonardo: {len(new_jobs)}"
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

        posted = job.get("postedOn", "")
        url = leonardo_job_url(job)

        message = (
            "🚨 NUOVA OFFERTA LEONARDO\n\n"
            f"💼 {title}\n"
            f"📍 {location}\n"
            f"📅 {posted}\n\n"
            "🏷 Communications / Sales & Marketing\n\n"
            f"🔗 {url}\n\n"
            "🤖 Pic_Job_Finder_Bot"
        )

        notify_all(message)

    updated_seen = seen_ids | current_ids

    memory["sources"]["leonardo"]["seen"] = sorted(
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
        data=json.dumps(INPA_PAYLOAD).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://www.inpa.gov.it",
            "Referer": "https://www.inpa.gov.it/",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def get_inpa_jobs():
    jobs = []
    page = 0

    while True:
        response = inpa_request(
            page=page,
            size=50,
        )

        batch = response.get("content", [])

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
    return str(job.get("id", ""))


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
            value.replace("Z", "+00:00")
        )

        return dt.strftime("%d/%m/%Y %H:%M")

    except Exception:
        return value


def process_inpa(memory):
    print("")
    print("=== INPA ===")

    jobs = get_inpa_jobs()

    print(
        f"Bandi inPA OPEN trovati: {len(jobs)}"
    )

    current_ids = {
        inpa_job_id(job)
        for job in jobs
        if inpa_job_id(job)
    }

    seen_ids = set(
        memory["sources"]["inpa"].get("seen", [])
    )

    # Primo avvio inPA:
    # registra tutto senza inviare notifiche.
    if not seen_ids:
        print(
            "Prima inizializzazione inPA."
        )

        print(
            f"Registro {len(current_ids)} bandi "
            "esistenti senza notificare."
        )

        memory["sources"]["inpa"]["seen"] = sorted(
            current_ids
        )

        return

    new_jobs = [
        job
        for job in jobs
        if (
            inpa_job_id(job)
            and inpa_job_id(job) not in seen_ids
        )
    ]

    print(
        f"Nuovi bandi inPA: {len(new_jobs)}"
    )

    for job in new_jobs:
        title = (
            job.get("figuraRicercata")
            or job.get("titolo")
            or "Titolo non disponibile"
        )

        enti = job.get("entiRiferimento") or []

        ente = (
            ", ".join(enti)
            if enti
            else "Ente non disponibile"
        )

        sedi = job.get("sedi") or []

        location = (
            ", ".join(sedi)
            if sedi
            else "Sede non disponibile"
        )

        num_posti = job.get(
            "numPosti",
            "Non disponibile",
        )

        published = format_inpa_date(
            job.get("dataPubblicazione")
        )

        deadline = format_inpa_date(
            job.get("dataScadenza")
        )

        url = inpa_job_url(job)

        message = (
            "🚨 NUOVO BANDO inPA\n\n"
            f"💼 {title}\n"
            f"🏛 {ente}\n"
            f"📍 {location}\n"
            f"👥 Posti: {num_posti}\n\n"
            f"📅 Pubblicato: {published}\n"
            f"⏳ Scadenza: {deadline}\n\n"
            "🏷 Comunicazione e informazione\n\n"
            f"🔗 {url}\n\n"
            "🤖 Pic_Job_Finder_Bot"
        )

        notify_all(message)

    updated_seen = seen_ids | current_ids

    memory["sources"]["inpa"]["seen"] = sorted(
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
    print("Avvio controllo sorgenti...")

    memory = load_memory()

    errors = []

    # Leonardo e inPA vengono gestiti separatamente.
    # Se una sorgente ha problemi, proviamo comunque l'altra.

    try:
        process_leonardo(memory)
    except Exception as exc:
        print(
            f"ERRORE monitor Leonardo: {exc}"
        )
        errors.append(
            f"Leonardo: {exc}"
        )

    try:
        process_inpa(memory)
    except Exception as exc:
        print(
            f"ERRORE monitor inPA: {exc}"
        )
        errors.append(
            f"inPA: {exc}"
        )

    save_memory(memory)

    print("")
    print("=== RIEPILOGO ===")

    if errors:
        print(
            "Controllo completato con errori:"
        )

        for error in errors:
            print(f"- {error}")

        # Facciamo fallire l'Action così GitHub
        # segnala chiaramente il problema.
        sys.exit(1)

    print(
        "Leonardo + inPA controllati correttamente."
    )

    print("Controllo completato.")


if __name__ == "__main__":
    main()
