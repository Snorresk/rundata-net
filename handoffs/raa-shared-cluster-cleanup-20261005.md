# RAÄ Shared Cluster Cleanup Handoff, 2026-10-05

Branch: `codex/db-work`

## What Was Done

- Found RAÄ image links that were attached to many unrelated inscriptions.
- Defined a shared RAÄ cluster as a RAÄ `runes_imagelink.link_url` appearing on `20` or more distinct inscriptions.
- Removed those shared RAÄ cluster links from the database:
  - `151` shared RAÄ links
  - `7598` `runes_imagelink` rows
  - `352` affected inscriptions
- Verified after cleanup:
  - `0` RAÄ links remain that are shared by `20` or more inscriptions.
  - `python manage.py check` passes.

Important reports:

- `RAÄ/raa_shared_cluster_signa_20261005-214113.csv`
  - The `352` signa that were affected and need RAÄ rebuild.
- `RAÄ/raa_shared_cluster_links_removed_20261005-214113.csv`
  - Every removed image row: `image_id`, `signature`, `link_url`.

Important backup:

- `rundatanet/static/runes/runes.sqlite3.before-raa-shared-cluster-cleanup-20261005-214113.bak`

## What Remains

The shared bad links are removed, but the correct RAÄ links have not yet been rebuilt for those `352` signa.

An attempted rebuild used RAÄ advanced search by `runsignum`. The first scripts failed because the parser expected `items`; RAÄ returned `indexResults`. A later corrected script started correctly but one RAÄ request hung for too long, so it was stopped before inserting anything. The database was not left half-imported.

## Script For Next Chat

Use:

```bash
python utility/rebuild_raa_links_for_shared_clusters.py --signa-csv RAÄ/raa_shared_cluster_signa_20261005-214113.csv
```

Recommended first smoke test:

```bash
python utility/rebuild_raa_links_for_shared_clusters.py --signa-csv RAÄ/raa_shared_cluster_signa_20261005-214113.csv --limit 10 --timeout 6
```

If that works, run the full command. The script:

- backs up `rundatanet/static/runes/runes.sqlite3`;
- calls `https://arkivsok.raa.se/api/dokumentation/search/advanced`;
- searches by `runsignum`;
- reads RAÄ `indexResults`;
- inserts exact hits into `runes_imagelink`;
- writes `found`, `no_match`, and `errors` CSV files.

Because RAÄ can be slow, use a short timeout and rerun for errors if needed.

## Verification Queries

Check whether large shared RAÄ clusters remain:

```bash
sqlite3 -header -csv rundatanet/static/runes/runes.sqlite3 "select count(*) as shared_raa_links_remaining from (select link_url from runes_imagelink where link_url like '%arkivsok.raa.se%' or link_url like '%pub.raa.se%' group by link_url having count(distinct meta_id) >= 20);"
```

Run app check:

```bash
source .venv/bin/activate && python manage.py check
```

## Notes

- Keep the backup and CSV report files local unless the user explicitly wants to commit them.
- Do not rerun the cluster deletion unless you intentionally want to remove newly imported links that happen to be shared by many signa.
- Some RAÄ results are archival volumes or plansches that mention multiple signa. The current script keeps hits where the queried signum appears in the RAÄ metadata.
