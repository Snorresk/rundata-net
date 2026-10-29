"""Import the reviewed RuneS missing-link CSV; default is a dry run."""
import argparse
import csv
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'Graphtype analysis (RuneS)'


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    rows = list(csv.DictReader(args.source.open(encoding='utf-8-sig', newline='')))
    db = ROOT / 'rundatanet/static/runes/runes.sqlite3'
    report_dir = args.source.parent
    conn = sqlite3.connect(db)
    conn.execute('PRAGMA foreign_keys=ON')
    planned, existing = [], []
    seen = set()
    for row in rows:
        number = row['find_no']
        if not re.fullmatch(r'[1-9][0-9]*', number):
            raise ValueError(f'Invalid find number: {number}')
        if row['url'] not in (f'https://www.runesdb.de/de/find/{number}', f'http://www.runesdb.de/de/find/{number}'):
            raise ValueError(f'Unexpected URL: {row}')
        if row['live_verified'] != 'True' or int(row['graphtype_count']) <= 0:
            raise ValueError(f'Unverified row: {row}')
        matches = conn.execute('SELECT mi.id FROM meta_information mi JOIN signatures s ON s.id=mi.signature_id WHERE s.signature_text=?', (row['main_signature'],)).fetchall()
        if len(matches) != 1:
            raise ValueError(f'Ambiguous or missing signature: {row}')
        meta_id = matches[0][0]
        key = (meta_id, number)
        if key in seen:
            raise ValueError(f'Duplicate source association: {key}')
        seen.add(key)
        refs = conn.execute('SELECT r.text FROM "references" r JOIN meta_information_references mr ON mr.reference_id=r.id WHERE mr.metainformation_id=?', (meta_id,)).fetchall()
        present = any(re.search(r'runesdb\.de/(?:de/)?find/' + number + r'/?(?:[?#].*)?$', text or '') for (text,) in refs)
        (existing if present else planned).append(dict(row, meta_id=meta_id))
    if args.apply and planned:
        backup = report_dir / 'runes.before-import.sqlite3'
        if backup.exists():
            raise FileExistsError(backup)
        with sqlite3.connect(backup) as target:
            conn.backup(target)
        with conn:
            for row in planned:
                ref = conn.execute('SELECT id FROM "references" WHERE text=? AND kind=? AND label=?', (row['url'], 'link', LABEL)).fetchone()
                ref_id = ref[0] if ref else conn.execute('INSERT INTO "references" (text,kind,label) VALUES (?,?,?)', (row['url'], 'link', LABEL)).lastrowid
                conn.execute('INSERT INTO meta_information_references (metainformation_id,reference_id) VALUES (?,?)', (row['meta_id'], ref_id))
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or conn.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Database validation failed')
    result = dict(applied=args.apply, source_rows=len(rows), new_associations=len(planned), already_present=len(existing), imported=planned)
    if args.apply:
        (report_dir / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'imported'}))
    conn.close()


if __name__ == '__main__':
    run()
