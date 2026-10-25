# Handoff: Wikimedia Commons-länkar och bildexport

Senast uppdaterad: 25 oktober 2026. Gren: `codex/export-images`.

## Klart

Commons-resolvern är implementerad, två godkända importer är utförda och underlagen är samlade i denna mapp. Databasen finns som vanligt i `rundatanet/static/runes/runes.sqlite3`. Sidans databas-cacheversion är `20261025-commons-reviewed-import`.

| Steg | Resultat |
| --- | --- |
| Ursprungliga filtrerade kandidater, poäng 90–100 | 2 610 rader: 2 466 med 100, 144 med 90–99 |
| Efter aliasupplösning och deduplicering | 2 460 signum/fil-par för 1 316 huvudsignum |
| Tidigare helt utan bilder | 62 signa |
| Första importen | 83 länkar till dessa 62 signa, lägsta poäng 95 |
| Granskning av signa som redan hade bilder | 2 377 par, 2 262 unika Commons-filer, 1 254 signa |
| Exkluderade efter godkända regler | 1 137 par |
| Andra importen | 1 240 länkar för 883 signa |
| Nya Commons-länkar sammanlagt | 1 323 |
| Commons-länkar i slutlig DB | 1 355, inklusive 32 tidigare länkar |
| Alla bildrader i slutlig DB | 32 359, jämfört med 31 036 före Commons-importerna |

## Beslut om urval och dubbletter

Poängen är automatiska matchningspoäng, inte sannolikheter eller manuella godkännanden. Det ursprungliga filtret behöll endast 100-poängsträffar när sådana fanns för samma kandidatetikett. En ensam kandidat under 90 flaggades för manuell granskning. Förslag under 90 har redovisats men inte importerats.

Användaren godkände uttryckligen att samma arkiv eller fotograf räcker för att exkludera en Commons-kandidat för samma signum; identiska bildfiler krävs inte.

- RAÄ, SHM och Sörmlands museum jämförs med befintliga källor.
- Bengt A. Lundberg räknas som RAÄ även när arkivnamnet saknas.
- Nationalmuseet i Danmark räknas som överlappande källa för signa som redan har Runer KU-länkar. Detta är en uttrycklig urvalsregel, inte en teknisk identitetskontroll. DR 120, `File:Spentrupstenen 2 DMR.jpg`, källan `https://samlinger.natmus.dk/dmr/asset/6703`, exkluderades därför.
- Redan befintliga Commons-länkar utesluts.

Slutliga beslut: 1 134 samma arkiv, 1 samma fotograf och 2 redan befintliga länkar. Bland arkivmatchningarna finns RAÄ 1 098, SHM 17, Sörmlands museum 179 och Nationalmuseet/Runer KU 11. Dessa arkivtal överlappar och ska inte summeras. Samtliga 348 kandidater med Bengt A. Lundberg som fotograf exkluderades.

## Metod och verifiering

Kandidater matchades på exakt signumtext, alias följdes via `signatures.parent_id`, och aktuellt meta-ID hämtades via `meta_information`. De gamla meta-ID:na i juliunderlaget används inte för importkopplingen. Deduplicering sker per huvudsignum och avkodad Commons-filadress.

För den andra importen hämtades Commons revisionsinnehåll och imageinfo/extmetadata med API i grupper om 20. Samtliga 2 262 filer kunde bekräftas. Fotograf, kredit, källbeskrivning och befintliga länkar låg till grund för exkluderingarna. Fotografuppgifter saknas för vissa befintliga bilder, så kvarvarande kandidater är inte garanterat fria från allt överlapp. Licensen i importerad bildtext kommer från äldre metadata där den aktuella API-cachen saknar licensfältet. Exportresolvern hämtar aktuell licens vid export.

För den första importen verifierades 10 bildfiler. Commons bildserver svarade sedan 429; ytterligare bildhämtning stoppades. Resterande 73 importerades från det godkända äldre underlaget. Den andra importen verifierade aktuella filposter och originaladresser genom API, men laddade inte ned 1 240 bildfiler.

Båda importer bevarade samtliga befintliga bildrader och passerade SQLite `integrity_check`. Inga exkluderade kandidater importerades i den andra importen. Totalt 46 tester passerar för resolver, SHM-audit/komplettering och Commons-importens bildformat/metadatahantering.

## Commons-resolver

Implementerad i `rundatanet/runes/image_resolvers.py`, kopplad till exporten i `views.py` och till exportknappens källigenkänning i `rundatanet/templates/runes/index.html`. Tester finns i `rundatanet/tests/test_image_resolvers.py`. Applikationskoden ligger kvar på sina normala platser i projektet.

Resolvern stöder Commons `/wiki/File:` och `/w/index.php?title=File:`, normaliserar filnamn och hanterar omdirigeringar/omdöpningar. API:t ger aktuell originalbild, fotograf och licens. HTML rensas från attribution, uppladdaren antas inte vara fotograf och licens gissas inte. Originalbilder begränsas till Commons uppladdningsserver; thumbnails stöder även `thumb.wikimedia.org`.

Livekontroller gjordes för G 157, G 13 och U 877. En faktisk ZIP-export för G 13 kontrollerades med JPEG och attribution/licens.

## Innehåll

- `source-20260710/`: kopia av hela ursprungsmappen, inklusive 23 review-filer, 23 filtered-filer, äldre handoff och sök-/filterskript. Historiska skript och texter kan innehålla gamla absoluta sökvägar.
- `commons-coverage-20261024/`: täckningsrapporter för poäng 90–100 och under 90, före importerna.
- `commons-import-20261025/`: första importens förslag, införda rader, verifieringsstatus och sammanfattning.
- `commons-existing-source-review-20261025/`: alla kandidater, exkluderade, återstående och full käll-wikitext. Detta är den godkända ögonblicksbilden före andra importen.
- `commons-reviewed-import-20261025/`: andra importens 1 240 införda rader och verifiering.
- `scripts/`: de nya granskning-/importskripten och importtester, med sökvägar anpassade till denna mapp.
- `commons-api-metadata-20261025.tar.gz`: versionshanterad kopia av API-cachen. Packa upp i `commons-existing-source-review-20261025/` vid behov.
- `manifest.json`: SHA-256 och storlek för de versionshanterade underlagen såsom de lagras i Git (CSV-radslut normaliseras av Git).

Databassäkerhetskopior, uppackad API-cache och de 10 hämtade provbilderna finns kvar lokalt under samma mapp men ignoreras av Git. Projektets faktiska uppdaterade databas ingår i committen.

## Fortsatt arbete

Importerna är redan utförda. Kör inte importskripten för att lägga in samma underlag igen. Det andra skriptet vägrar vid befintlig lokal säkerhetskopia och hoppar över befintliga källadresser; det första kräver att de 62 målen fortfarande saknar bilder. Granskningsskriptet läser aktuell DB och skulle efter importen omklassificera nyligen införda länkar som befintliga; skriv därför inte över den godkända rapporten vid en framtida omgranskning.

För nya körningar: skapa en ny daterad rapportmapp och utgå från då aktuell DB. Respektera Commons 429/Retry-After. Under-90-grupperna återstår som möjliga framtida granskningsunderlag. Cacheversionen behöver ändras vid framtida DB-importer om webbläsaren visar äldre data.

Testkommando från projektroten:

```sh
.venv/bin/python -m pytest rundatanet/tests/test_image_resolvers.py utility/test_shm_audit.py utility/test_supplement_shm_images.py audit/commons-20261025/scripts/test_import_commons_missing_images.py -q
```
