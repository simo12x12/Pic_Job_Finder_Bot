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
CDP_KEYWORDS = ["comunicazione", "communication", "marketing", "media", "social"]

LEONARDO_FACETS = {
    "locationCountry": ["8cd04a563fd94da7b06857a79faaf815"],
    "jobFamilyGroup": ["8f7876e90e9c0101f751f430c4290000", "8f7876e90e9c0101f751e65634a60000"],
}
INPA_BASE_PAYLOAD = {
    "text": "", "categoriaId": None, "regioneId": None, "status": ["OPEN"], "settoreId": None,
    "dateFrom": None, "dateTo": None, "enteRiferimentoName": "", "livelliAnzianitaIds": None,
    "provinciaCodice": None, "salaryMax": None, "salaryMin": None, "tipoImpiegoId": None,
}
INPA_COMMUNICATION_SECTOR = "b078865c126040558601"
INPA_SEARCH_TERMS = ["marketing", "comunicazione istituzionale"]

SOURCE_NAMES = ["leonardo", "inpa", "eutalia", "consip", "sogei", "agid", "invitalia", "cdp"]
SOURCE_LABELS = {
    "leonardo": "Leonardo", "inpa": "inPA", "eutalia": "Eutalia", "consip": "Consip",
    "sogei": "Sogei", "agid": "AgID", "invitalia": "Invitalia", "cdp": "CDP",
}
MEMORY_SCHEMA_VERSION = 6

def now_rome(): return datetime.now(ROME).strftime("%d/%m/%Y %H:%M")
def normalize_space(text): return re.sub(r"\s+", " ", html.unescape(text or "")).strip()
def strip_tags(text): return normalize_space(re.sub(r"<[^>]+>", " ", text or ""))
def absolute_url(base, href): return urllib.parse.urljoin(base, html.unescape(href)).split("#", 1)[0]

def fetch_html(url, timeout=30, retries=1):
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml", "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                print(f"Tentativo {attempt + 1}/{retries} fallito per {url}: {exc}. Riprovo...")
                time.sleep(3)
    raise last_error

def send_telegram(chat_id, text):
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "disable_web_page_preview": "false"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as response: response.read()

def notify_all(text):
    errors = []
    for chat_id in AUTHORIZED_CHAT_IDS:
        try: send_telegram(chat_id, text); print(f"Notifica inviata a {chat_id}")
        except Exception as exc: errors.append(f"{chat_id}: {exc}")
    if errors: raise RuntimeError("; ".join(errors))

def empty_source(): return {"initialized": False, "seen": []}
def empty_memory(): return {"schema_version": MEMORY_SCHEMA_VERSION, "sources": {n: empty_source() for n in SOURCE_NAMES}}

def load_memory():
    if not SEEN_FILE.exists(): return empty_memory()
    data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    if "sources" not in data:
        old = data.get("seen", []); data = empty_memory(); data["sources"]["leonardo"] = {"initialized": True, "seen": old}
    data.setdefault("sources", {})
    if data.get("schema_version", 1) < 6:
        a = data["sources"].pop("invitalia_jobs", {"seen": []}); b = data["sources"].pop("invitalia_consulting", {"seen": []})
        data["sources"]["invitalia"] = {"initialized": a.get("initialized", False) or b.get("initialized", False), "seen": sorted(set(a.get("seen", [])) | set(b.get("seen", [])))}
    data["schema_version"] = MEMORY_SCHEMA_VERSION
    for n in SOURCE_NAMES:
        data["sources"].setdefault(n, empty_source()); data["sources"][n].setdefault("seen", []); data["sources"][n].setdefault("initialized", False)
    return data

def save_memory(memory):
    memory["last_update"] = datetime.now(timezone.utc).isoformat()
    SEEN_FILE.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")

def process_items(memory, source, items, formatter):
    src = memory["sources"][source]; current = {x["id"] for x in items if x.get("id")}; seen = set(src.get("seen", []))
    if not src.get("initialized", False):
        print(f"Prima inizializzazione {source}: registro {len(current)} elementi senza notificare.")
        src["initialized"] = True; src["seen"] = sorted(current); return 0
    new = [x for x in items if x.get("id") and x["id"] not in seen]
    print(f"Nuovi elementi {source}: {len(new)}")
    for item in new: notify_all(formatter(item))
    src["seen"] = sorted(seen | current)
    return len(new)

