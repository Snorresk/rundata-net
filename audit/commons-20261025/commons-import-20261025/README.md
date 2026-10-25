# Import av Commons-länkar, 25 oktober 2026

Användaren godkände import av Commons-förslag med poäng **över 90**, enbart till de 62 huvudsignum som saknade bildposter enligt täckningsanalysen den 24 oktober. Alla 62 kontrollerades på nytt och hade fortfarande noll bildposter före importen.

## Resultat

- 83 nya bildposter för exakt dessa 62 huvudsignum.
- 65 förslag med poäng 100, 12 med poäng 98 och sex med poäng 95. Inga förslag med poäng 90 eller lägre har importerats.
- Samma Commons-fil har bara importerats en gång per huvudsignum; alias har följts till dagens huvudpost. Gamla meta-ID i exportunderlaget har inte använts för DB-kopplingen.
- Källänk: Commons-filens beskrivningssida. Direktlänk: miniatyradressen från det sparade Commons-underlaget, alternativt originaladressen när miniatyr saknades. Originaladress och äldre artist-/licensmetadata finns kvar i importloggen.
- Samtliga 62 har nu minst en bildpost. Alla tidigare bildrader i hela databasen är identiska med backupen; ingen befintlig rad har ändrats eller tagits bort.
- Totalt innehåller DB nu 115 Commons-källänkar.
- SQLite `integrity_check`: `ok`.

## Kontroll av tillgänglighet

Tio bilder hämtades på nytt och verifierades som bilddata. Därefter svarade Wikimedia med HTTP 429 och `Retry-After: 600`. Nätkontrollen stoppades. Inga försök att kringgå begränsningen gjordes.

De återstående 73 länkarna importerades enligt användarens godkända, sparade poängunderlag utan ny live-verifiering. Statusen `archived_metadata_only_rate_limited` anges på varje sådan rad, medan de tio kontrollerade bilderna har status `live_image_verified`. HTTP 429 visar att förfrågningarna begränsades, inte att dessa filer har konstaterats saknas. Matchningspoängen är fortfarande automatiska poäng från juli-arbetet och innebär ingen ny manuell bildgranskning. Artist och licens i bildtexten härrör också från detta äldre underlag.

## Underlag och återställning

- Källa: de 23 `*_filtered.csv`-filerna i `/Users/sost7972/Desktop/Rundata  test/Rundata Common links`.
- `targets-before.csv`: de 62 godkända, tidigare bildlösa huvudsignumen med aktuella meta-ID.
- `proposed.csv`: deduplicerade importförslag och verifieringsstatus.
- `inserted.csv`: alla importerade poster, inklusive nya bild-ID, ursprunglig signumetikett, poäng, matchningsskäl, filadress, originalbildadress och miniatyradress.
- `per-signum.csv`: antal före, tillagda och totalt per signum.
- `summary.json`: sammanfattning med antal live-kontrollerade respektive arkivbaserade poster.
- `errors.csv`: tom efter förberedelse med godkänt arkivunderlag; nätbegränsningen och dess konsekvenser redovisas ovan och per kandidat i verifieringsstatus.
- Full SQLite-backup: `runes-before-commons-import.sqlite3`, sparad lokalt och undantagen från versionshantering.
- Hämtade bilder sparas lokalt i `images/`, också undantagna från versionshantering.

Verktyg: `utility/import_commons_missing_images.py`. `--archive-only` förbereder från arkivunderlag och redan hämtad bildcache utan nya nätanrop; `--apply` utför importen i en transaktion efter kontroll av att alla 62 fortfarande saknar bilder. En ny importkörning av samma mål stoppas efter att de fått bildposter.

Oberoende kontroll mot fullbackupen bekräftade exakt 83 tillagda rader och inga andra förändringar i bildtabellen. Tre tester för bilddatakontroll och hantering av bildtexter passerar.
