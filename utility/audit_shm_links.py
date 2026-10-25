#!/usr/bin/env python3
"""Cache SHM evidence and audit links; never change the database."""
import csv
import hashlib
import html
import json
import re
import sqlite3
import subprocess
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'audit/shm-20261021'
CACHE = OUT / 'pages'
CACHE.mkdir(parents=True, exist_ok=True)

def fetch(url):
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest() + '.txt')
    if path.exists():
        return path.read_text()
    for attempt in range(3):
        result = subprocess.run(['curl', '-fsSL', '--max-time', '25', '--user-agent', 'Rundata-net metadata audit', url], capture_output=True)
        if result.returncode == 0:
            text = result.stdout.decode('utf-8', errors='replace')
            path.write_text(text)
            time.sleep(.5)
            return text
        time.sleep(30 if b'429' in result.stderr else 2 + attempt * 3)
    raise RuntimeError(result.stderr.decode(errors='replace')[-250:])

def plain(text):
    text = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', text, flags=re.S | re.I)
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', text))).strip()

def norm(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', html.unescape(text))).strip().casefold()

def fields(page):
    data = {}
    for name, value in re.findall(r'<th\b[^>]*>(.*?)</th>\s*<td\b[^>]*>(.*?)</td>', page, re.S | re.I):
        data[plain(name)] = plain(value)
    return data

def signa(page):
    value = fields(page).get('Andra nummer', '')
    return [v.strip() for v in re.findall(r'Runsignum:\s*(.*?)(?=\s+[A-Za-zÅÄÖåäö][A-Za-zÅÄÖåäö -]*:|$)', value)]

def title(page):
    m = re.search(r'<meta property="og:title" content="([^"]*)"', page)
    return html.unescape(m[1]) if m else ''

def objects(page):
    return sorted(set(html.unescape(u) for u in re.findall(r'href="(https://samlingar\.shm\.se/object/[A-Fa-f0-9-]+)"', page)))

def write(name, rows):
    path = OUT / name
    if rows:
        with path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

def connection():
    return sqlite3.connect(f'file:{ROOT}/rundatanet/static/runes/runes.sqlite3?mode=ro', uri=True)

def catalog(conn):
    entries = {i:(s,p) for i,s,p in conn.execute('select id,signature_text,parent_id from signatures')}
    def root(i):
        seen=set()
        while entries[i][1] is not None:
            if i in seen: raise ValueError('Alias cycle')
            seen.add(i);i=entries[i][1]
        return i
    aliases={}
    for i,(s,p) in entries.items(): aliases.setdefault(root(i),set()).add(s)
    return entries,aliases

def audit():
    conn=connection(); entries, aliases=catalog(conn)
    rows=conn.execute("select i.id,i.meta_id,s.id,s.signature_text,i.link_url,i.direct_url from runes_imagelink i join meta_information m on m.id=i.meta_id join signatures s on s.id=m.signature_id where i.link_url like 'https://samlingar.shm.se/%' or i.link_url like 'http://samlingar.shm.se/%'").fetchall()
    results=[]
    for index,(iid,mid,sid,sig,url,direct) in enumerate(rows,1):
        row=dict(image_id=iid,meta_id=mid,signature=sig,link_url=url,direct_url=direct,status='',object_urls='',shm_signa='',titles='',evidence='',error='')
        try:
            page=fetch(url); urls=objects(page) if '/media/' in url else [url]
            evidence=[];matched=[]
            for obj in urls:
                op=fetch(obj);ss=signa(op); tt=title(op)
                known=aliases.get(sid,{sig})
                hits=[a for a in known if norm(a) in {norm(x) for x in ss}]
                # An explicit title can establish identity when a structured signum is historical.
                title_hits=[a for a in known if norm(a)==norm(tt)]
                evidence.append(dict(url=obj,signa=ss,title=tt,hits=hits,title_hits=title_hits,fields=fields(op)))
                if hits:matched.append('exact_signum' if sig in hits else 'alias_signum')
                elif title_hits:matched.append('exact_title_review')
            row.update(object_urls=' | '.join(urls),shm_signa=' | '.join(x for e in evidence for x in e['signa']),titles=' | '.join(e['title'] for e in evidence),evidence=json.dumps(evidence,ensure_ascii=False))
            row['status']=('verified_'+matched[0]) if any(x in {'exact_signum','alias_signum'} for x in matched) else ('review_title_match' if matched else ('review_different_signum' if any(e['signa'] for e in evidence) else 'review_missing_signum'))
        except Exception as e:row.update(status='fetch_error',error=str(e))
        results.append(row)
        if index%25==0 or index==len(rows):
            write('existing-links.csv',results); print('audit',index,'/',len(rows),flush=True)
    write('existing-links.csv',results)
    from collections import Counter
    print(dict(Counter(r['status'] for r in results)),flush=True)

def discover():
    conn=connection(); entries,aliases=catalog(conn)
    owners={}
    for sid,aa in aliases.items():
        for a in aa:owners.setdefault(norm(a),set()).add(sid)
    metas=dict(conn.execute('select signature_id,id from meta_information'))
    existing={(m,u.lower()) for m,u in conn.execute('select meta_id,link_url from runes_imagelink')}
    existing_media={}
    for m,u in conn.execute("select meta_id,link_url from runes_imagelink where link_url like '%samlingar.shm.se/media/%'"):
        existing_media.setdefault(m,set()).add(u.rsplit('/',1)[-1].lower())
    candidates={}; searches=[]
    for query in ['runsten','runristning','runbleck','runinskrift','runben','runor','runhäll','runfragment','brakteat runinskrift','brakteat runor']:
        offset=0
        while True:
            data=json.loads(fetch('https://samlingar.shm.se/api/v1/search?'+urlencode(dict(type='object',query=query,rows=100,offset=offset), quote_via=quote)))
            items=data.get('items',[]); total=data.get('totalResults',0)
            searches.append(dict(query=query,offset=offset,total=total,returned=len(items)))
            for item in items:
                if item.get('type')=='object':candidates[item['id']]=item
            print('search',query,offset,total,flush=True)
            offset+=len(items)
            if not items or offset>=total:break
    write('searches.csv',searches)
    results=[]
    for index,item in enumerate(candidates.values(),1):
        url=item['url'].split('?')[0]
        try:
            page=fetch(url); ss=signa(page)
            owner_ids=set()
            for s in ss:owner_ids.update(owners.get(norm(s),set()))
            media_ids=set(re.findall(r'https://samlingar\.shm\.se/media/([A-Fa-f0-9-]+)',page))
            media_ids={x.lower() for x in media_ids}
            for sid in sorted(owner_ids):
                if sid not in metas:continue
                mid=metas[sid]; image=item.get('image') or {}; thumb=((image.get('sizes') or {}).get('thumbnail') or {}).get('url','')
                iid=(image.get('itemUrl') or '').rsplit('/',1)[-1].lower()
                represented=bool((media_ids | {iid}) & existing_media.get(mid,set()))
                status='existing_object' if (mid,url.lower()) in existing else ('existing_media' if represented else ('proposed_exact' if thumb else 'no_image'))
                results.append(dict(signature=entries[sid][0],meta_id=mid,status=status,object_url=url,direct_url=thumb,shm_signa=' | '.join(ss),title=title(page),evidence=json.dumps(fields(page),ensure_ascii=False)))
        except Exception as e:results.append(dict(signature='',meta_id='',status='fetch_error',object_url=url,direct_url='',shm_signa='',title='',evidence=str(e)))
        if index%50==0 or index==len(candidates):
            write('discovery.csv',results);print('discovery',index,'/',len(candidates),flush=True)
    write('discovery.csv',results)
    from collections import Counter
    print(dict(Counter(r['status'] for r in results)),flush=True)

if __name__=='__main__':
    import sys
    if 'discover' in sys.argv:discover()
    else:audit()
