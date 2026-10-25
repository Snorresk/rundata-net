#!/usr/bin/env python3
"""Read-only Commons import exclusions using the user's same-source/artist rule."""
import csv,hashlib,html,json,re,sqlite3,subprocess,sys,time,unicodedata
from collections import defaultdict,Counter
from pathlib import Path
from urllib.parse import urlencode,unquote,urlparse
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'audit/commons-20261025/commons-existing-source-review-20261025'
SOURCES=ROOT/'audit/commons-20261025/source-20260710'
DB=ROOT/'rundatanet/static/runes/runes.sqlite3'

def text(s):return ' '.join(html.unescape(re.sub('<[^>]*>',' ',s or '')).split())
def normalized(s):return re.sub(r'[^\w]+',' ',unicodedata.normalize('NFC',text(s)).casefold()).strip()
def person_key(s):
    s=text(s)
    if s.count(',')==1:
        last,first=s.split(',',1);s=first+' '+last
    key=normalized(s)
    return 'arild hauge' if key in {'www arild hauge com','arild hauge com'} else key

def title_key(s):return unicodedata.normalize('NFC',unquote(s)).replace('_',' ')
def agencies(s):
    s=text(s).casefold()
    result=set()
    if re.search(r'riksantikvarie|swedish national heritage|kulturmilj[oö]bild|\bkmb\b|(?:pub|kmb|arkivsok)\.raa\.se|\braä\b|bengt\s+a[. ]*\s*lundberg',s):result.add('RAÄ')
    if re.search(r'statens historiska|historiska museet|swedish history museum|samlingar\.shm\.se|\bshm\b',s):result.add('SHM')
    if re.search(r'sörmlands museum|s[oö]rmlandsmuseum|sokisamlingar.sormlandsmuseum',s):result.add('Sörmlands museum')
    # User's exclusion rule groups Runer KU with Danish National Museum sources.
    if re.search(r'nationalmuseet|national museum of denmark|danish national museum|(?:samlinger\.)?natmus\.dk|runer\.ku\.dk',s):result.add('Nationalmuseet i Danmark / Runer KU')
    return result

def write(name,rows,columns=None):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns or list(rows[0]));w.writeheader();w.writerows(rows)

def fetch(titles):
    params=dict(action='query',format='json',formatversion=2,prop='revisions|imageinfo',rvprop='content',rvslots='main',iiprop='url|sha1|extmetadata',iiextmetadatafilter='Artist|Credit|ImageDescription|ObjectName',redirects=1,maxlag=5,titles='|'.join(titles))
    url='https://commons.wikimedia.org/w/api.php?'+urlencode(params)
    p=OUT/'cache'/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    if p.exists():return json.loads(p.read_text())
    result=subprocess.run(['curl','-fsSL','--max-time','40','--user-agent','Rundata-net Commons source audit (https://rundata.info/)',url],capture_output=True)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-300:])
    data=json.loads(result.stdout)
    if data.get('error'):raise RuntimeError(str(data['error']))
    p.write_text(json.dumps(data,ensure_ascii=False));time.sleep(1.1)
    return data

