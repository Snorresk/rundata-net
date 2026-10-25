#!/usr/bin/env python3
"""Import >90-score Commons images only for the reviewed 62 image-less signa."""
import csv
import hashlib
import html
import json
import re
import sqlite3
import subprocess
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT=Path(__file__).resolve().parents[3]
DB=ROOT/'rundatanet/static/runes/runes.sqlite3'
OUT=ROOT/'audit/commons-20261025/commons-import-20261025'
SOURCE=ROOT/'audit/commons-20261025/source-20260710'
TARGETS=ROOT/'audit/commons-20261025/commons-coverage-20261024/signum-utan-bildlankar.csv'
BACKUP=ROOT/'audit/commons-20261025/commons-import-20261025/runes-before-commons-import.sqlite3'


def write(name,rows,columns=None):
    with (OUT/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns or list(rows[0]));w.writeheader();w.writerows(rows)


def image_data(data):
    if data.startswith((b'\xff\xd8\xff',b'\x89PNG\r\n\x1a\n',b'GIF87a',b'GIF89a',b'II*\x00',b'MM\x00*')) or (data[:4]==b'RIFF' and data[8:12]==b'WEBP'):
        return True
    try:
        return ET.fromstring(data).tag.rsplit('}',1)[-1]=='svg'
    except (ET.ParseError, ValueError):
        return False


def prepare(archive_only=False):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'.gitignore').write_text('images/\n*.sqlite3\n')
    (OUT/'images').mkdir(exist_ok=True)
    c=sqlite3.connect(f'file:{DB}?mode=ro',uri=True)
    targets=list(csv.DictReader(TARGETS.open(encoding='utf-8-sig')))
    assert len(targets)==62
    signatures={i:(s,p) for i,s,p in c.execute('select id,signature_text,parent_id from signatures')}
    lookup={s:i for i,(s,p) in signatures.items()}
    metas=dict(c.execute('select signature_id,id from meta_information'))
    scope={r['signum']:int(r['meta_id']) for r in targets}
    for sig,mid in scope.items():
        assert metas[lookup[sig]]==mid
        assert c.execute('select count(*) from runes_imagelink where meta_id=?',(mid,)).fetchone()[0]==0,sig
    if not BACKUP.exists():
        with sqlite3.connect(BACKUP) as dst:c.backup(dst)
    write('targets-before.csv',targets)
    unique={}
    for source in sorted(SOURCE.glob('*_filtered.csv')):
        for row in csv.DictReader(source.open(encoding='utf-8-sig')):
            if int(row['confidence'])<=90:continue
            sid=lookup[row['signature']]
            visited=set()
            while signatures[sid][1] is not None:
                assert sid not in visited;visited.add(sid);sid=signatures[sid][1]
            sig=signatures[sid][0]
            if sig not in scope:continue
            url=row['commons_file_page'];direct=row['direct_image_url'];thumb=row['thumbnail_url'] or direct
            assert urlparse(url).hostname=='commons.wikimedia.org' and urlparse(url).path.startswith('/wiki/File:')
            assert all(urlparse(u).scheme=='https' and urlparse(u).hostname=='upload.wikimedia.org' for u in (direct,thumb))
            assert row['mime'].startswith('image/')
            key=(sig,unicodedata.normalize('NFC',unquote(url)))
            if key not in unique or int(row['confidence'])>int(unique[key]['confidence']):
                unique[key]=dict(row,signum=sig,current_meta_id=scope[sig],source_file=source.name,thumbnail_to_import=thumb)
    assert {r['signum'] for r in unique.values()}==set(scope)
    accepted=[];errors=[]
    for index,row in enumerate(unique.values(),1):
        url=row['thumbnail_to_import'];path=OUT/'images'/hashlib.sha256(url.encode()).hexdigest()
        if not path.exists() and not archive_only:
            for attempt in range(3):
                result=subprocess.run(['curl','-fsSL','--max-time','30','--user-agent','Rundata-net Commons link verification/1.0',url],capture_output=True)
                time.sleep(1)
                if result.returncode==0:
                    path.write_bytes(result.stdout);break
                if b'Could not resolve host' in result.stderr:raise RuntimeError(result.stderr.decode(errors='replace'))
                if b'429' in result.stderr:
                    raise RuntimeError('Commons rate limited the request. Stop network checks and respect Retry-After; --archive-only uses the approved saved metadata without more requests.')
                time.sleep(3)
        if path.exists() and image_data(path.read_bytes()):
            row['verification_status']='live_image_verified'
            accepted.append(row)
        elif not path.exists() and archive_only:
            row['verification_status']='archived_metadata_only_rate_limited'
            accepted.append(row)
        else:errors.append(dict(signum=row['signum'],commons_file_page=row['commons_file_page'],thumbnail=url,reason='Could not fetch valid image data'))
        if index%10==0 or index==len(unique):print(f'Candidates prepared: {index}/{len(unique)}; accepted={len(accepted)}',flush=True)
    write('proposed.csv',accepted)
    write('errors.csv',errors,['signum','commons_file_page','thumbnail','reason'])
    print(json.dumps(dict(accepted=len(accepted),covered_signa=len({r['signum'] for r in accepted}),errors=len(errors),scores=dict(Counter(r['confidence'] for r in accepted))),ensure_ascii=False),flush=True)


