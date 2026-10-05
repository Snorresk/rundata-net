#!/usr/bin/env python3
"""Rebuild SHM image links removed from inscriptions with noisy SHM clusters."""

from __future__ import annotations

import csv
import html
import json
import re
import ssl
import sqlite3
import sys
import time
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "rundatanet/static/runes/runes.sqlite3"
REMOVED_REPORT = ROOT / "shm_over5_removed_20261005-155825.csv"
STAMP = time.strftime("%Y%m%d-%H%M%S")
ADDED_REPORT = ROOT / f"shm_exact_links_added_{STAMP}.csv"
NO_MATCH_REPORT = ROOT / f"shm_exact_links_no_match_{STAMP}.csv"
AMBIGUOUS_REPORT = ROOT / f"shm_exact_links_ambiguous_{STAMP}.csv"
SEARCH_URL = "https://samlingar.shm.se/api/v1/search"
USER_AGENT = "rundata-net-link-cleanup/1.0"
SSL_CONTEXT = ssl._create_unverified_context()


def fetch_text(url: str, timeout: int = 30, accept: str = "text/html") -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
        return response.read().decode("utf-8", errors="replace")


def unique_removed_signatures() -> list[tuple[int, str]]:
    signatures: dict[str, int] = {}
    with REMOVED_REPORT.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            signatures.setdefault(row["signature"], int(row["meta_id"]))
    return sorted(signatures.items(), key=lambda item: item[0])


def canonical_object_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def search_candidates(signature: str) -> list[dict]:
    params = urlencode(
        {"type": "object", "query": signature, "rows": 25, "offset": 0},
        quote_via=quote,
    )
    payload = json.loads(fetch_text(f"{SEARCH_URL}?{params}", accept="application/json"))
    return payload.get("items", [])


def has_exact_runsignum(page: str, signature: str) -> bool:
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    text = re.sub(r"\s+", " ", text)
    pattern = rf"Runsignum\s*:\s*{re.escape(signature)}(?!\S)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def image_thumbnail(candidate: dict) -> str:
    image = candidate.get("image") or {}
    sizes = image.get("sizes") or {}
    for key in ("thumbnail", "small", "medium"):
        value = sizes.get(key) or {}
        if value.get("url"):
            return value["url"]
    return ""


def validate_candidates(signature: str, candidates: Iterable[dict]) -> list[dict]:
    exact_matches = []
    for candidate in candidates:
        if candidate.get("type") != "object" or not candidate.get("url"):
            continue
        object_url = canonical_object_url(candidate["url"])
        try:
            page = fetch_text(object_url)
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"warn: {signature}: could not fetch {object_url}: {exc}", file=sys.stderr)
            continue
        if has_exact_runsignum(page, signature):
            exact_matches.append(
                {
                    "signature": signature,
                    "object_url": object_url,
                    "direct_url": image_thumbnail(candidate),
                    "title": candidate.get("title", ""),
                    "object_number": ((candidate.get("fields") or {}).get("objectNumber") or {}).get("value", ""),
                }
            )
        time.sleep(0.08)
    return exact_matches


def existing_link(conn: sqlite3.Connection, meta_id: int, url: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM runes_imagelink WHERE meta_id = ? AND link_url = ? LIMIT 1",
            (meta_id, url),
        ).fetchone()
        is not None
    )


def insert_link(conn: sqlite3.Connection, meta_id: int, match: dict) -> bool:
    if existing_link(conn, meta_id, match["object_url"]):
        return False
    info = "Samlingar på Statens historiska museum"
    conn.execute(
        """
        INSERT INTO runes_imagelink (link_url, direct_url, meta_id, info, original_info)
        VALUES (?, ?, ?, ?, ?)
        """,
        (match["object_url"], match["direct_url"], meta_id, info, info),
    )
    return True


def write_rows(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    targets = unique_removed_signatures()
    added_rows: list[dict] = []
    no_match_rows: list[dict] = []
    ambiguous_rows: list[dict] = []

    conn = sqlite3.connect(DB_PATH)
    try:
        for index, (signature, meta_id) in enumerate(targets, start=1):
            print(f"{index}/{len(targets)} {signature}", flush=True)
            try:
                candidates = search_candidates(signature)
                matches = validate_candidates(signature, candidates)
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                no_match_rows.append(
                    {
                        "signature": signature,
                        "meta_id": meta_id,
                        "reason": f"search failed: {exc}",
                        "candidate_count": "",
                    }
                )
                continue

            if not matches:
                no_match_rows.append(
                    {
                        "signature": signature,
                        "meta_id": meta_id,
                        "reason": "no exact Runsignum match",
                        "candidate_count": len(candidates),
                    }
                )
            elif len(matches) > 1:
                for match in matches:
                    ambiguous_rows.append({"meta_id": meta_id, **match})
            else:
                match = matches[0]
                inserted = insert_link(conn, meta_id, match)
                added_rows.append({"meta_id": meta_id, "inserted": inserted, **match})
                conn.commit()
            time.sleep(0.12)
    finally:
        conn.close()

    write_rows(
        ADDED_REPORT,
        ["signature", "meta_id", "inserted", "object_url", "direct_url", "title", "object_number"],
        added_rows,
    )
    write_rows(
        NO_MATCH_REPORT,
        ["signature", "meta_id", "reason", "candidate_count"],
        no_match_rows,
    )
    write_rows(
        AMBIGUOUS_REPORT,
        ["signature", "meta_id", "object_url", "direct_url", "title", "object_number"],
        ambiguous_rows,
    )

    print(f"added_or_existing={len(added_rows)}")
    print(f"no_match={len(no_match_rows)}")
    print(f"ambiguous={len(ambiguous_rows)}")
    print(f"added_report={ADDED_REPORT}")
    print(f"no_match_report={NO_MATCH_REPORT}")
    print(f"ambiguous_report={AMBIGUOUS_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
