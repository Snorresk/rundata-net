#!/usr/bin/env python3
"""Export high-value DB strings for English translation review.

The output is an audit CSV: it does not change the database. Rows are grouped by
source table, source field, and original value so repeated labels can be
translated once and applied consistently later.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sqlite3
from pathlib import Path


DEFAULT_DB = Path("rundatanet/static/runes/runes.sqlite3")
DEFAULT_OUTPUT = Path("translation_audit/high_value_metadata_image_captions.csv")

WORD_RE = re.compile(r"[\wÅÄÖåäöÆØæøÉéÞþÐð]+(?:[-'][\wÅÄÖåäöÆØæøÉéÞþÐð]+)?")

META_FIELDS = (
    "original_site",
    "rune_type",
    "dating",
    "style",
    "material",
    "objectInfo",
)

FIELD_POLICIES = {
    "original_site": "Translate yes/no and descriptive location phrases; preserve compass abbreviations.",
    "rune_type": "Translate rune-type terminology; preserve uncertain markers and technical abbreviations.",
    "dating": "Translate period wording; preserve date ranges, U/V/M prefixes, and uncertainty markers.",
    "style": "Preserve style codes; translate only plain-language additions.",
    "material": "Translate material names and color adjectives; preserve question marks.",
    "objectInfo": "Translate object type; preserve counts, parentheses, and specialist terms where needed.",
    "name": "Translate controlled material-type labels.",
    "info": "Translate caption text; preserve names, institutions, licenses, URLs, and arrow/link markers.",
}


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def word_count(value: str) -> int:
    return len(WORD_RE.findall(value or ""))


def value_key(source_table: str, source_field: str, original: str) -> str:
    raw = f"{source_table}\x1f{source_field}\x1f{original}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def priority_for(field: str, frequency: int, chars: int) -> str:
    if field in {"objectInfo", "material", "name"} and frequency >= 25:
        return "high"
    if field == "info" and frequency >= 5:
        return "high"
    if field in {"rune_type", "original_site"} or frequency >= 5 or chars >= 80:
        return "medium"
    return "low"


def emit_meta_rows(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for field in META_FIELDS:
        query = f"""
            SELECT
                m.{field} AS original,
                COUNT(*) AS frequency,
                GROUP_CONCAT(m.id, '|') AS source_ids,
                GROUP_CONCAT(s.signature_text, '|') AS signatures
            FROM meta_information m
            INNER JOIN signatures s ON s.id = m.signature_id
            WHERE TRIM(m.{field}) <> ''
            GROUP BY m.{field}
            ORDER BY COUNT(*) DESC, LOWER(m.{field})
        """
        for row in connection.execute(query):
            original = row["original"]
            signatures = (row["signatures"] or "").split("|")
            source_ids = (row["source_ids"] or "").split("|")
            rows.append(
                make_row(
                    source_table="meta_information",
                    source_field=field,
                    original=original,
                    frequency=row["frequency"],
                    source_ids=source_ids,
                    signatures=signatures,
                )
            )
    return rows


def emit_material_type_rows(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    query = """
        SELECT
            mt.id AS source_id,
            mt.name AS original,
            COUNT(m.id) AS frequency,
            GROUP_CONCAT(m.id, '|') AS meta_ids,
            GROUP_CONCAT(s.signature_text, '|') AS signatures
        FROM material_types mt
        LEFT JOIN meta_information m ON m.materialType_id = mt.id
        LEFT JOIN signatures s ON s.id = m.signature_id
        WHERE TRIM(mt.name) <> ''
        GROUP BY mt.id, mt.name
        ORDER BY COUNT(m.id) DESC, LOWER(mt.name)
    """
    for row in connection.execute(query):
        original = row["original"]
        source_ids = [str(row["source_id"])]
        signatures = (row["signatures"] or "").split("|")
        rows.append(
            make_row(
                source_table="material_types",
                source_field="name",
                original=original,
                frequency=row["frequency"],
                source_ids=source_ids,
                signatures=signatures,
            )
        )
    return rows


def emit_image_caption_rows(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    query = """
        SELECT
            img.info AS original,
            COUNT(*) AS frequency,
            GROUP_CONCAT(img.id, '|') AS source_ids,
            GROUP_CONCAT(s.signature_text, '|') AS signatures
        FROM runes_imagelink img
        INNER JOIN meta_information m ON m.id = img.meta_id
        INNER JOIN signatures s ON s.id = m.signature_id
        WHERE TRIM(img.info) <> ''
        GROUP BY img.info
        ORDER BY COUNT(*) DESC, LOWER(img.info)
    """
    for row in connection.execute(query):
        original = row["original"]
        signatures = (row["signatures"] or "").split("|")
        source_ids = (row["source_ids"] or "").split("|")
        rows.append(
            make_row(
                source_table="runes_imagelink",
                source_field="info",
                original=original,
                frequency=row["frequency"],
                source_ids=source_ids,
                signatures=signatures,
            )
        )
    return rows


def make_row(
    *,
    source_table: str,
    source_field: str,
    original: str,
    frequency: int,
    source_ids: list[str],
    signatures: list[str],
) -> dict[str, object]:
    signatures = [item for item in signatures if item]
    source_ids = [item for item in source_ids if item]
    return {
        "value_key": value_key(source_table, source_field, original),
        "priority": priority_for(source_field, frequency, len(original)),
        "source_table": source_table,
        "source_field": source_field,
        "frequency": frequency,
        "char_count": len(original),
        "word_count": word_count(original),
        "sample_signatures": " | ".join(signatures[:12]),
        "sample_source_ids": " | ".join(source_ids[:12]),
        "source_id_count": len(source_ids),
        "translation_policy": FIELD_POLICIES.get(source_field, ""),
        "original": original,
        "suggested_en": "",
        "review_status": "todo",
        "reviewer_notes": "",
    }


def export(db_path: Path, output_path: Path) -> dict[str, int]:
    with connect(db_path) as connection:
        rows = []
        rows.extend(emit_meta_rows(connection))
        rows.extend(emit_material_type_rows(connection))
        rows.extend(emit_image_caption_rows(connection))

    rows.sort(
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2}[str(row["priority"])],
            str(row["source_table"]),
            str(row["source_field"]),
            -int(row["frequency"]),
            str(row["original"]).lower(),
        )
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "value_key",
        "priority",
        "source_table",
        "source_field",
        "frequency",
        "char_count",
        "word_count",
        "sample_signatures",
        "sample_source_ids",
        "source_id_count",
        "translation_policy",
        "original",
        "suggested_en",
        "review_status",
        "reviewer_notes",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return {
        "rows": len(rows),
        "high": sum(1 for row in rows if row["priority"] == "high"),
        "medium": sum(1 for row in rows if row["priority"] == "medium"),
        "low": sum(1 for row in rows if row["priority"] == "low"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    stats = export(args.db, args.output)
    print(f"Wrote {stats['rows']} rows to {args.output}")
    print(f"Priority counts: high={stats['high']} medium={stats['medium']} low={stats['low']}")


if __name__ == "__main__":
    main()