def clean(text):
    return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]*>',' ',text))).strip()


def apply():
    rows=list(csv.DictReader((OUT/'proposed.csv').open()))
    targets=list(csv.DictReader((OUT/'targets-before.csv').open()))
    scope={int(r['meta_id']):r['signum'] for r in targets}
    assert len(scope)==62 and {r['signum'] for r in rows}==set(scope.values())
    conn=sqlite3.connect(DB);conn.row_factory=sqlite3.Row
    before={r['id']:dict(r) for r in conn.execute('select * from runes_imagelink')}
    inserted=[];seen=set()
    with conn:
        for mid,sig in scope.items():
            assert conn.execute('select count(*) from runes_imagelink where meta_id=?',(mid,)).fetchone()[0]==0,sig
            assert conn.execute('select s.signature_text from meta_information m join signatures s on s.id=m.signature_id where m.id=?',(mid,)).fetchone()[0]==sig
        for row in rows:
            mid=int(row['current_meta_id']);assert mid in scope and scope[mid]==row['signum']
            assert int(row['confidence'])>90
            key=(mid,unicodedata.normalize('NFC',unquote(row['commons_file_page'])))
            assert key not in seen;seen.add(key)
            if row['verification_status']=='live_image_verified':
                data=(OUT/'images'/hashlib.sha256(row['thumbnail_to_import'].encode()).hexdigest()).read_bytes()
                assert image_data(data)
            else:
                assert row['verification_status']=='archived_metadata_only_rate_limited'
            info='Wikimedia Commons'
            for label,value in [('artist',row['artist']),('license',row['license_short_name'])]:
                if value:info+=f'; {label}: {clean(value)}'
            info=info[:1500]
            cur=conn.execute('insert into runes_imagelink (meta_id,link_url,direct_url,info,original_info) values (?,?,?,?,?)',(mid,row['commons_file_page'],row['thumbnail_to_import'],info,info))
            inserted.append(dict(image_id=cur.lastrowid,**row))
        after={r['id']:dict(r) for r in conn.execute('select * from runes_imagelink')}
        assert all(after[i]==r for i,r in before.items())
        assert set(after)-set(before)=={r['image_id'] for r in inserted}
        assert conn.execute('pragma integrity_check').fetchone()[0]=='ok'
    write('inserted.csv',inserted)
    counts=Counter(int(r['current_meta_id']) for r in inserted)
    write('per-signum.csv',[dict(signum=sig,meta_id=mid,before=0,added=counts[mid],after=conn.execute('select count(*) from runes_imagelink where meta_id=?',(mid,)).fetchone()[0],highest_score=max(int(r['confidence']) for r in inserted if int(r['current_meta_id'])==mid)) for mid,sig in sorted(scope.items(),key=lambda item:item[1])])
    summary=dict(inserted=len(inserted),signa=len({r['signum'] for r in inserted}),minimum_score=min(int(r['confidence']) for r in inserted),live_images_verified=sum(r['verification_status']=='live_image_verified' for r in inserted),archived_metadata_only=sum(r['verification_status']!='live_image_verified' for r in inserted),all_existing_image_rows_unchanged=True,integrity_check='ok')
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    apply() if '--apply' in sys.argv else prepare(archive_only='--archive-only' in sys.argv)
