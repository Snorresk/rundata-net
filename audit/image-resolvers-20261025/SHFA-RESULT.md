# SHFA-resolver 2026-10-25

Implementerad och liveverifierad för samtliga tio befintliga SHFA-bildrader.

## Upplösning

- Källadress: `https://shfa.dh.gu.se/image/<id>`.
- Metadata: `https://shfa.dh.gu.se/api/image/?id=<id>&depth=1`.
- Använder API-fältet `file`, precis som SHFA:s nedladdningsknapp.
- De sparade adresserna under `data.dh.gu.se/diana/static/shfa/original/`
  gav 404. Aktuella API-adresser ligger under
  `data.dh.gu.se/shfa/static/shfa/original/` och gick att hämta.
- Kontrollerar exakt ett API-resultat, rätt bild-ID och published=true.
- Sparad vald bild måste ha samma filnamn på tillåten SHFA-originalsökväg.
  Inget annat foto väljs när matchning saknas. Ingen generell domänomskrivning.
- Fotograf läses från `people`, med `author` som reserv. Flera namn behålls.
- Licens CC BY 4.0 enligt SHFA:s officiella om-sida. Policyn verifierades i
  den publika klientkoden `/assets/index-BZhdtxTC.js`, som används av
  `https://shfa.dh.gu.se/about`. Ingen fotograf eller licens härleds ur
  filnamnet eller museitillhörigheten.
- Klientens exportfilter och serverns dispatch/stödfilter är uppdaterade.
- Ingen databasändring. Sparade förhandsvisningslänkar uppdateras inte;
  exporten hämtar den aktuella adressen dynamiskt.

## Verifiering

`test_shfa_image_resolver.py`, `test_jamtland_image_resolver.py`,
`test_blekinge_image_resolver.py`, `test_image_resolvers.py`: **55 passerade**.
SHFA-fixturen `rundatanet/tests/fixtures/shfa/image-109439.json` är hämtad
från det riktiga API:t. Tester täcker API-validering, bibehållen vald bild,
aktuella adresser, metadata, saknad fotograf, hämtningsfel och ZIP-export.
`git diff --check` passerade.

Alla tio original hämtades och identifierades som JPEG. Radvis underlag:
`shfa-live-results.json`.

Lokalsidan startades om. `/api/images/6904/resolve/` gav ok=true. En faktisk
POST till `/api/images/export-raa-zip/` med alla tio bild-ID:n gav en ZIP med
10 bilder, 10 metadata-rader och 0 överhoppade bilder. Alla bilder hade
JPEG-signatur, fotograf och CC BY 4.0 i metadata. ZIP-integritetskontrollen
passerade. Sammanfattning: `shfa-zip-verification.json`; ZIP i
`/tmp/shfa-live-export.zip` (tillfälligt testunderlag).

## Signa för test

- **Sö 101**: 3 bilder (ID 6904–6906).
- **U 875**: 2 bilder (ID 22636–22637).
- **Bo NIYR5;224**: 5 bilder (ID 58870–58874).

Sök signum på http://127.0.0.1:8000 och välj SHFA-bilder för export.
Norrbottens museum återstår. Blekinge och Jämtland är fortfarande preliminära
på grund av källornas nedstängning.
