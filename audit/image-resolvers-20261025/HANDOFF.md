# Handoff: bildresolvers och Export images

Status 25 oktober 2026, gren `codex/export-images`. Senaste kod-/databascommit: `7b5b84c` (pushad). Denna handoff sammanfattar det faktiska stödet i koden, inte planerade funktioner.

## Implementerade resolvers

| Webbplats | Status och arbetssätt | Bildrader i DB |
| --- | --- | ---: |
| RAÄ, `pub.raa.se` | Klar för dokumentations-URL med UUID. Hämtar JSON och väljer nedladdningsresurs med filmetadata och licens. Även UUID i sparad direktlänk kan användas. | 23 184 |
| Sörmlands museum, `sokisamlingar.sormlandsmuseum.se` | Klar för `/objects/c24-…/`. Använder sparad fullstor bild eller hittar den i sidan; hämtar licenslänk. Bildserver: `cust.kulturhotell.se`. | 923 |
| Digitalt museum, `digitaltmuseum.se`, `.no`, `.org` | Klar för numeriska objektadresser. Söker nedladdningslänk med `dimension=max`, därefter andra bildfält. Bildserver: `ems.dimu.org`. Endast `.se` finns bland nuvarande källrader. | 1 073 |
| Runer KU, `runer.ku.dk` | Klar när vald direktbild redan finns eller själva källadressen är en bild. Bevarar vald bild. Kräver inte att objektsidan skrapas. | 966 |
| Arild Hauge, `arild-hauge.com` / `www.arild-hauge.com` | Klar för sparade direktbilder inklusive JPEG, PNG och GIF. Bevarar vald bild; HTML-entiteter och URL-kodning hanteras. | 3 872 |
| SHM, `samlingar.shm.se` | Klar för objekt- och mediasidor med UUID. Kontrollerar att vald bild tillhör objektet och hämtar original, fotograf och licens från mediasidan. Bildserver: `media.samlingar.shm.se`. | 731 |
| Wikimedia Commons, `commons.wikimedia.org` | Klar för `/wiki/File:…` och `/w/index.php?title=File:…`. Imageinfo-API ger aktuell originalbild, fotograf och licens; omdirigeringar/omdöpningar stöds. | 1 355 |

Totalt känner stödfiltret igen 32 104 av bildtabellens 32 359 rader. Detta är källigenkänning, inte ett löfte att varje bild går att hämta live. Enskilda sidor kan saknas, ändra struktur eller begränsa hämtningar. Runer KU och Arild Hauge har inga inbyggda licens-/fotografantaganden; tomma uppgifter lämnas tomma.

## Återstår: webbplatser utan egen resolver

| Webbplats | Rader / sparad direktlänk | Kvarstående arbete |
| --- | ---: | --- |
| RAÄ Arkivsök, `arkivsok.raa.se` | 182 / 0 | Ingen särskild Arkivsök-resolver. Adressernas query kan innehålla en URL-kodad `pub.raa.se/dokumentation/UUID`; nuvarande UUID-regex avkodar inte queryn. Dessutom har samtliga 182 rader signumtext i `meta_id`, utan matchande `meta_information`-ID. Utred kopplingar och eventuella befintliga RAÄ-dubbletter före import/normalisering. |
| Blekinge museum, `blm.kulturhotell.se` | 43 / 43 | Saknar resolver. Undersök objektsidans fullstor bild och rättighetsmetadata. Befintlig Sörmlandsresolver är begränsad till dess domän och täcker inte alla Kulturhotell-sajter. |
| Jämtlands läns museum, `jlm.kulturhotell.se` | 19 / 19 | Saknar resolver. Undersök `/items/show/…`, originalbild och metadata. |
| SHFA, `shfa.dh.gu.se` | 10 / 10 | Saknar resolver. Undersök `/image/…`, originalbild och rättigheter. |
| Norrbottens museum, `samlingar.norrbottensmuseum.se` | 1 / 1 | Saknar resolver. Undersök `/web/object/…`, originalbild och metadata. |

Dessa fem domäner motsvarar 255 råa bildrader, inklusive de 182 äldre Arkivsök-raderna med ogiltig meta-koppling. Inventeringen är sparad i `source-inventory.csv`. Antalen avser bildrader, inte unika signa eller fotografier. Ingen generell resolver för valfri direktbild finns.

Nationalmuseet i Danmark (`samlinger.natmus.dk`) har ingen egen resolver, men förekommer inte som källdomän i dagens bildtabell. Commons-bilder därifrån använder Commons-resolvern om de importeras. Vi har uttryckligen exkluderat sådana Commons-förslag när samma signum redan har Runer KU-länk. Alvin har inte heller någon bildresolver i denna modul; dokument-/PDF-länkar i andra delar av DB ingår inte i denna inventering.

En rimlig nästa ordning är att först reda ut Arkivsöks kopplingar och överlapp med befintliga RAÄ-bilder, sedan Blekinge, Jämtland, SHFA och Norrbotten utifrån antal nuvarande bildrader. Detta är ett förslag, inget beslutat eller påbörjat implementeringsarbete.

