#!/usr/bin/env python3
"""Supplement only existing SHM-linked signa from their approved object galleries."""
import csv
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from audit_shm_links import catalog, fields, norm, signa, title
from rebuild_verified_shm_links import matching_owners

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'audit/shm-supplement-20261024'
DB = ROOT / 'rundatanet/static/runes/runes.sqlite3'
BACKUP = ROOT / 'SHM/backups/runes-before-shm-supplement-20261024.sqlite3'
LIMIT = 15
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def image_id(url):
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or parsed.hostname != 'media.samlingar.shm.se':
        return ''
    m = re.fullmatch(rf'/item/({UUID})(?:/(?:thumbnail|small|medium|large))?/?', parsed.path, re.I)
    return m[1].lower() if m else ''


def gallery_images(page):
    """Preserve gallery order, excluding links without a matching image resource."""
    from html import unescape
    urls = [unescape(u) for u in re.findall(r'(?:href|src|content|data-url)=["\']([^"\']+)["\']', page)]
    images = {image_id(u) for u in urls if image_id(u)}
    media = []
    for url in urls:
        parsed = urlparse(url)
        match = re.fullmatch(rf'/media/({UUID})/?', parsed.path, re.I)
        if parsed.scheme in {'http', 'https'} and parsed.hostname == 'samlingar.shm.se' and match:
            iid = match[1].lower()
            if iid in images and iid not in media:
                media.append(iid)
    return media


def write(name, rows, columns=None):
    with (OUT / name).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fetch(url, kind):
    folder = OUT / kind
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / hashlib.sha256(url.encode()).hexdigest()
    if path.exists():
        return path.read_bytes()
    for attempt in range(3):
        result = subprocess.run(['curl', '-fsSL', '--max-time', '25', '--user-agent',
                                 'Rundata-net SHM gallery audit', url], capture_output=True)
        time.sleep(1.05)
        if result.returncode == 0:
            path.write_bytes(result.stdout)
            return result.stdout
        if b'Could not resolve host' in result.stderr:
            raise RuntimeError(result.stderr.decode(errors='replace'))
        time.sleep(30 if b'429' in result.stderr else 3)
    raise RuntimeError(result.stderr.decode(errors='replace')[-250:])


def is_image(data):
    return data.startswith((b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n', b'GIF87a', b'GIF89a')) or (
        data[:4] == b'RIFF' and data[8:12] == b'WEBP')


def select_new_images(existing, galleries, maximum=LIMIT):
    """Count all existing rows toward the cap and never add a duplicate photo."""
    counts = Counter(int(r['meta_id']) for r in existing)
    seen = {(int(r['meta_id']), image_id(r['direct_url'])) for r in existing}
    for row in galleries:
        mid = int(row['meta_id'])
        if counts[mid] >= maximum or (mid, row['media_id']) in seen:
            continue
        yield row
        # Callers acknowledge only verified images by adding to the shared row list.
        counts = Counter(int(r['meta_id']) for r in existing)
        seen = {(int(r['meta_id']), image_id(r['direct_url'])) for r in existing}


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / '.gitignore').write_text('pages/\nimages/\n')
    c = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    if not BACKUP.exists():
        with sqlite3.connect(BACKUP) as dst:
            c.backup(dst)
    snapshot = OUT / 'existing-before.csv'
    if snapshot.exists():
        existing = list(csv.DictReader(snapshot.open()))
    else:
        existing = [dict(r) for r in c.execute("""
            select i.*, s.signature_text as signature, s.id as signature_id
            from runes_imagelink i join meta_information m on m.id=i.meta_id
            join signatures s on s.id=m.signature_id
            where i.link_url like 'https://samlingar.shm.se/%'
            order by s.signature_text, i.id
        """)]
        write('existing-before.csv', existing)
    assert all('/object/' in r['link_url'] for r in existing)
    entries, aliases = catalog(c)
    owners = defaultdict(set)
    for sid, values in aliases.items():
        for value in values:
            owners[norm(value)].add(sid)
    objects = {}
    for r in existing:
        objects.setdefault(r['link_url'], []).append(r)
    galleries, object_rows, errors = [], [], []
    for index, (url, rows) in enumerate(objects.items(), 1):
        try:
            page = fetch(url, 'pages').decode('utf-8', errors='replace')
            owner_ids, basis = matching_owners(page, owners)
            photos = gallery_images(page)
            for r in rows:
                verified = int(r['signature_id']) in owner_ids
                object_rows.append(dict(signature=r['signature'], meta_id=r['meta_id'], object_url=url,
                                        matched=verified, shm_signa=' | '.join(signa(page)), title=title(page),
                                        gallery_images=len(photos), verification=basis))
                if not verified:
                    errors.append(dict(signature=r['signature'], source_url=url, reason='Object no longer confirms assigned signum'))
                    continue
                for iid in photos:
                    galleries.append(dict(signature=r['signature'], meta_id=r['meta_id'], link_url=url,
                                          direct_url=f'https://media.samlingar.shm.se/item/{iid}/thumbnail',
                                          media_id=iid, media_url=f'https://samlingar.shm.se/media/{iid}',
                                          verification=basis, shm_signa=' | '.join(signa(page)), title=title(page)))
        except Exception as error:
            errors.append(dict(signature=' | '.join(r['signature'] for r in rows), source_url=url, reason=str(error)))
        if index % 20 == 0 or index == len(objects):
            print(f'Object galleries: {index}/{len(objects)}', flush=True)
    write('object-galleries.csv', object_rows)
    print(f'Gallery candidates: {len(galleries)}; verifying additional images', flush=True)
    accepted = []
    working = list(existing)
    for row in select_new_images(working, galleries):
        try:
            data = fetch(row['direct_url'], 'images')
            if not is_image(data):
                raise ValueError('Thumbnail is not recognized image data')
            accepted.append(row)
            working.append(row)
        except Exception as error:
            errors.append(dict(signature=row['signature'], source_url=row['direct_url'], reason=str(error)))
        if len(accepted) and len(accepted) % 25 == 0:
            print(f'Additional images verified: {len(accepted)}', flush=True)
    columns = ['signature','meta_id','link_url','direct_url','media_id','media_url','verification','shm_signa','title']
    write('proposed-additions.csv', accepted, columns)
    write('errors.csv', errors, ['signature','source_url','reason'])
    counts = Counter(int(r['meta_id']) for r in working)
    before = Counter(int(r['meta_id']) for r in existing)
    names = {int(r['meta_id']): r['signature'] for r in existing}
    summary = [dict(signature=names[m], meta_id=m, before=before[m], added=counts[m]-before[m], after=counts[m]) for m in sorted(counts, key=lambda m:names[m])]
    write('per-signum.csv', summary)
    assert max(counts.values()) <= LIMIT
    print(json.dumps(dict(existing=len(existing), scoped_signa=len(names), additions=len(accepted),
                          total=len(working), changed_signa=sum(x['added']>0 for x in summary),
                          maximum=max(counts.values()), errors=len(errors)), ensure_ascii=False), flush=True)


