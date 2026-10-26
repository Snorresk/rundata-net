# Jämtlands läns museum: preliminär resolver 2026-10-25

Källfilter och resolver för `jlm.kulturhotell.se/items/show/<id>` är
inkopplade i server och klient. Parser och urval delas med den preliminära
Blekinge-resolvern, med separata tillåtna bilddomäner.

Resolvern läser uttryckliga `/files/fullsize/`- eller `/files/original/`-
länkar på museets egen domän. Den bevarar vald bild genom matchning mot
sparat filnamn och väljer aldrig en annan bild om matchningen saknas.
Utan sparad bild krävs en entydig kandidat. Licenslänk läses när tillgänglig;
fotograf lämnas tom tills verkliga metadatafält kan undersökas. Inga
bildadresser eller rättigheter gissas. Appens TLS-kontroll är oförändrad.

## Livekontroll

Startsidan visade samma SOFIE-meddelande om tillfällig stängning som Blekinge.
Objektsidan `/items/show/272754` och den sparade thumbnailen returnerade
404 vid undersökningsanrop med curl utan certifikatkontroll. Den lokala
resolver-endpointen `/api/images/58741/resolve/` testades efter omstart och
returnerade ett kontrollerat hämtningsfel. Ingen lyckad liveexport har
verifierats. Parserfixture är syntetisk; faktisk HTML, originalstorlek och
attribution måste verifieras när sajten öppnar igen.

## Testsignum

Samtliga 19 befintliga bildlänkar hör till **J RS1928;66**.
Exempel: bild-ID 58741, objekt 272754. Sök på detta signum lokalt och välj
bilder med Jämtlands museum som källa. För närvarande förväntas hämtningsfel.

Lokalsidan startades om på http://127.0.0.1:8000. Ingen databasändring har
gjorts i detta steg. SHFA och Norrbottens museum återstår.

Verifiering: `test_jamtland_image_resolver.py`, `test_blekinge_image_resolver.py`
och `test_image_resolvers.py` täcker bl.a. urval mellan flera bilder,
fullsize/original, licens, saknad attribution, fel domän, stängningssida,
hämtningsfel och ZIP-export. Blekinges tester körs också eftersom parsern delas.
