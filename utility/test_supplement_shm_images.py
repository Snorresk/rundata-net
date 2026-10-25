from supplement_shm_images import gallery_images, image_id, select_new_images

A = '11111111-1111-1111-1111-111111111111'
B = '22222222-2222-2222-2222-222222222222'
C = '33333333-3333-3333-3333-333333333333'


def row(mid, iid):
    return {'meta_id':mid, 'media_id':iid, 'direct_url':f'https://media.samlingar.shm.se/item/{iid}/thumbnail'}


def test_gallery_requires_image_membership_and_preserves_order():
    page = f'''<a href="https://samlingar.shm.se/media/{B}">Photo</a>
    <a href="https://media.samlingar.shm.se/item/{B}/large">Original</a>
    <a href="https://samlingar.shm.se/media/{A}">Photo</a>
    <meta content="https://media.samlingar.shm.se/item/{A}/medium">
    <a href="https://samlingar.shm.se/media/{A}">Duplicate</a>
    <a href="https://samlingar.shm.se/media/{C}">No image</a>
    <a href="https://samlingar.shm.se.example.org/media/{C}">Other host</a>'''
    assert gallery_images(page) == [B,A]


def test_limit_counts_existing_rows_across_objects_and_skips_duplicates():
    working = [row(1,A),row(1,A),row(2,A)]
    added = []
    for candidate in select_new_images(working,[row(1,A),row(1,B),row(1,C),row(2,B),row(2,B)],maximum=3):
        added.append(candidate)
        working.append(candidate)
    assert [(x['meta_id'],x['media_id']) for x in added] == [(1,B),(2,B)]


def test_failed_image_does_not_use_a_slot():
    working = [row(1,A)]
    added = []
    for candidate in select_new_images(working,[row(1,B),row(1,C)],maximum=2):
        if candidate['media_id']==B:
            continue
        added.append(candidate)
        working.append(candidate)
    assert [x['media_id'] for x in added] == [C]


def test_photo_ids_do_not_match_other_hosts_or_paths():
    assert image_id(f'https://media.samlingar.shm.se/item/{A}/thumbnail') == A
    assert image_id(f'https://media.samlingar.shm.se.example.org/item/{A}/thumbnail') == ''
    assert image_id(f'https://example.org/media.samlingar.shm.se/item/{A}') == ''


def test_unsupported_url_schemes_are_rejected():
    assert image_id(f'ftp://media.samlingar.shm.se/item/{A}/thumbnail') == ''


def test_reports_preserve_unrelated_legacy_rows_with_text_meta_ids(tmp_path, monkeypatch):
    import csv
    import json
    import sqlite3
    import supplement_shm_images as module

    database = tmp_path/'current.sqlite3'
    backup = tmp_path/'backup.sqlite3'
    rows = [(1,1,'https://samlingar.shm.se/object/'+A,row(1,A)['direct_url']),
            (2,'U 384','https://pub.raa.se/visa/dokumentation/'+B,'')]
    for path in (database,backup):
        with sqlite3.connect(path) as conn:
            conn.execute('create table runes_imagelink (id integer primary key,meta_id,link_url,direct_url)')
            conn.executemany('insert into runes_imagelink values (?,?,?,?)',rows)
    with sqlite3.connect(database) as conn:
        conn.execute('insert into runes_imagelink values (?,?,?,?)',
                     (3,1,'https://samlingar.shm.se/object/'+A,row(1,B)['direct_url']))
    for name,columns,values in (
        ('existing-before.csv',['meta_id','signature'],[[1,'U 1']]),
        ('inserted.csv',['image_id','meta_id'],[[3,1]])):
        with (tmp_path/name).open('w',newline='') as handle:
            writer=csv.writer(handle);writer.writerow(columns);writer.writerows(values)
    monkeypatch.setattr(module,'OUT',tmp_path)
    monkeypatch.setattr(module,'DB',database)
    monkeypatch.setattr(module,'BACKUP',backup)
    module.finish_reports()
    result=json.loads((tmp_path/'summary.json').read_text())
    assert result['added']==1 and result['total_shm']==2
    assert result['existing_images_unchanged'] is True
    with sqlite3.connect(database) as conn:
        assert conn.execute('select meta_id from runes_imagelink where id=2').fetchone()[0]=='U 384'