## Kod och exportflöde

- `rundatanet/runes/image_resolvers.py`: `ResolvedImage`, `resolve_image_link()`, `is_supported_image_source()` och de sju källspecifika resolverfunktionerna.
- `rundatanet/runes/views.py`: upplösning och ZIP-export; `MAX_IMAGE_EXPORT_FILES = 750`. Exporten skapar `images/`, `metadata.csv`, `skipped-images.csv` och `README.txt`. Fel för en bild redovisas i skipped-filen. Om ingen bild kan hämtas returneras HTTP 422.
- `rundatanet/runes/urls.py`: `api/images/<image_id>/resolve/` och `api/images/export-raa-zip/`. Exportens endpoint-/funktionsnamn innehåller fortfarande RAÄ av historiska skäl, men stöder alla sju källor.
- `rundatanet/templates/runes/index.html`: väljer exportkandidater i klienten. Uppdatera även detta filter när ny resolver läggs till.
- `rundatanet/tests/test_image_resolvers.py`: tester av igenkänning, metadata, urval av bild, felhantering och ZIP-export.

Resolverns resultat innehåller provider, källadress, nedladdningsadress, thumbnail, filnamn, MIME, storlek när känd, licens och fotograf när tillgänglig. Saknade rättighetsuppgifter ska inte gissas.

## Relaterat arbete och underlag

- `audit/commons-20261025/HANDOFF.md`: hela Commons-arbetet, poäng, urval, exkluderingar och två importer. Totalt 1 323 nya Commons-länkar: 83 till 62 tidigare bildlösa signa och 1 240 till 883 andra signa.
- `audit/shm-20261021/`: ombyggnad av SHM-länkar till verifierade signum-/objektkopplingar.
- `audit/shm-supplement-20261024/`: komplettering av befintligt SHM-länkade signa upp till 15 bilder per signum. Nu 731 SHM-rader; U Fv1969;210 har 8. Inga nya signa söktes i den kompletteringen.
- RAÄ-bildtexterna har enhetligt namn: `Image from RAÄ archives`. Det innebär inte att alla RAÄ-URL-varianter har egen resolver.

Viktiga commits: `7f7d823` (Runer KU, Arild Hauge och RAÄ-bildtexter), `953ad88` (SHM-ombyggnad), `aab5173` (SHM-resolver och komplettering), `7b5b84c` (Commons-resolver, importer och Commons-handoff). RAÄ, Sörmlands museum och Digitalt museum fanns redan som resolverstöd före de senaste kompletteringarna.

## Verifiering och nästa implementation

Senaste samlade testkörningen passerade med 46 tester:

```sh
.venv/bin/python -m pytest rundatanet/tests/test_image_resolvers.py utility/test_shm_audit.py utility/test_supplement_shm_images.py audit/commons-20261025/scripts/test_import_commons_missing_images.py -q
```

Liveverifiering finns dokumenterad för Commons G 157, G 13 och U 877, inklusive en faktisk ZIP för G 13. Det är inte en fullständig livekontroll av samtliga bildrader. Commons 429/Retry-After ska respekteras; metadataexistens och nedladdade bildbytes är olika verifieringsnivåer.

Vid ny resolver: undersök aktuella exempeladresser, bevara användarens valda bild när objektet har flera, hämta original och tillgänglig attribution/licens, lägg till dispatch och klientfilter, och testa representativa fel samt ZIP-export. Bekräfta att länkarna avser rätt signum innan DB kompletteras.

Inventeringen och denna handoff skapades utan databasändringar eller nya nätverkskontroller.

## Uppdatering efter fortsatt arbete 2026-10-25

Den ursprungliga statusen och source-inventory.csv ovan är en historisk
ögonblicksbild. Följande är genomfört därefter:

- 182 felkopplade Arkivsök-dubbletter raderade efter användarens godkännande.
  Varje UUID fanns redan som giltig RAÄ-bild för samma signum. Nu 32 177
  bildrader; giltiga kopplingar oförändrade. Se ARKIVSOK-RESULT.md och JSON-underlag.
- Blekinge och Jämtland har preliminära resolvers och klientfilter.
  Båda källorna visar tillfällig SOFIE-nedstängning och bildlänkar ger 404.
  Parserdata är syntetiska; riktig HTML, fotografmetadata och lyckad
  liveexport återstår. Se BLEKINGE-RESULT.md och JAMTLAND-RESULT.md.
- SHFA är implementerad via aktuellt API. Alla 10 original hämtade live;
  faktisk lokal ZIP innehöll 10 bilder och 0 överhoppade. Fotograf och
  CC BY 4.0 medföljer. Sparade gamla bildadresser ändras inte i DB.
  Se SHFA-RESULT.md och liveunderlag.
- Samlad resolver-/exporttestning: 55 passerade.
- Norrbottens museum återstår (1 bildrad). Nästa källa enligt användarens
  önskemål att implementera och testa en i taget.

Fullständig databasbackup finns lokalt i auditmappen men ingår inte i Git.
