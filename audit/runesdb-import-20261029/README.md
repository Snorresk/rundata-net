# RuneS import 2026-10-29

Source: Desktop/RuneSdb/RuneS signaturgranskning 2026-10-24/missing.csv,
copied unchanged to missing-source.csv. The saved audit reports these 80
links as live verified with graphtype analysis and unambiguous main signatures.
This import did not repeat the remote audit.

All 80 signatures matched exactly one metadata record in the current database.
Imported 80 new reference associations with label `Graphtype analysis (RuneS)`.
Existing references were preserved, including the two disputed older mappings
mentioned in the source audit. Review/ambiguous rows were not imported.

SQLite integrity and foreign-key checks passed inside the import transaction.
A repeat dry run found 80 existing associations and zero additions.
The ignored `runes.before-import.sqlite3` is the SQLite backup taken before import.
See result.json for each imported association.

Reproduce the dry run:

    python3 utility/import_verified_runesdb_links.py audit/runesdb-import-20261029/missing-source.csv
