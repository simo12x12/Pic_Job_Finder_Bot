import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------
# CONFIGURAZIONE
# ---------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

AUTHORIZED_CHAT_IDS = [
    "2020881944",
    # In futuro aggiungeremo qui la seconda persona
]

SEEN_FILE = Path("seen_jobs.json")

WORKDAY_ENDPOINT = (
    "https://leonardocompany.wd3.myworkdayjobs.com/"
    "wday/cxs/leonardocompany/LeonardoCareerSite/jobs"
)

# Filtri ricavati dall'URL Leonardo che ci hai fornito
APPLIED_FACETS = {
    "locationCountry": [
        "8cd04a563fd94da7b06857a79faaf815"
    ],
    "jobFamilyGroup": [
        "8f7876e90e9c0101f751f430c4290000",
        "8f7876e90e9c0101f751e65634a60000",
    ],
}


# ---------------------------------------------------------
# TELEGRAM
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# MEMORIA OFFERTE
# ---------------------------------------------------------

def load_seen_jobs():
    if not SEEN_FILE.exists():
        return set()

    try:
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        return set(data.get("seen", []))
    except Exception:
        return set()


def save_seen_jobs(job_ids):
    data = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "seen": sorted(job_ids),
    }

    SEEN_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------
# LEONARDO / WORKDAY
# ---------------------------------------------------------

def workday_request(offset=0):
    payload = {
        "appliedFacets": APPLIED_FACETS,
        "limit": 20,
        "offset": offset,
        "searchText": "",
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        WORKDAY_ENDPOINT,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_leonardo_jobs():
    jobs = []
    offset = 0

    while True:
        response = workday_request(offset)

        batch = response.get("jobPostings", [])

        if not batch:
            break

        jobs.extend(batch)

        total = response.get("total", len(jobs))

        offset += len(batch)

        if offset >= total:
            break

    return jobs


def make_job_id(job):
    path = job.get("externalPath")

    if path:
        return path

    return (
        f"{job.get('title', '')}|"
        f"{job.get('locationsText', '')}"
    )


def make_job_url(job):
    external_path = job.get("externalPath", "")

    return (
        "https://leonardocompany.wd3.myworkdayjobs.com/"
        "it-IT/LeonardoCareerSite"
        f"{external_path}"
    )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    if not TELEGRAM_BOT_TOKEN:
        print("ERRORE: TELEGRAM_BOT_TOKEN non configurato.")
        sys.exit(1)

    print("Pic_Job_Finder_Bot")
    print("Controllo Leonardo in corso...")

    jobs = get_leonardo_jobs()

    print(f"Offerte trovate con i filtri Leonardo: {len(jobs)}")

    current_ids = {
        make_job_id(job)
        for job in jobs
    }

    seen_ids = load_seen_jobs()

    # -----------------------------------------------------
    # PRIMO AVVIO
    # -----------------------------------------------------

    if not seen_ids:

        print("Prima esecuzione.")
        print("Registro le offerte esistenti senza notificare.")

        save_seen_jobs(current_ids)

        print(
            f"Inizializzazione completata: "
            f"{len(current_ids)} offerte memorizzate."
        )

        return

    # -----------------------------------------------------
    # CONTROLLI SUCCESSIVI
    # -----------------------------------------------------

    new_jobs = [
        job
        for job in jobs
        if make_job_id(job) not in seen_ids
    ]

    print(f"Nuove offerte trovate: {len(new_jobs)}")

    for job in new_jobs:

        title = job.get("title", "Titolo non disponibile")
        location = job.get("locationsText", "Località non disponibile")
        posted = job.get("postedOn", "")
        url = make_job_url(job)

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

    # Manteniamo memoria anche delle offerte viste in passato.
    # In questo modo una posizione rimossa e successivamente
    # riapparsa non viene automaticamente considerata nuova.

    updated_seen = seen_ids | current_ids

    save_seen_jobs(updated_seen)

    print("Controllo completato.")


if __name__ == "__main__":
    import urllib.parse
    main()
