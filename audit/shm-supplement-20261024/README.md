# Komplettering av SHM-bilder, 24 oktober 2026

Användaren bad om fler bilder endast för de signum som redan har SHM-länkar, med högst 15 SHM-bildposter per signum.

## Avgränsning och kontroll

Utgångspunkten är 211 befintliga bildposter för 180 signum, kopplade till 209 unika och tidigare godkända SHM-föremål. Inga nya signum eller nya föremålsadresser söks fram. Föremålssidorna hämtas på nytt och måste fortfarande styrka signum eller ett registrerat alternativ enligt samma strikta identitetsregler som vid återuppbyggnaden den 21 oktober.

Bildgallerierna läses i sidornas ordning. En ny bild måste finnas både som mediepost och som en bildresurs i det godkända föremålets galleri. Dess miniatyr hämtas och svaret kontrolleras som bilddata. Bara därefter tilldelas bilden en plats inom gränsen på 15. Misslyckade hämtningar förbrukar ingen plats.

Samma medie-ID läggs inte till på nytt under samma signum, även om det återkommer på flera föremålssidor. Alla befintliga bildposter bevaras. Det innebär att även de fyra redan befintliga extra rader som upprepar ett fotografi räknas in i gränsen; kompletteringen utför ingen gallring av äldre poster.

Nya rader behåller föremålet som källänk och har en egen direktlänk till det specifika fotografiets miniatyr. SHM-resolvern använder bildens medie-ID för att välja samma fotografi i originalstorlek och hämta dess licens och fotograf.

Gränsen på 15 gäller lagrade SHM-bildposter. Webbplatsens separata gränser för antalet synliga galleribilder och automatiskt valda bilder vid ZIP-export ändras inte av denna datakomplettering.

## Underlag

- `existing-before.csv`: samtliga ursprungliga SHM-bildposter och deras signum.
- `object-galleries.csv`: färsk signumkontroll och antal medieposter per godkänt föremål.
- `proposed-additions.csv`: verifierade kompletteringar, med medie-ID, mediesida och föremålsadress.
- `per-signum.csv`: antal bildposter före och efter samt antal tillägg för vart och ett av de 180 signumen.
- `errors.csv`: hämtningar eller kontroller som inte kunde godkännas.
- `inserted.csv`: tillagda databasrader med nya bild-ID.
- `all-shm-image-links.csv`: samtliga SHM-bildlänkar efter kompletteringen, med bild-ID och markering av nya poster.
- `summary.json`: slutliga antal och integritetskontroller.
- Fullbackup: `SHM/backups/runes-before-shm-supplement-20261024.sqlite3`.
- Hämtade källsidor och miniatyrer finns lokalt i `pages/` och `images/`, vilka inte versionshanteras.

Ändringarna utförs i en transaktion. Alla befintliga bildrader jämförs före och efter och ska vara oförändrade. Inga nya huvudposter får tillkomma i SHM-urvalet och ingen får ha fler än 15 SHM-bildposter. SQLite `integrity_check` ska ge `ok`.

Verktyg: `utility/supplement_shm_images.py` förbereder underlag; `--apply` lägger till de verifierade raderna. Verktyget använder daterade underlag och är avsett för denna avgränsade engångskomplettering.

## Slutresultat

- 520 nya bildposter har lagts till för 129 av de 180 befintliga signumen.
- Totalt finns nu 731 SHM-bildposter. Ingen har fler än 15 per signum; sex signum når gränsen.
- U Fv1969;210 har kompletterats från en till åtta bilder.
- Samtliga 211 befintliga kopplingar bekräftades på nytt i SHM:s metadata. Alla tidigare bildrader i databasen är oförändrade vid jämförelse mot fullbackupen.
- Två ytterligare medieposter för U Fv1912;8 gav PDF-data och importerades inte som bilder. De är redovisade i `errors.csv`.
- Alla nya medie-ID har även kontrollerats mot SHM-resolverns parsning av föremålssidorna.
- SQLite-integritet: `ok`.

Rapporterna kan återskapas med `--finish-reports` utan att tilläggen körs igen. Rapporteringen filtrerar SHM-källor innan den tolkar deras metadata-ID; äldre orelaterade bildrader med textvärden i `meta_id` lämnas orörda.
