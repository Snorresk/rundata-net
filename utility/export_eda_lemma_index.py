#!/usr/bin/env python3
"""Export reviewed LoRI pilot lemma attestations for the EDA page."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


INCLUDED_REVIEW_STATUSES = {
    "source_confirmed",
    "source_lemma_new_occurrence",
    "inferred_pattern",
}
PILOT_LEMMA_IDS = {"KIN001", "KIN002", "KIN005"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def rows_by(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row[key]: row for row in rows}


def build_lemma_index(source_dir: Path) -> list[dict[str, object]]:
    lemmas = rows_by(read_csv(source_dir / "01_lexem.csv"), "lemma_id")
    forms = rows_by(read_csv(source_dir / "02_former.csv"), "form_id")
    candidates = rows_by(read_csv(source_dir / "03_kandidater.csv"), "candidate_id")
    reviews = read_csv(source_dir / "04_granskning.csv")

    exported_rows: list[dict[str, object]] = []
    for review in reviews:
        lemma_id = review["accepted_lemma_id"].strip()
        if (
            review["review_status"] not in INCLUDED_REVIEW_STATUSES
            or not lemma_id
            or lemma_id not in PILOT_LEMMA_IDS
        ):
            continue

        candidate_id = review["candidate_id"]
        candidate = candidates[candidate_id]
        lemma = lemmas[lemma_id]
        accepted_form_id = review["accepted_form_id"].strip()
        accepted_form = forms.get(accepted_form_id, {})

        exported_rows.append(
            {
                "candidate_id": candidate_id,
                "signature_id": candidate["signature_id"],
                "signature": candidate["signature"],
                "word_index": int(candidate["word_index"]),
                "lemma_id": lemma_id,
                "lemma_norse": lemma["lemma_norse"],
                "lemma_scandinavian": lemma["lemma_scandinavian"],
                "accepted_form_id": accepted_form_id,
                "accepted_form": accepted_form.get("form", ""),
                "accepted_form_layer": accepted_form.get("normalisation_layer", ""),
                "accepted_case": review["accepted_case"],
                "accepted_number": review["accepted_number"],
                "accepted_gender": review["accepted_gender"],
                "lemma_certainty": review["lemma_certainty"],
                "review_status": review["review_status"],
                "attestation_group_id": review["attestation_group_id"],
                "reading_variant": review["reading_variant"],
                "reading_relation": review["reading_relation"],
                "counting_rule": review["counting_rule"],
                "normalisation_norse": candidate["normalisation_norse"],
                "normalisation_scandinavian": candidate[
                    "normalisation_scandinavian"
                ],
                "transliteration": candidate["transliteration"],
            }
        )

    return sorted(exported_rows, key=lambda row: row["candidate_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source_dir",
        type=Path,
        help="Directory containing 01_lexem.csv through 04_granskning.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("rundatanet/static/runes/lemma_index.json"),
        help="Destination JSON file",
    )
    args = parser.parse_args()

    rows = build_lemma_index(args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output_file:
        json.dump(rows, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")

    print(f"Exported {len(rows)} reviewed lemma tokens to {args.output}")


if __name__ == "__main__":
    main()
