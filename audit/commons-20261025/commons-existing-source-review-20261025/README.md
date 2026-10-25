# Commons: granskning av befintliga bildkällor

Omfattar Commons-kandidater med 90–100 poäng för de 1 254 primära signa som redan hade bildlänkar före importen till 62 tidigare bildlösa signa. Totalt 2 377 signum/fil-par, 2 262 unika Commons-filer. Inga bildlänkar ändras av granskningen.

## Urvalsregel

På användarens uttryckliga önskemål räcker samma arkiv eller samma fotograf på samma signum för att exkludera ett förslag. Bengt A. Lundberg räknas som RAÄ även om arkivnamnet saknas. Nationalmuseet i Danmark (natmus.dk, National Museum of Denmark) grupperas enligt användarens önskemål med befintliga Runer KU-länkar (runer.ku.dk); sådana förslag exkluderas för samma signum. Detta är en importregel och kräver inte identiska fotografier. Arkiv identifieras i Commons beskrivning, kredit, fotograf och filnamn; befintliga arkiv identifieras genom databasens länk och bildtext. Fotograf jämförs med befintlig bildtext, sparade SHM-fotografuppgifter och tillgängliga Commons-metadata för befintliga Commons-länkar.

## Resultatfiler

- `excluded.csv`: förslag att utesluta, med kriterium och matchande befintliga länkar.
- `retained-candidates.csv`: förslag utan påvisad match enligt regeln; inte ett bevis på att alla fotografer skiljer sig. Befintliga bilder saknar ibland fotografuppgift.
- `needs-review.csv`: filer som inte kunde bekräftas genom Commons API.
- `all-candidates.csv`: samtliga kandidater med källbeskrivningens wikitext.
- `summary.json`: antal per beslut och arkiv.

Commons API hämtas med revisionsinnehåll och imageinfo/extmetadata, i grupper om 20 filer. API-svaren sparas i ignorerad cache. Inga bildfiler laddas ned. Rapporterna produceras med `../scripts/audit_commons_existing_sources.py`.
