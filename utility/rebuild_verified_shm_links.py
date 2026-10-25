#!/usr/bin/env python3
"""Prepare a fully evidenced SHM reset, verify images, then apply atomically."""
import csv
import hashlib
import html
import json
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlparse
from audit_shm_links import ROOT, OUT, CACHE, catalog, connection, fetch, fields, norm, plain, signa, title, write

IMAGE_CACHE = OUT / 'images'
IMAGE_CACHE.mkdir(exist_ok=True)


def host_is_shm(url):
    host = urlparse(url).hostname or ''
    return host == 'shm.se' or host.endswith('.shm.se')


def matching_owners(page, owners):
    ss = signa(page)
    if 'testpost' in norm(title(page)) or 'testpost' in norm(fields(page).get('Föremålsnummer', '')):
        return set(), 'test_record'
    ids = set()
    basis = 'structured_signum'
    for sig in ss:
        found = owners.get(norm(sig), set())
        if len(found) == 1:
            ids.update(found)
    title_owners = owners.get(norm(title(page)), set())
    if ss and title_owners and title_owners != ids:
        return set(), 'conflicting_title_and_signum'
    # Exact titles are accepted only when there is no conflicting structured signum.
    if not ss:
        found = owners.get(norm(title(page)), set())
        if len(found) == 1:
            ids.update(found)
            basis = 'exact_title'
    return ids, basis


def image_ok(url):
    path = IMAGE_CACHE / hashlib.sha256(url.encode()).hexdigest()
    if not path.exists():
        for attempt in range(3):
            result = subprocess.run(['curl','-fsSL','--max-time','25','--user-agent','Rundata-net metadata audit',url],capture_output=True)
            if result.returncode == 0:
                path.write_bytes(result.stdout)
                time.sleep(.5)
                break
            time.sleep(30 if b'429' in result.stderr else 3)
        else:
            return False, result.stderr.decode(errors='replace')[-200:]
    data = path.read_bytes()
    valid = data.startswith((b'\xff\xd8\xff',b'\x89PNG\r\n\x1a\n',b'GIF87a',b'GIF89a')) or (data[:4] == b'RIFF' and data[8:12] == b'WEBP')
    return valid, '' if valid else 'Response is not a recognized image'


def prepare():
    conn=connection(); entries,aliases=catalog(conn)
    owners={}
    for sid,aa in aliases.items():
        for a in aa:owners.setdefault(norm(a),set()).add(sid)
    metas=dict(conn.execute('select signature_id,id from meta_information'))
    old_pairs=set()
    old=list(csv.DictReader((OUT/'before-reset-all-shm-links.csv').open()))
    for row in old:old_pairs.add((int(row['meta_id']),row['link_url'].lower()))
    verified_old_objects=set()
    for row in csv.DictReader((OUT/'existing-links.csv').open()):
        if row['status'].startswith('verified_') or row['status']=='review_title_match':
            for url in row['object_urls'].split(' | '):verified_old_objects.add((int(row['meta_id']),url.lower()))
    candidates=[];excluded=[];seen=set()
    for path in sorted(CACHE.glob('*.txt')):
        page=path.read_text()
        match=re.search(r'<meta property="og:url" content="(https://samlingar\.shm\.se/object/[A-Fa-f0-9-]+)"',page)
        if not match:continue
        url=match[1]
        if url.lower() in seen:continue
        seen.add(url.lower())
        ids,basis=matching_owners(page,owners)
        if not ids:
            excluded.append(dict(object_url=url,title=title(page),shm_signa=' | '.join(signa(page)),reason='No unambiguous exact signum or title in the local signature catalog'))
            continue
        image=re.search(r'<meta property="og:image" content="([^"]+)"',page)
        direct=html.unescape(image[1]) if image else ''
        if not re.fullmatch(r'https://media\.samlingar\.shm\.se/item/[a-fA-F0-9-]+/(?:large|medium|small|thumbnail)',direct):
            excluded.append(dict(object_url=url,title=title(page),shm_signa=' | '.join(signa(page)),reason='No supported SHM image attached to the object'))
            continue
        direct=direct.rsplit('/',1)[0]+'/thumbnail'
        ok,error=image_ok(direct)
        for sid in sorted(ids):
            if sid not in metas:continue
            mid=metas[sid]
            candidates.append(dict(signature=entries[sid][0],meta_id=mid,link_url=url,direct_url=direct,shm_signa=' | '.join(signa(page)),title=title(page),verification=basis,image_verified=ok,error=error,previously_linked=(mid,url.lower()) in verified_old_objects or (mid,url.lower()) in old_pairs,evidence=json.dumps(fields(page),ensure_ascii=False)))
        if len(candidates)%25==0:print('prepared',len(candidates),flush=True)
    write('rebuild-proposed.csv',candidates);write('rebuild-excluded.csv',excluded)
    mixed=[]
    for row in old:
        if host_is_shm(row['link_url']) or not host_is_shm(row['direct_url']):continue
        match=re.fullmatch(r'https://pub\.raa\.se/visa/dokumentation/([a-fA-F0-9-]+)',row['link_url'])
        if not match:raise RuntimeError('Unexpected mixed source')
        document=json.loads(fetch('https://pub.raa.se/dokumentation/'+match[1]))
        thumbnails=[g.get('presentationThumbnailUrl') for g in document.get('resourceGroups',[]) if g.get('presentationThumbnailUrl')]
        thumbnail=thumbnails[0] if thumbnails else ''
        if thumbnail and urlparse(thumbnail).hostname!='pub.raa.se':raise RuntimeError('Unexpected RAÄ thumbnail host')
        if thumbnail:
            ok,error=image_ok(thumbnail)
            if not ok:raise RuntimeError('RAÄ thumbnail verification failed: '+error)
        mixed.append(dict(image_id=row['id'],signature=row['signature'],link_url=row['link_url'],old_direct_url=row['direct_url'],new_direct_url=thumbnail,action='replace_thumbnail' if thumbnail else 'remove_unavailable_image',reason='RAÄ metadata supplies its own image' if thumbnail else 'RAÄ publishes no image resource; old thumbnail pointed to SHM'))
    write('mixed-raa-thumbnail-corrections.csv',mixed)
    print('Prepared',len(candidates),'image_verified',sum(x['image_verified'] for x in candidates),'new object/signum pairs',sum(not x['previously_linked'] for x in candidates),flush=True)


