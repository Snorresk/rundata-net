#!/usr/bin/env python3
"""Rebuild RAÄ image links for inscriptions cleaned from shared-link clusters.

Usage:
    python utility/rebuild_raa_links_for_shared_clusters.py \
        --signa-csv raa_shared_cluster_signa_20261005-214113.csv

The script searches RAÄ Arkivsök advanced search by runsignum and inserts exact
metadata hits into runes_imagelink. It writes found/no-match/error reports.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sqlite3
import ssl
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "rundatanet/static/runes/runes.sqlite3"
RAA_ADVANCED_API = "https://arkivsok.raa.se/api/dokumentation/search/advanced"
UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)


def read_signa(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row["signature"] for row in csv.DictReader(handle)]


def find_uuid(hit: dict) -> str:
    for key in ("id", "uuid", "dokumentId", "dokumentationId", "documentationId"):
        value = hit.get(key)
        if value and UUID_RE.fullmatch(str(value)):
            return str(value)

    text = json.dumps(hit, ensure_ascii=False)
    match = UUID_RE.search(text)
    return match.group(0) if match else ""


def fetch_hits(signature: str, timeout: float, context: ssl.SSLContext) -> list[dict]:
    body = json.dumps(
        {
            "criterias": [{"key": "runsignum", "values": [signature]}],
            "contentOption": "includeAll",
            "page": 0,
            "pagesize": 100,
        }
    ).encode()
    request = urllib.request.Request(
        RAA_ADVANCED_API,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Rundata link audit"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data.get("indexResults") or data.get("items") or data.get("hits") or data.get("results") or []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signa-csv", required=True, type=Path)
    parser.add_argument("--db", default=DB_PATH, type=Path)
    parser.add_argument("--timeout", default=8.0, type=float)
    parser.add_argument("--sleep", default=0.03, type=float)
    parser.add_argument("--limit", default=0, type=int, help="Optional max number of signa to process.")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = args.db.with_name(f"{args.db.name}.before-raa-shared-cluster-rebuild-{timestamp}.bak")
    shutil.copy2(args.db, backup)

    found_csv = ROOT / f"raa_shared_cluster_rebuild_found_{timestamp}.csv"
    no_match_csv = ROOT / f"raa_shared_cluster_rebuild_no_match_{timestamp}.csv"
    errors_csv = ROOT / f"raa_shared_cluster_rebuild_errors_{timestamp}.csv"

    signa = read_signa(args.signa_csv)
    if args.limit:
        signa = signa[: args.limit]

    context = ssl._create_unverified_context()
    connection = sqlite3.connect(args.db)
    cursor = connection.cursor()

    found_rows: list[list[str]] = []
    no_match_rows: list[list[str]] = []
    error_rows: list[list[str]] = []
    inserted = 0
    existing = 0

    for index, signature in enumerate(signa, 1):
        try:
            hits = fetch_hits(signature, args.timeout, context)
        except Exception as exc:
            error_rows.append([signature, repr(exc)])
            continue

        exact_hits: list[tuple[str, str, str]] = []
        for hit in hits:
            text = json.dumps(hit, ensure_ascii=False)
            if signature not in text:
                continue
            uuid = find_uuid(hit)
            if not uuid:
                continue
            title = hit.get("titel") or hit.get("title") or hit.get("displayName") or ""
            description = hit.get("innehallBeskrivning") or hit.get("description") or ""
            exact_hits.append((uuid, title, description))

        deduped: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for hit in exact_hits:
            if hit[0] not in seen:
                seen.add(hit[0])
                deduped.append(hit)

        if not deduped:
            no_match_rows.append([signature])
            continue

        for uuid, title, description in deduped:
            doc_uri = f"https://pub.raa.se/dokumentation/{uuid}"
            link_url = "https://arkivsok.raa.se/document?uri=" + urllib.parse.quote(doc_uri, safe="")
            found_rows.append([signature, uuid, link_url, title, description])
            cursor.execute(
                "select count(*) from runes_imagelink where meta_id=? and link_url=?",
                (signature, link_url),
            )
            if cursor.fetchone()[0]:
                existing += 1
                continue
            cursor.execute(
                "insert into runes_imagelink (link_url, direct_url, meta_id, info, original_info) values (?, ?, ?, ?, ?)",
                (link_url, "", signature, title, description),
            )
            inserted += 1

        if index % 25 == 0:
            connection.commit()
            print(f"processed {index}/{len(signa)} inserted={inserted}", flush=True)
        time.sleep(args.sleep)

    connection.commit()
    connection.close()

    with found_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["signature", "uuid", "link_url", "title", "description"])
        writer.writerows(found_rows)
    with no_match_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["signature"])
        writer.writerows(no_match_rows)
    with errors_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["signature", "error"])
        writer.writerows(error_rows)

    print(f"backup {backup}")
    print(f"signa {len(signa)}")
    print(f"found_links {len(found_rows)}")
    print(f"inserted {inserted}")
    print(f"existing {existing}")
    print(f"no_match {len(no_match_rows)}")
    print(f"errors {len(error_rows)}")
    print(f"found_csv {found_csv}")
    print(f"no_match_csv {no_match_csv}")
    print(f"errors_csv {errors_csv}")


if __name__ == "__main__":
    main()
