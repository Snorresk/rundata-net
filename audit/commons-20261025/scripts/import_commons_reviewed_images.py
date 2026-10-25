#!/usr/bin/env python3
"""Import the approved Commons candidates remaining after source exclusions."""
import csv,json,sqlite3,unicodedata
from pathlib import Path
from urllib.parse import unquote,urlparse
from import_commons_missing_images import clean
from audit_commons_existing_sources import title_key,ROOT,DB,SOURCES
REVIEW=ROOT/'audit/commons-20261025/commons-existing-source-review-20261025'
OUT=ROOT/'audit/commons-20261025/commons-reviewed-import-20261025'
def key(url):return unicodedata.normalize('NFC',unquote(url))
def main():
    OUT.mkdir(exist_ok=True);(OUT/'.gitignore').write_text('*.sqlite3\n')
    rows=list(csv.DictReader((REVIEW/'retained-candidates.csv').open(encoding='utf-8-sig')))
    assert len(rows)==1240 and all(r['decision']=='retain_candidate' for r in rows)
    archive={}
    for p in SOURCES.glob('*_filtered.csv'):
        for r in csv.DictReader(p.open(encoding='utf-8-sig')):
            archive[title_key(r['file_title'])]=r
    pages={};aliases={}
    for p in (REVIEW/'cache').glob('*.json'):
        q=json.loads(p.read_text()).get('query',{})
        for part in ('normalized','redirects'):
            for a in q.get(part,[]):aliases[title_key(a['from'])]=title_key(a['to'])
        for page in q.get('pages',[]):pages[title_key(page['title'])]=page
    conn=sqlite3.connect(DB);conn.row_factory=sqlite3.Row
    before={r['id']:dict(r) for r in conn.execute('select * from runes_imagelink')}
    backup=OUT/'before-import.sqlite3'
    assert not backup.exists(),'Import already prepared: inspect audit before repeating'
    with sqlite3.connect(backup) as dst:conn.backup(dst)
    inserted=[];skipped=[]
    with conn:
        existing={(r['meta_id'],key(r['link_url'])) for r in before.values()}
        for row in rows:
            mid=int(row['meta_id']);sig=row['signum']
            assert conn.execute('select s.signature_text from meta_information m join signatures s on s.id=m.signature_id where m.id=?',(mid,)).fetchone()[0]==sig
            assert int(row['confidence'])>=90
            title=title_key(row['file_title']);seen=set()
            while title in aliases and title not in seen:seen.add(title);title=aliases[title]
            page=pages[title];ii=page['imageinfo'][0];direct=ii['url']
            assert not page.get('missing') and page.get('ns')==6
            assert urlparse(direct).hostname=='upload.wikimedia.org'
            source=archive[title_key(row['file_title'])]
            assert source['mime'].startswith('image/')
            thumb=source['thumbnail_url'] or direct
            # A renamed file uses the current, confirmed original instead of an old thumbnail.
            if title!=title_key(row['file_title']):thumb=direct
            assert urlparse(thumb).hostname in {'upload.wikimedia.org','thumb.wikimedia.org'}
            url=row['commons_file_page'];assert urlparse(url).hostname=='commons.wikimedia.org'
            pair=(mid,key(url))
            if pair in existing:skipped.append(row);continue
            meta=ii.get('extmetadata',{})
            artist=clean((meta.get('Artist') or {}).get('value','')) or row['photographer']
            license_name=clean((meta.get('LicenseShortName') or {}).get('value','')) or clean(source['license_short_name'])
            info='Wikimedia Commons'
            for label,value in [('artist',artist),('license',license_name)]:
                if value:info+=f'; {label}: {value}'
            info=info[:1500]
            cur=conn.execute('insert into runes_imagelink (meta_id,link_url,direct_url,info,original_info) values (?,?,?,?,?)',(mid,url,thumb,info,info))
            existing.add(pair)
            inserted.append(dict(image_id=cur.lastrowid,**row,thumbnail_to_import=thumb,current_original_url=direct,verification_status='live_commons_metadata_verified_image_bytes_not_downloaded'))
        after={r['id']:dict(r) for r in conn.execute('select * from runes_imagelink')}
        assert all(after[i]==r for i,r in before.items())
        assert set(after)-set(before)=={r['image_id'] for r in inserted}
        assert len(inserted)+len(skipped)==1240
        assert conn.execute('pragma integrity_check').fetchone()[0]=='ok'
    for name,data in [('inserted.csv',inserted),('already-present.csv',skipped)]:
        with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]) if data else list(rows[0]));w.writeheader();w.writerows(data)
    summary=dict(inserted=len(inserted),signa=len({r['signum'] for r in inserted}),already_present=len(skipped),images_before=len(before),images_after=len(after),all_existing_image_rows_unchanged=True,integrity_check='ok')
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