def apply():
    existing = list(csv.DictReader((OUT/'existing-before.csv').open()))
    additions = list(csv.DictReader((OUT/'proposed-additions.csv').open()))
    assert BACKUP.exists() and additions
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    before = {r['id']: dict(r) for r in conn.execute('select * from runes_imagelink')}
    current_shm = {r['id'] for r in before.values() if (urlparse(r['link_url']).hostname or '') == 'samlingar.shm.se'}
    assert current_shm == {int(r['id']) for r in existing}, 'SHM set changed since preparation'
    counts = Counter(int(r['meta_id']) for r in existing)
    ids = {int(r['meta_id']) for r in existing}
    seen = {(int(r['meta_id']), image_id(r['direct_url'])) for r in existing}
    for row in existing:
        assert all(str(before[int(row['id'])][k]) == row[k] for k in before[int(row['id'])])
    inserted = []
    with conn:
        for row in additions:
            mid = int(row['meta_id'])
            assert mid in ids and counts[mid] < LIMIT
            assert (mid,row['media_id']) not in seen
            path = OUT/'images'/hashlib.sha256(row['direct_url'].encode()).hexdigest()
            assert is_image(path.read_bytes())
            assert row['media_id'] in gallery_images((OUT/'pages'/hashlib.sha256(row['link_url'].encode()).hexdigest()).read_text())
            caption = 'Image from SHM collections'
            cur = conn.execute('insert into runes_imagelink (meta_id,link_url,direct_url,info,original_info) values (?,?,?,?,?)',
                               (mid,row['link_url'],row['direct_url'],caption,caption))
            inserted.append(dict(image_id=cur.lastrowid, **row))
            counts[mid] += 1
            seen.add((mid,row['media_id']))
        after = {r['id']:dict(r) for r in conn.execute('select * from runes_imagelink')}
        assert all(after[i] == row for i,row in before.items())
        assert len(after)-len(before) == len(additions)
        assert conn.execute('pragma integrity_check').fetchone()[0] == 'ok'
    write('inserted.csv', inserted)
    finish_reports()


def finish_reports():
    """Reports can be regenerated without repeating the committed insertion."""
    existing = list(csv.DictReader((OUT/'existing-before.csv').open()))
    inserted = list(csv.DictReader((OUT/'inserted.csv').open()))
    names = {int(r['meta_id']):r['signature'] for r in existing}
    conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    after = {r['id']:dict(r) for r in conn.execute('select * from runes_imagelink')}
    backup = sqlite3.connect(f'file:{BACKUP}?mode=ro', uri=True)
    backup.row_factory = sqlite3.Row
    before = {r['id']:dict(r) for r in backup.execute('select * from runes_imagelink')}
    assert all(after[i] == r for i,r in before.items())
    assert set(after)-set(before) == {int(r['image_id']) for r in inserted}
    all_links = [dict(signature=names[int(r['meta_id'])], image_id=r['id'], object_url=r['link_url'],
                      media_url=f"https://samlingar.shm.se/media/{image_id(r['direct_url'])}",
                      thumbnail_url=r['direct_url'], added_now=r['id'] not in before)
                 for r in after.values() if urlparse(r['link_url']).hostname=='samlingar.shm.se'
                 and int(r['meta_id']) in names]
    all_links.sort(key=lambda r:(r['signature'],r['image_id']))
    write('all-shm-image-links.csv', all_links)
    counts = Counter(r['signature'] for r in all_links)
    assert len(counts)==len(names) and max(counts.values())<=LIMIT
    assert conn.execute('pragma integrity_check').fetchone()[0]=='ok'
    summary = dict(added=len(inserted), total_shm=len(all_links),
                   scoped_signa=len(names), supplemented_signa=len({r['meta_id'] for r in inserted}),
                   maximum_per_signum=max(counts.values()), existing_images_unchanged=True, integrity_check='ok')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    if '--finish-reports' in sys.argv:
        finish_reports()
    elif '--apply' in sys.argv:
        apply()
    else:
        prepare()
