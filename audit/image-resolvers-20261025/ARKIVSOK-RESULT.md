# Arkivsök: jämförelse 2026-10-25

Databasen lästes utan ändringar. Samtliga 182 bildrader från
`arkivsok.raa.se` har signumtext i `meta_id` i stället för ett giltigt
`meta_information.id`.

För varje rad avkodades queryparametern `uri` med `urllib.parse.parse_qs`.
RAÄ-dokumentets UUID jämfördes sedan med befintliga bildrader. Signumtexten
matchades exakt mot `signatures.signature_text`, kopplad till
`meta_information` genom `signature_id`.

Resultat: **182 av 182 är dubbletter av ett befintligt RAÄ-dokument för
samma signum.** Inga nya bilder behöver importeras eller kopplas om för att
göra dessa dokument tillgängliga genom den befintliga RAÄ-exporten.
Detta är en databasjämförelse, inte en livekontroll av dokumentens åtkomlighet.

Radvis underlag finns i `arkivsok-audit.json`: gammalt bild-ID, signum,
matchande meta-ID, dokument-UUID och befintliga bildrader med deras meta-ID.

Ingen databasrensning eller kodändring har gjorts. De felkopplade äldre
raderna finns kvar; eventuell borttagning bör göras som en separat,
säkerhetskopierad databasåtgärd.

## Fortsatt arbete

Blekinge, Jämtland, SHFA och Norrbotten återstår, totalt 73 bildrader.
Ett liveförsök mot Blekinges objektsida
`https://blm.kulturhotell.se/objects/c32-38619/` misslyckades med TLS-felet
`unable to get local issuer certificate`, även med venvs certifi och curl
utanför sandboxen. Webbverktyget kunde inte heller öppna de fyra
exempelobjektsidorna. Detta fastställer inte att webbplatserna är nere.
Originalbild, bildurval och rättighetsmetadata är ännu inte verifierade.

## Genomförd rensning 2026-10-25

Efter användarens godkännande raderades de 182 Arkivsök-raderna i en
transaktion. Varje rad verifierades på nytt som felkopplad och med en
befintlig RAÄ-bild med samma UUID för samma signum innan radering.

- Fullständig SQLite-backup: `runes.before-arkivsok-delete-20261025-140239.sqlite3`.
- Rader och verifieringsunderlag: `arkivsok-deleted-rows-20261025-140239.json`.
- Antal bildrader: 32 359 → 32 177.
- Antal giltigt kopplade bildrader: oförändrat, 32 177.
- `PRAGMA integrity_check`: `ok`.

Tidigare status ovan och i HANDOFF.md/source-inventory.csv beskriver läget
före rensningen. Ingen resolverkod ändrades.