def standard_job_message(source, title, url, published=None, deadline=None, extra=None):
    lines = [f"🚨 NUOVA OPPORTUNITÀ - {source.upper()}", "", f"💼 {title}", f"🏢 Fonte: {source}"]
    if published: lines.append(f"📅 Pubblicata: {published}")
    if deadline: lines.append(f"⏳ Scadenza: {deadline}")
    if extra: lines.append(f"🏷 {extra}")
    lines += [f"🔔 Rilevata: {now_rome()}", "", f"🔗 {url}", "", "🤖 Pic_Job_Finder_Bot"]
    return "\n".join(lines)

def leonardo_request(offset=0):
    payload = {"appliedFacets": LEONARDO_FACETS, "limit": 20, "offset": offset, "searchText": ""}
    req = urllib.request.Request(LEONARDO_ENDPOINT, data=json.dumps(payload).encode(), method="POST", headers={"Content-Type":"application/json","Accept":"application/json","User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read().decode())

def get_leonardo_jobs():
    jobs=[]; offset=0
    while True:
        r=leonardo_request(offset); batch=r.get("jobPostings", [])
        if not batch: break
        jobs += batch; offset += len(batch)
        if offset >= r.get("total", len(jobs)): break
    return [{"id":j.get("externalPath") or j.get("title",""),"title":j.get("title","Titolo non disponibile"),"location":j.get("locationsText","Località non disponibile"),"posted":j.get("postedOn",""),"url":"https://leonardocompany.wd3.myworkdayjobs.com/it-IT/LeonardoCareerSite"+j.get("externalPath","")} for j in jobs]

def inpa_request(payload,page=0,size=50):
    req=urllib.request.Request(f"{INPA_ENDPOINT}?page={page}&size={size}",data=json.dumps(payload).encode(),method="POST",headers={"Content-Type":"application/json","Accept":"application/json","User-Agent":"Mozilla/5.0","Origin":"https://www.inpa.gov.it","Referer":"https://www.inpa.gov.it/"})
    with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode())
def get_inpa_results(payload):
    jobs=[]; page=0
    while True:
        r=inpa_request(payload,page,50); jobs+=r.get("content",[]); page+=1
        if page>=r.get("totalPages",1):break
    return jobs
def format_inpa_date(v):
    if not v:return "Non disponibile"
    try:return datetime.fromisoformat(v.replace("Z","+00:00")).astimezone(ROME).strftime("%d/%m/%Y %H:%M")
    except:return v
def get_inpa_items():
    by={}; p=dict(INPA_BASE_PAYLOAD); p["settoreId"]=INPA_COMMUNICATION_SECTOR; results=get_inpa_results(p); print(f"inPA - Comunicazione e informazione: {len(results)}")
    for j in results:
        if j.get("id"):by[str(j["id"])]=j
    for term in INPA_SEARCH_TERMS:
        p=dict(INPA_BASE_PAYLOAD);p["text"]=term; results=get_inpa_results(p);print(f"inPA - ricerca '{term}': {len(results)}")
        for j in results:
            if j.get("id"):by[str(j["id"])]=j
    print(f"inPA - risultati unici complessivi: {len(by)}")
    out=[]
    for j in by.values():
        jid=str(j.get("id",""));out.append({"id":jid,"title":j.get("figuraRicercata") or j.get("titolo") or "Titolo non disponibile","published":format_inpa_date(j.get("dataPubblicazione")),"deadline":format_inpa_date(j.get("dataScadenza")),"extra":", ".join(j.get("entiRiferimento") or []),"url":f"https://www.inpa.gov.it/bandi-e-avvisi/dettaglio-bando-avviso/?concorso_id={jid}"})
    return out

def get_eutalia_open_notices():
    page=fetch_html(EUTALIA_URL,45,2); notices={}; marks=list(re.finditer(r'Avviso\s+(Aperto|Chiuso)',page,re.I))
    for i,m in enumerate(marks):
        if m.group(1).lower()!="aperto":continue
        seg=page[m.start():(marks[i+1].start() if i+1<len(marks) else min(len(page),m.end()+5000))]
        lm=re.search(r'href=["\'](?P<url>(?:https?://www\.eutalia\.eu)?/avvisi/[^"\']+)["\']',seg,re.I)
        if not lm:continue
        full=absolute_url(EUTALIA_URL,lm.group("url")).rstrip("/");heads=re.findall(r'<h[2-4][^>]*>(.*?)</h[2-4]>',seg,re.I|re.S);title=strip_tags(heads[0]) if heads else full.rsplit("/",1)[-1].replace("-"," ").title();notices[full]={"id":full,"title":title,"url":full+"/"}
    return list(notices.values())

def get_consip_positions():
    page=fetch_html(CONSIP_URL,45,2);items={}
    cards=re.findall(r'<h3[^>]*>(?P<title>.*?)</h3>.*?<a[^>]+href=["\'](?P<href>/posizioni/[^"\'?/#]+)["\'][^>]*>.*?</a>',page,re.I|re.S)
    for t,h in cards:
        full=absolute_url("https://www.consip.it",h).rstrip("/");items[full]={"id":full,"title":strip_tags(t),"url":full}
    return list(items.values())

def get_sogei_positions():
    page=fetch_html(SOGEI_TRANSPARENCY_URL,45,2); a=re.search(r'Avvisi\s+di\s+selezione\s+in\s+corso',page,re.I); b=re.search(r'Avvisi\s+di\s+selezione\s+conclusi',page,re.I)
    if not a:raise RuntimeError("Sezione Sogei non trovata")
    sec=page[a.end():(b.start() if b and b.start()>a.end() else len(page))]
    if "al momento non esistono posizioni disponibili" in strip_tags(sec).lower():return []
    items={}
    for href,label_html in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',sec,re.I|re.S):
        label=strip_tags(label_html);full=absolute_url(SOGEI_TRANSPARENCY_URL,href);cm=re.search(r'\((20\d{2}/\d+[A-Z]?)\)',label,re.I);iid="sogei:"+(cm.group(1).upper() if cm else hashlib.sha256(full.encode()).hexdigest()[:24]);items[iid]={"id":iid,"title":label,"url":full}
    return list(items.values())

def parse_it_date(v):
    try:return datetime.strptime(v.strip(),"%d/%m/%Y").date()
    except:return None
def get_agid_table_items(url,nonexpired=False):
    page=fetch_html(url,45,2);today=datetime.now(ROME).date();items={}
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>',page,re.I|re.S):
        lm=re.search(r'<a[^>]+href=["\'](?P<href>[^"\']+/details/[^"\']+)["\'][^>]*>(?P<title>.*?)</a>',row,re.I|re.S)
        if not lm:continue
        full=absolute_url(url,lm.group("href")); dates=re.findall(r'\b\d{2}/\d{2}/\d{4}\b',strip_tags(row));deadline=dates[1] if len(dates)>1 else "";dd=parse_it_date(deadline)
        if nonexpired and (not dd or dd<today):continue
        iid="agid:"+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={"id":iid,"title":strip_tags(lm.group("title")),"url":full,"published":dates[0] if dates else "","deadline":deadline}
    return list(items.values())
def get_agid_positions():
    a=get_agid_table_items(AGID_ACTIVE_URL);print(f"AgID - Concorsi attivi: {len(a)}");b=get_agid_table_items(AGID_NOTICES_URL,True);print(f"AgID - Avvisi non scaduti: {len(b)}");return list({x["id"]:x for x in a+b}.values())

def get_invitalia_jobs():
    page=fetch_html(INVITALIA_JOBS_URL,45,2);start=page.lower().find("le ricerche in corso");end=page.lower().find("vedi le selezioni chiuse");sec=page[start:end if end>start else len(page)] if start>=0 else page;items={}
    for href,lhtml in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',sec,re.I|re.S):
        label=strip_tags(lhtml);full=absolute_url(INVITALIA_JOBS_URL,href);low=(label+full).lower()
        if label and "ingate.invitalia.it" not in full.lower() and "/lavora-con-noi/" in full.lower() and "selezioni-chiuse" not in low and "candidatura-spontanea" not in low and full.rstrip("/")!=INVITALIA_JOBS_URL.rstrip("/"):
            iid="invitalia-job:"+hashlib.sha256(full.encode()).hexdigest()[:24];items[iid]={"id":iid,"title":label,"url":full}
    return list(items.values())
def get_invitalia_consulting():
    page=fetch_html(INVITALIA_JOBS_URL,45,2);items={}
    for href,lhtml in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',page,re.I|re.S):
        full=absolute_url(INVITALIA_JOBS_URL,href);label=strip_tags(lhtml);low=label.lower()
        if "ingate.invitalia.it" in full.lower() and any(x in low for x in ("consulenza","esperti","specialisti","profession")) and not any(x in low for x in ("gara","fornitura","lavori","appalto")):
            oid=(urllib.parse.parse_qs(urllib.parse.urlparse(full).query).get("opportunityId") or [full])[0];iid="invitalia-consulting:"+str(oid);items[iid]={"id":iid,"title":label,"url":full}
    return list(items.values())
def get_invitalia_positions():
    jobs=get_invitalia_jobs();cons=get_invitalia_consulting();print(f"Invitalia - posizioni: {len(jobs)}");print(f"Invitalia - consulenze/esperti: {len(cons)}");out=[]
    for x in jobs: y=dict(x);y["extra"]="Posizione";out.append(y)
    for x in cons: y=dict(x);y["extra"]="Consulenza / Esperti / Specialisti";out.append(y)
    out=list({x["id"]:x for x in out}.values());print(f"Invitalia - opportunita uniche complessive: {len(out)}");return out

def get_cdp_positions():
    items={}
    for term in CDP_KEYWORDS:
        url=f"{CDP_JOBS_URL.rstrip('/')}/search/?"+urllib.parse.urlencode({"createNewAlert":"false","q":term,"locationsearch":""});page=fetch_html(url,45,2);found={}
        for m in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']*/job/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',page,re.I|re.S):
            full=absolute_url(url,m.group("href")).rstrip("/");label=strip_tags(m.group("label"));iid="cdp:"+hashlib.sha256(full.encode()).hexdigest()[:24]
            if label:found[iid]={"id":iid,"title":label,"url":full,"extra":"Comunicazione / Marketing"}
        print(f"CDP - ricerca '{term}': {len(found)}");items.update(found)
    print(f"CDP - posizioni uniche complessive: {len(items)}");return list(items.values())

