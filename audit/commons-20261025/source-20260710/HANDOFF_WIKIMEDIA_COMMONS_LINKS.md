# Handoff: Wikimedia Commons links for Rundata inscriptions

Date: 2026-07-10

This folder contains the uncommitted working files for the Wikimedia Commons link experiment. Nothing here has been imported into the Rundata database and nothing has been committed to Git.

## What was done

We created a script that searches Wikimedia Commons for possible image links for Rundata inscriptions, scores the matches, and exports review CSV files. The script is read-only against the Rundata database: it queries `runes.sqlite3` only to get inscription signatures and metadata.

Main script:

- `export_wikimedia_commons_links.py`

Filtering script:

- `filter_wikimedia_commons_review.py`

The export script was improved during the work so alias signatures can use their canonical/parent signature for searching and scoring. This was especially important for Danish `DK ...` signatures, which are aliases of `DR ...` records in the local database.

## Generated review files

There are 23 original review CSV files:

- Swedish landscape files, for example `rundata_commons_uppland_review.csv`, `rundata_commons_sodermanland_review.csv`, etc.
- Denmark files:
  - `rundata_commons_denmark_dr_review.csv`
  - `rundata_commons_denmark_dk_review.csv`
- Norway file:
  - `rundata_commons_norway_n_review.csv`

The original review files contain up to 10 candidate Commons image links per inscription, sorted by confidence.

## Filtered files

There are also 23 filtered companion files named:

- `*_filtered.csv`

Filtering rule:

1. If an inscription/signature has one or more links with confidence `100`, keep only the `100` links and remove the lower-confidence links for that same signature.
2. If an inscription/signature has only one link and that link has confidence below `90`, keep it but mark it for manual review with:
   - `manual check: only one candidate and confidence below 90`
3. Otherwise, keep the candidate rows unchanged.

Filtering result:

- Rows before filtering: 8877
- Rows after filtering: 8117
- Rows removed: 760
- Signatures simplified by the 100-confidence rule: 1290
- Manual-check signatures: 484

Helper files:

- `rundata_commons_filtered_summary.csv`
  - One summary row per review file.
- `rundata_commons_manual_check.csv`
  - Only the rows that need manual checking.

## Important caution

The filtered files are easier to review, but they are not automatically “approved” for database import.

Recommended review order:

1. Start with `rundata_commons_manual_check.csv`.
2. Then inspect the filtered files for high-value regions/countries.
3. Norway has many medium-confidence matches, especially confidence `53`, so it needs more careful human review than the strongest Swedish and Danish matches.

## Commands used / useful commands

Example export command:

```bash
.venv/bin/python utility/export_wikimedia_commons_links.py \
  --db rundatanet/static/runes/runes.sqlite3 \
  --out rundata_commons_uppland_review.csv \
  --signature-prefix 'U ' \
  --max-per-inscription 10 \
  --search-limit 10 \
  --max-queries 8 \
  --delay 0.1 \
  --timeout 60 \
  --max-retries 5
```

Example filtering command:

```bash
.venv/bin/python utility/filter_wikimedia_commons_review.py 'rundata_commons_*_review.csv' --overwrite
```

The copies of both scripts are placed in this folder for safekeeping. In the project repo, the same scripts were also present under `utility/` during this work, but this work is intentionally not committed.

## Verification already done

The filtered files passed an integrity check:

- Every filtered file keeps the same set of signatures as its original review file.
- If a signature had confidence `100` rows, only confidence `100` rows remain for that signature.
- If a signature had exactly one candidate below confidence `90`, it is marked with the manual-check note.

The project checks passed during the work:

- `pytest rundatanet/tests/test_export_wikimedia_commons_links.py -q`
- `python manage.py check`

## Current status

This is a working handoff/archive folder for later continuation. The next step, when ready, is to decide which reviewed links should be imported into the Rundata database and define a safe import script.
