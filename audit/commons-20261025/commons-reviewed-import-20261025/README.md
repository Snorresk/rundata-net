# Import av granskade Commons-länkar

På användarens begäran importerades de 1 240 kandidater som återstod efter exkludering av samma arkiv/fotograf, befintliga Commons-länkar samt Nationalmuseet i Danmark för signa med Runer KU-länk. Detta kompletterar den tidigare importen till 62 bildlösa signa.

1 240 nya bildrader för 883 signa. Samtliga 31 119 tidigare bildrader är oförändrade; totalt 32 359 efter importen. SQLite integrity_check: ok.

Källorna är retained-candidates.csv och aktuella, cachade Commons API-svar i ../commons-existing-source-review-20261025/. Originalfilens existens och URL bekräftades genom API; bildfilerna laddades inte ned. Sparade thumbnails används för oförändrade filnamn; omdirigerade/omdöpta filer använder aktuell originalbild. Fotograf hämtas från aktuella Commons-metadata och licens från den tidigare insamlade informationen när aktuell API-cache inte innehåller licensfältet. Exportresolvern hämtar aktuell licens vid export.

inserted.csv listar varje ny rad med signum och bildkälla. summary.json redovisar verifieringen. before-import.sqlite3 är lokal säkerhetskopia och ignoreras av Git. Ingen commit eller push ingår i denna import.
