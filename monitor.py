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
CONSIP_URL = "https://www.consip.it/lavora-con-noi/posizioni?field_pos_stato_value=All&page=0"
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


def absolute_url(base, href):
    return urllib.parse.urljoin(base, html.unescape(href)).split("#", 1)[0]
	@@ -437,6 +468,7 @@ def get_leonardo_jobs():
            "posted": job.get("postedOn", ""),
            "url": "https://leonardocompany.wd3.myworkdayjobs.com/it-IT/LeonardoCareerSite"
            + job.get("externalPath", ""),
        }
        for job in jobs
    ]
	@@ -523,6 +555,7 @@ def get_inpa_items():
                "deadline": format_inpa_date(job.get("dataScadenza")),
                "extra": ", ".join(job.get("entiRiferimento") or []),
                "url": f"https://www.inpa.gov.it/bandi-e-avvisi/dettaglio-bando-avviso/?concorso_id={job_id}",
            }
        )
    return items
	@@ -560,7 +593,7 @@ def get_eutalia_open_notices():
            if headings
            else full.rsplit("/", 1)[-1].replace("-", " ").title()
        )
        notices[full] = {"id": full, "title": title, "url": full + "/"}

    return list(notices.values())

	@@ -569,7 +602,7 @@ def get_eutalia_open_notices():
def get_consip_positions():
    page = fetch_html(CONSIP_URL, 45, 2)
    items = {}
    blacklist = {'chi siamo','category','lavora con noi','scopri','approfondisci','leggi di più','leggi di piu'}
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>/posizioni/[^"\'?/#]+)["\'][^>]*>(?P<label>.*?)</a>', page, re.I|re.S):
        full=absolute_url('https://www.consip.it',m.group('href')).rstrip('/')
        slug=urllib.parse.unquote(full.rsplit('/',1)[-1])
	@@ -784,7 +817,7 @@ def get_pagopa_positions():
    for m in re.finditer(r'<a[^>]+href=["\'](?P<href>(?:https?://www\.pagopa\.it)?/it/lavora-con-noi/jobposition-[^"\']+/)["\'][^>]*>(?P<label>.*?)</a>',sec,re.I|re.S):
        full=absolute_url(PAGOPA_URL,m.group('href'));title=strip_tags(m.group('label'));context=strip_tags(sec[max(0,m.start()-400):min(len(sec),m.end()+400)])
        if not matches_corporate_keywords(title+' '+context):continue
        iid='pagopa:'+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={'id':iid,'title':title,'url':full,'extra':'Corporate keywords'}
    return list(items.values())


	@@ -1082,7 +1115,7 @@ def get_ifel_positions():
        if not any(x in low for x in ('avviso', 'selezione', 'concorso', 'assunzione')):
            continue
        iid = 'ifel:' + hashlib.sha256(full.encode('utf-8')).hexdigest()[:24]
        items[iid] = {'id': iid, 'title': title, 'url': full, 'deadline': dates[-1]}

    return list(items.values())

	@@ -1128,7 +1161,7 @@ def get_tagliacarne_positions():
        title = strip_tags(detail.group('title'))
        full = absolute_url(TAGLIACARNE_OPEN_URL, detail.group('href')).rstrip('/')
        iid = 'tagliacarne:' + hashlib.sha256(full.encode('utf-8')).hexdigest()[:24]
        items[iid] = {'id': iid, 'title': title, 'url': full, 'deadline': dates[-1]}
    return list(items.values())


	@@ -1539,8 +1572,10 @@ def main():
                    {
                        "title": item.get("title", "Titolo non disponibile"),
                        "url": item.get("url", ""),
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
