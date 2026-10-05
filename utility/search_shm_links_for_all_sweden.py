#!/usr/bin/env python3
"""Find and add exact SHM object links for all Swedish inscriptions."""

from __future__ import annotations

import csv
import sys
import sqlite3
import time
from urllib.error import HTTPError
from pathlib import Path

from rebuild_shm_links_for_over5 import (
    DB_PATH,
    search_candidates,
    validate_candidates,
)


ROOT = Path(__file__).resolve().parents[1]
STAMP = time.strftime("%Y%m%d-%H%M%S")
ADDED_REPORT = ROOT / f"shm_sweden_exact_links_added_{STAMP}.csv"
EXISTING_REPORT = ROOT / f"shm_sweden_exact_links_existing_{STAMP}.csv"
NO_MATCH_REPORT = ROOT / f"shm_sweden_exact_links_no_match_{STAMP}.csv"
AMBIGUOUS_REPORT = ROOT / f"shm_sweden_exact_links_ambiguous_{STAMP}.csv"
ERROR_REPORT = ROOT / f"shm_sweden_exact_links_errors_{STAMP}.csv"

SWEDISH_CODES = {
    "Öl",
    "Ög",
    "Sö",
    "Sm",
    "Vg",
    "U",
    "Vs",
    "Nä",
    "Vr",
    "Gs",
    "Hs",
    "M",
    "Ån",
    "D",
    "Hr",
    "J",
    "Lp",
    "Ds",
    "Bo",
    "G",
    "SE",
}


def write_rows(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def swedish_targets(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    placeholders = ",".join("?" for _ in SWEDISH_CODES)
    rows = conn.execute(
        f"""
        SELECT m.id, s.signature_text
        FROM meta_information m
        JOIN signatures s ON m.signature_id = s.id
        WHERE s.parent_id IS NULL
          AND substr(s.signature_text, 1, instr(s.signature_text || ' ', ' ') - 1) IN ({placeholders})
        ORDER BY s.signature_text
        """,
        sorted(SWEDISH_CODES),
    ).fetchall()
    return [(int(row[0]), row[1]) for row in rows]


def targets_from_error_report(path: Path) -> list[tuple[int, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [(int(row["meta_id"]), row["signature"]) for row in csv.DictReader(handle)]


def search_with_retry(signature: str) -> list[dict]:
    for attempt in range(5):
        try:
            return search_candidates(f'"{signature}"')
        except HTTPError as exc:
            if exc.code != 429 or attempt == 4:
                raise
            wait = 20 + attempt * 20
            print(f"rate limited; sleeping {wait}s", flush=True)
            time.sleep(wait)
    return []


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


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    added_rows: list[dict] = []
    existing_rows: list[dict] = []
    no_match_rows: list[dict] = []
    ambiguous_rows: list[dict] = []
    error_rows: list[dict] = []

    try:
        targets = targets_from_error_report(Path(sys.argv[1])) if len(sys.argv) > 1 else swedish_targets(conn)
        print(f"targets={len(targets)}", flush=True)
        for index, (meta_id, signature) in enumerate(targets, start=1):
            if index == 1 or index % 50 == 0 or index == len(targets):
                print(f"{index}/{len(targets)} {signature}", flush=True)
            try:
                candidates = search_with_retry(signature)
                matches = validate_candidates(signature, candidates)
            except Exception as exc:
                error_rows.append({"signature": signature, "meta_id": meta_id, "error": repr(exc)})
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
                row = {"meta_id": meta_id, "inserted": inserted, **match}
                if inserted:
                    added_rows.append(row)
                    conn.commit()
                else:
                    existing_rows.append(row)

            if index % 25 == 0:
                write_reports(added_rows, existing_rows, no_match_rows, ambiguous_rows, error_rows)
            time.sleep(0.9)
    finally:
        conn.close()

    write_reports(added_rows, existing_rows, no_match_rows, ambiguous_rows, error_rows)
    print(f"added={len(added_rows)}")
    print(f"existing={len(existing_rows)}")
    print(f"no_match={len(no_match_rows)}")
    print(f"ambiguous_rows={len(ambiguous_rows)}")
    print(f"ambiguous_signatures={len({row['signature'] for row in ambiguous_rows})}")
    print(f"errors={len(error_rows)}")
    print(f"added_report={ADDED_REPORT}")
    print(f"existing_report={EXISTING_REPORT}")
    print(f"no_match_report={NO_MATCH_REPORT}")
    print(f"ambiguous_report={AMBIGUOUS_REPORT}")
    print(f"error_report={ERROR_REPORT}")
    return 0


def write_reports(
    added_rows: list[dict],
    existing_rows: list[dict],
    no_match_rows: list[dict],
    ambiguous_rows: list[dict],
    error_rows: list[dict],
) -> None:
    common = ["signature", "meta_id", "inserted", "object_url", "direct_url", "title", "object_number"]
    write_rows(ADDED_REPORT, common, added_rows)
    write_rows(EXISTING_REPORT, common, existing_rows)
    write_rows(NO_MATCH_REPORT, ["signature", "meta_id", "reason", "candidate_count"], no_match_rows)
    write_rows(
        AMBIGUOUS_REPORT,
        ["signature", "meta_id", "object_url", "direct_url", "title", "object_number"],
        ambiguous_rows,
    )
    write_rows(ERROR_REPORT, ["signature", "meta_id", "error"], error_rows)


if __name__ == "__main__":
    raise SystemExit(main())
