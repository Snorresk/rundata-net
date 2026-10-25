# Blekinge museum: första resolverversion 2026-10-25

Resolver och klientfilter är implementerade. Ingen bilddata har ändrats.

- Källor: `https://blm.kulturhotell.se/objects/c32-<id>/`.
- Läser uttryckliga fullsize/original-länkar från objektsidan, på museets
  domän eller `cust.kulturhotell.se/c32/`.
- Väljer samma filnamn som den sparade bilden; ersätter inte vald bild med
  objektets första bild. Utan sparad bild krävs en enda entydig kandidat.
- Läser Creative Commons-länk och licensnamn. Fotograf lämnas tom i denna
  version; metadatafält för fotograf behöver verifieras när sajten öppnar.
- Gissar inte fullsize-adress från thumbnail. TLS-kontroll förblir aktiv.

## Livekontroll och begränsning

Startsidan visade meddelandet ”Tillfälligt stängt” om en förebyggande
nedstängning av SOFIE och berörda museers webbplatser. Objekt c32-38619 och
sparad thumbnail returnerade HTTP 404 vid undersökningshämtning utan
certifikatkontroll. Vanlig verifierad HTTPS misslyckades dessutom med
certifikatfel. Dessa undersökningsanrop ändrar inte appens TLS-beteende.

Lokalt API `/api/images/66656/resolve/` testades efter serveromstart och
returnerade ett kontrollerat hämtningsfel. **Ingen lyckad liveexport är
verifierad.** Parserns HTML-testdata är syntetiska och måste jämföras med
riktiga objektsidor efter återöppning. Denna version är därför preliminär.

## Tester

`test_blekinge_image_resolver.py` och `test_image_resolvers.py`: 39 passerade.
Täcker bildurval, metadata, otillåtna domäner, saknad bild, stängningssida,
hämtningsfel och ZIP-export med metadata.

## Signa att testa lokalt

- DR 356: 3 Blekinge-bilder, exempel bild-ID 66656.
- DR 360: 26 Blekinge-bilder.
- DR 363: 14 Blekinge-bilder.

Lokalsidan startades om på http://127.0.0.1:8000 med den nya koden.
Jämtland, SHFA och Norrbotten har inte påbörjats i denna omgång.