def save_current(snapshot):
    CURRENT_FILE.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")

def main():
    if not TELEGRAM_BOT_TOKEN: print("ERRORE: TELEGRAM_BOT_TOKEN non configurato.");sys.exit(1)
    print("Pic_Job_Finder_Bot");print("Avvio controllo sorgenti...");memory=load_memory();errors=[];snapshot={"last_check":now_rome(),"sources":{}}
    specs=[
        ("leonardo",get_leonardo_jobs,lambda x: standard_job_message("Leonardo",x["title"],x["url"],published=x.get("posted"),extra=x.get("location"))),
        ("inpa",get_inpa_items,lambda x: standard_job_message("inPA",x["title"],x["url"],published=x.get("published"),deadline=x.get("deadline"),extra=x.get("extra"))),
        ("eutalia",get_eutalia_open_notices,lambda x: standard_job_message("Eutalia",x["title"],x["url"],extra="Avviso Aperto")),
        ("consip",get_consip_positions,lambda x: standard_job_message("Consip",x["title"],x["url"])),
        ("sogei",get_sogei_positions,lambda x: standard_job_message("Sogei",x["title"],x["url"])),
        ("agid",get_agid_positions,lambda x: standard_job_message("AgID",x["title"],x["url"],published=x.get("published"),deadline=x.get("deadline"))),
        ("invitalia",get_invitalia_positions,lambda x: standard_job_message("Invitalia",x["title"],x["url"],extra=x.get("extra"))),
        ("cdp",get_cdp_positions,lambda x: standard_job_message("CDP - Cassa Depositi e Prestiti",x["title"],x["url"],extra=x.get("extra"))),
    ]
    for source,getter,formatter in specs:
        print(f"\n=== {SOURCE_LABELS[source].upper()} ===")
        try:
            items=getter();print(f"Elementi correnti {SOURCE_LABELS[source]}: {len(items)}");process_items(memory,source,items,formatter)
            snapshot["sources"][source]={"label":SOURCE_LABELS[source],"status":"ok","items":[{"title":x.get("title","Titolo non disponibile"),"url":x.get("url","")} for x in items]}
        except urllib.error.HTTPError as exc:
          if source == "sogei" and exc.code == 403:
            print("Sogei: HTTP 403. Controllo non disponibile in questo run.")
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
            print(f"ERRORE monitor {SOURCE_LABELS[source]}: {exc}");errors.append(f"{SOURCE_LABELS[source]}: {exc}");snapshot["sources"][source]={"label":SOURCE_LABELS[source],"status":"error","items":[],"error":str(exc)}
    save_memory(memory);save_current(snapshot)
    print("\n=== RIEPILOGO ===")
    if errors:
        print("Controllo completato con errori:");[print(f"- {e}") for e in errors];sys.exit(1)
    print("Leonardo + inPA + Eutalia + Consip + Sogei + AgID + Invitalia + CDP controllati.");print("Controllo completato.")
if __name__=="__main__":main()