def apply():
    rows=list(csv.DictReader((OUT/'rebuild-proposed.csv').open()))
    accepted=[r for r in rows if r['image_verified']=='True']
    if not accepted:raise RuntimeError('No verified replacements')
    conn=sqlite3.connect(ROOT/'rundatanet/static/runes/runes.sqlite3')
    conn.row_factory=sqlite3.Row
    old=list(csv.DictReader((OUT/'before-reset-all-shm-links.csv').open()))
    before=list(conn.execute('select * from runes_imagelink'))
    targets=[r for r in before if host_is_shm(r['link_url'])]
    # Mixed RAÄ sources are kept and their SHM thumbnail is handled separately.
    old_ids={int(r['id']) for r in old if host_is_shm(r['link_url'])}
    assert {r['id'] for r in targets}==old_ids, 'SHM rows changed since the backup'
    backup=ROOT/'SHM/backups/runes-before-shm-reset-20261021.sqlite3'
    assert backup.exists()
    inserted=[]
    mixed=list(csv.DictReader((OUT/'mixed-raa-thumbnail-corrections.csv').open()))
    with conn:
        for r in targets:
            original=next(x for x in old if int(x['id'])==r['id'])
            assert all(str(r[k])==original[k] for k in r.keys())
            conn.execute('delete from runes_imagelink where id=?',(r['id'],))
        for row in accepted:
            caption='Image from SHM collections'
            cursor=conn.execute('insert into runes_imagelink (meta_id,link_url,direct_url,info,original_info) values (?,?,?,?,?)',(int(row['meta_id']),row['link_url'],row['direct_url'],caption,caption))
            inserted.append(dict(image_id=cursor.lastrowid,**row))
        for row in mixed:
            current=conn.execute('select * from runes_imagelink where id=?',(int(row['image_id']),)).fetchone()
            assert current['link_url']==row['link_url'] and current['direct_url']==row['old_direct_url']
            if row['action']=='replace_thumbnail':
                conn.execute('update runes_imagelink set direct_url=? where id=?',(row['new_direct_url'],int(row['image_id'])))
            else:
                conn.execute('delete from runes_imagelink where id=?',(int(row['image_id']),))
        changed_ids=old_ids | {int(r['image_id']) for r in mixed}
        others_before={r['id']:tuple(r) for r in before if r['id'] not in changed_ids}
        others_after={r['id']:tuple(r) for r in conn.execute('select * from runes_imagelink') if r['id'] in others_before}
        assert others_before==others_after
        assert conn.execute('pragma integrity_check').fetchone()[0]=='ok'
    write('rebuild-inserted.csv',inserted)
    write('rebuild-removed.csv',[dict(r) for r in targets])
    summary=dict(mixed_raa_thumbnails_corrected=sum(r['action']=='replace_thumbnail' for r in mixed),mixed_unavailable_image_removed=sum(r['action']=='remove_unavailable_image' for r in mixed),removed=len(targets),inserted=len(inserted),inscriptions=len({r['meta_id'] for r in inserted}),unique_objects=len({r['link_url'].lower() for r in inserted}),new_object_signature_pairs=sum(r['previously_linked']=='False' for r in inserted),image_failures=len(rows)-len(accepted),integrity_check='ok',other_image_rows_unchanged=True)
    (OUT/'reset-summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    if '--apply' in sys.argv:apply()
    else:prepare()