def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'cache').mkdir(exist_ok=True)
    (OUT/'.gitignore').write_text('cache/\n')
    c=sqlite3.connect(f'file:{DB}?mode=ro',uri=True)
    c.row_factory=sqlite3.Row
    coverage=list(csv.DictReader((ROOT/'audit/commons-20261025/commons-coverage-20261024/alla-signum-90-100.csv').open(encoding='utf-8-sig')))
    scope={r['signum']:int(r['meta_id']) for r in coverage if int(r['current_image_links'])>0}
    sigs={r['signature_text']:(r['id'],r['parent_id']) for r in c.execute('select * from signatures')}
    byid={v[0]:(s,v[1]) for s,v in sigs.items()}
    original={}
    for path in sorted(SOURCES.glob('*_filtered.csv')):
        for r in csv.DictReader(path.open(encoding='utf-8-sig')):
            if int(r['confidence'])<90:continue
            sid=sigs[r['signature']][0]
            while byid[sid][1] is not None:sid=byid[sid][1]
            sig=byid[sid][0]
            if sig not in scope:continue
            k=(sig,title_key(r['file_title']))
            if k not in original or int(r['confidence'])>int(original[k]['confidence']):original[k]=r
    assert len(scope)==1254 and len(original)==2377
    current={};arch={};artists={};commons_existing={}
    for sig,mid in scope.items():
        rr=[dict(r) for r in c.execute('select * from runes_imagelink where meta_id=?',(mid,))]
        current[sig]=rr;arch[sig]=set();artists[sig]=defaultdict(list);commons_existing[sig]=set()
        for r in rr:
            arch[sig].update(agencies(r['link_url']+' '+r['info']))
            if urlparse(r['link_url']).hostname=='commons.wikimedia.org':commons_existing[sig].add(title_key(unquote(urlparse(r['link_url']).path.removeprefix('/wiki/'))))
            for name in re.findall(r'(?:artist:|photo(?:grapher)?:|foto:)\s*([^;©]+)',r['info'],re.I):
                if person_key(name):artists[sig][person_key(name)].append(r['link_url'])
    # Structured photographer metadata already saved during the SHM audit.
    for file in (ROOT/'audit/shm-20261021/pages').glob('*.txt'):
        page=file.read_text()
        m=re.search(r'<th>Fotograf</th>\s*<td>(.*?)</td>',page,re.S)
        media=re.search(r'property="og:url" content="https://samlingar.shm.se/media/([a-fA-F0-9-]+)',page)
        if not m or not media:continue
        name=person_key(m[1]);iid=media[1].casefold()
        for sig,rr in current.items():
            for row in rr:
                if iid in row['direct_url'].casefold():artists[sig][name].append(row['link_url'])
    wanted=sorted({k[1] for k in original})
    pages={};aliases={}
    for start in range(0,len(wanted),20):
        data=fetch(wanted[start:start+20]);q=data.get('query',{})
        for part in ('normalized','redirects'):
            for a in q.get(part,[]):aliases[title_key(a['from'])]=title_key(a['to'])
        for page in q.get('pages',[]):pages[title_key(page.get('title',''))]=page
        print(f'Commons metadata: {min(start+20,len(wanted))}/{len(wanted)}',flush=True)
    # Enrich photographers from existing Commons links covered by this audit.
    for sig,titles in commons_existing.items():
        for title in titles:
            resolved=title;seen=set()
            while resolved in aliases and resolved not in seen:seen.add(resolved);resolved=aliases[resolved]
            info=(pages.get(resolved,{}).get('imageinfo') or [{}])[0]
            artist=text(((info.get('extmetadata') or {}).get('Artist') or {}).get('value',''))
            if artist:
                artists[sig][person_key(artist)].extend(r['link_url'] for r in current[sig] if 'commons.wikimedia.org' in r['link_url'])
    results=[]
    for (sig,title),row in sorted(original.items()):
        resolved=title;seen=set()
        while resolved in aliases and resolved not in seen:seen.add(resolved);resolved=aliases[resolved]
        page=pages.get(resolved,{})
        info=(page.get('imageinfo') or [{}])[0];meta=info.get('extmetadata') or {}
        wiki=(((page.get('revisions') or [{}])[0].get('slots') or {}).get('main') or {}).get('content','')
        fresh_artist=text((meta.get('Artist') or {}).get('value',''))
        blob=' '.join([wiki,row['file_title'],row['artist'],row.get('credit',''),json.dumps(meta,ensure_ascii=False)])
        ca=agencies(blob);shared=ca & arch[sig]
        na=person_key(fresh_artist or row['artist']);matched=artists[sig].get(na,[]) if na else []
        already=title in commons_existing[sig] or resolved in commons_existing[sig]
        status='exclude_already_in_db' if already else ('exclude_same_archive' if shared else ('exclude_same_photographer' if matched else 'retain_candidate'))
        if not page or page.get('missing') or not info.get('url'):status='review_unavailable_file'
        result=dict(signum=sig,meta_id=scope[sig],confidence=row['confidence'],commons_file_page=row['commons_file_page'],file_title=row['file_title'],decision=status,matching_archives=' | '.join(sorted(shared)),commons_archives=' | '.join(sorted(ca)),existing_archives=' | '.join(sorted(arch[sig])),photographer=fresh_artist or text(row['artist']),matching_existing_links=' | '.join(matched),existing_image_count=len(current[sig]),credit=text((meta.get('Credit') or {}).get('value','')) or row.get('credit',''),source_wikitext=wiki)
        if shared:
            result['matching_existing_links']=' | '.join(r['link_url'] for r in current[sig] if agencies(r['link_url']+' '+r['info']) & shared)
        results.append(result)
    write('all-candidates.csv',results)
    excluded=[r for r in results if r['decision'].startswith('exclude')];retained=[r for r in results if r['decision']=='retain_candidate'];review=[r for r in results if r['decision'].startswith('review')]
    for name,rows in [('excluded.csv',excluded),('retained-candidates.csv',retained),('needs-review.csv',review)]:write(name,rows,list(results[0]))
    summary=dict(scoped_signa=len(scope),candidate_pairs=len(results),unique_commons_files=len(wanted),excluded=len(excluded),retained=len(retained),needs_review=len(review),decisions=dict(Counter(r['decision'] for r in results)),archive_exclusions=dict(Counter(a for r in excluded for a in r['matching_archives'].split(' | ') if a)))
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
