#!/usr/bin/env python3
"""Filter Rundata Wikimedia Commons review CSVs for easier manual review.

Rules:
  * If a signature has one or more 100-confidence candidates, keep only those
    100-confidence rows.
  * If a signature has exactly one candidate and it is below 90 confidence,
    keep it but mark it for manual checking.
  * Otherwise keep the signature's candidate rows unchanged.

The script writes companion files and never overwrites the source CSVs unless
``--overwrite`` is explicitly passed.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


REVIEW_NOTE_COLUMN = "review_note"


def confidence(row: dict[str, Any]) -> int:
    try:
        return int(str(row.get("confidence", "")).strip())
    except ValueError:
        return 0


def rank_filtered_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("signature", ""))].append(row)

    output_rows: list[dict[str, Any]] = []
    for signature in sorted(grouped):
        group = grouped[signature]
        perfect = [row for row in group if confidence(row) == 100]
        if perfect:
            kept = perfect
            note = "auto-kept: one or more 100-confidence candidates; lower-confidence candidates removed"
        else:
            kept = group
            note = ""
            if len(group) == 1 and confidence(group[0]) < 90:
                note = "manual check: only one candidate and confidence below 90"

        kept = sorted(kept, key=lambda row: (-confidence(row), str(row.get("file_title", "")).casefold()))
        for rank, row in enumerate(kept, start=1):
            new_row = dict(row)
            new_row["rank"] = rank
            new_row[REVIEW_NOTE_COLUMN] = note
            output_rows.append(new_row)

    return output_rows


def output_path_for(input_path: Path, suffix: str) -> Path:
    if input_path.name.endswith("_review.csv"):
        return input_path.with_name(input_path.name.replace("_review.csv", f"_{suffix}.csv"))
    return input_path.with_name(f"{input_path.stem}_{suffix}{input_path.suffix}")


def filter_file(input_path: Path, output_path: Path, overwrite: bool = False) -> dict[str, int]:
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"{output_path} exists; use --overwrite to replace it")

    with input_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if REVIEW_NOTE_COLUMN not in fieldnames:
        fieldnames.append(REVIEW_NOTE_COLUMN)

    filtered_rows = rank_filtered_rows(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_rows)

    signatures_before = {row.get("signature", "") for row in rows}
    signatures_after = {row.get("signature", "") for row in filtered_rows}
    manual_check_signatures = {
        row.get("signature", "")
        for row in filtered_rows
        if str(row.get(REVIEW_NOTE_COLUMN, "")).startswith("manual check:")
    }
    perfect_reduced_signatures = {
        row.get("signature", "")
        for row in filtered_rows
        if str(row.get(REVIEW_NOTE_COLUMN, "")).startswith("auto-kept:")
    }

    return {
        "rows_before": len(rows),
        "rows_after": len(filtered_rows),
        "rows_removed": len(rows) - len(filtered_rows),
        "signatures_before": len(signatures_before),
        "signatures_after": len(signatures_after),
        "manual_check_signatures": len(manual_check_signatures),
        "perfect_reduced_signatures": len(perfect_reduced_signatures),
    }


def iter_input_files(patterns: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        matched = sorted(Path().glob(pattern))
        if not matched:
            matched = [Path(pattern)]
        for path in matched:
            if not path.exists() or not path.is_file():
                continue
            if path.name.endswith("_filtered.csv"):
                continue
            if path in seen:
                continue
            seen.add(path)
            paths.append(path)
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create filtered Wikimedia Commons review CSV companions.")
    parser.add_argument("inputs", nargs="+", help="CSV files or glob patterns, for example 'rundata_commons_*_review.csv'.")
    parser.add_argument("--suffix", default="filtered", help="Output suffix. Default: filtered.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing output files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = iter_input_files(args.inputs)
    total_before = 0
    total_after = 0
    total_manual = 0
    total_reduced_signatures = 0

    for input_path in paths:
        output_path = output_path_for(input_path, args.suffix)
        summary = filter_file(input_path, output_path, overwrite=args.overwrite)
        total_before += summary["rows_before"]
        total_after += summary["rows_after"]
        total_manual += summary["manual_check_signatures"]
        total_reduced_signatures += summary["perfect_reduced_signatures"]
        print(
            f"{input_path} -> {output_path}: "
            f"{summary['rows_before']} rows to {summary['rows_after']} "
            f"({summary['rows_removed']} removed); "
            f"{summary['manual_check_signatures']} manual-check signatures; "
            f"{summary['perfect_reduced_signatures']} signatures reduced by 100-confidence rule"
        )

    print("COMMONS_REVIEW_FILTER_REPORT")
    print(f"files_processed={len(paths)}")
    print(f"rows_before={total_before}")
    print(f"rows_after={total_after}")
    print(f"rows_removed={total_before - total_after}")
    print(f"manual_check_signatures={total_manual}")
    print(f"perfect_reduced_signatures={total_reduced_signatures}")


if __name__ == "__main__":
    main()
