import json, os, urllib.parse, urllib.request
from pathlib import Path
TOKEN=os.environ.get('TELEGRAM_BOT_TOKEN'); AUTH={'2020881944'}; CURRENT=Path('current_jobs.json'); STATE=Path('bot_state.json'); MAX=4096

def api(method,data=None):
    url=f'https://api.telegram.org/bot{TOKEN}/{method}'; body=urllib.parse.urlencode(data or {}).encode() if data else None
    with urllib.request.urlopen(urllib.request.Request(url,data=body,method='POST' if body else 'GET'),timeout=30) as r:return json.loads(r.read().decode())
def send(chat,text): api('sendMessage',{'chat_id':chat,'text':text[:MAX],'disable_web_page_preview':'true'})
def load_current():
    try:return json.loads(CURRENT.read_text(encoding='utf-8'))
    except:return {'last_check':'Non disponibile','sources':{}}
def status(data):
    lines=['🤖 PIC JOB FINDER - STATO','',f"🕐 Ultimo controllo: {data.get('last_check','Non disponibile')}",''];total=0
    for key in ['leonardo','inpa','eutalia','consip','sogei','agid','invitalia','cdp']:
        s=data.get('sources',{}).get(key,{'label':key,'status':'unavailable','items':[]}); n=len(s.get('items',[]));total+=n
        icon='✅' if s.get('status')=='ok' else '⚠️'; lines.append(f"{icon} {s.get('label',key)} — {n if s.get('status')=='ok' else 'non disponibile'}")
    lines+=['',f'📊 Totale annunci: {total}'];return '\n'.join(lines)
def summary(data):
    lines=['📋 PIC JOB FINDER - RIEPILOGO','',f"🕐 Ultimo controllo: {data.get('last_check','Non disponibile')}",''];total=0
    for key in ['leonardo','inpa','eutalia','consip','sogei','agid','invitalia','cdp']:
        s=data.get('sources',{}).get(key,{'label':key,'status':'unavailable','items':[]});items=s.get('items',[]);label=s.get('label',key)
        if s.get('status')!='ok': lines += [f'⚠️ {label} — controllo non disponibile',''];continue
        total+=len(items);lines.append(f'{label.upper()} — {len(items)} annunci')
        for x in items: lines += [f"• {x.get('title','Titolo non disponibile')}", f"  {x.get('url','')}"]
        lines.append('')
    lines += [f'📊 Totale: {total} annunci','','🤖 Pic_Job_Finder_Bot'];text='\n'.join(lines)
    if len(text)>MAX:
        footer='\n\n⚠️ Riepilogo abbreviato per limite Telegram.\n🤖 Pic_Job_Finder_Bot';text=text[:MAX-len(footer)]+footer
    return text
HELP='''🤖 PIC JOB FINDER\n\nComandi disponibili:\n\n/riepilogo\nMostra gli annunci dell’ultimo controllo.\n\n/status\nMostra stato e conteggi delle fonti.\n\n/help\nMostra questo messaggio.'''
def main():
    if not TOKEN: raise SystemExit('TELEGRAM_BOT_TOKEN non configurato')
    state={'last_update_id':0}
    if STATE.exists():
        try:state=json.loads(STATE.read_text())
        except:pass
    res=api('getUpdates',{'offset':state.get('last_update_id',0)+1,'timeout':0,'allowed_updates':json.dumps(['message'])})
    last=state.get('last_update_id',0);data=load_current()
    for upd in res.get('result',[]):
        last=max(last,upd.get('update_id',0));msg=upd.get('message') or {};chat=str((msg.get('chat') or {}).get('id',''));text=(msg.get('text') or '').split('@',1)[0].strip().lower()
        if chat not in AUTH:continue
        if text=='/help':send(chat,HELP)
        elif text=='/status':send(chat,status(data))
        elif text=='/riepilogo':send(chat,summary(data))
    STATE.write_text(json.dumps({'last_update_id':last},indent=2))
if __name__=='__main__':main()
