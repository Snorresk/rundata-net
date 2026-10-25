# Granskning och återuppbyggnad av SHM-länkar, 2026-10-21

Användaren bad först om granskning och komplettering, och beslutade därefter att samtliga gamla SHM-källänkar skulle tas bort och ersättas med säkra kopplingar.

## Underlag och urval

- Befintliga SHM-källänkar har följts från mediesidor till länkade föremålsposter. Föremålens metadata har jämförts med vårt signum och uttryckligen registrerade alternativa signum.
- Före återuppbyggnaden fanns 714 SHM-källänkar och tre ytterligare RAÄ-källänkar med miniatyrer från SHM. De tre RAÄ-källänkarna behandlas separat: två behålls med verifierade miniatyrer från RAÄ; en bildpost tas bort eftersom RAÄ inte publicerar någon bildresurs och den gamla miniatyren pekade till SHM.
- De 714 källänkarna fördelades efter metadatagranskning på 425 med exakt signumstöd, 92 med andra signum, 193 utan signumstöd och fyra med exakt signum som titel. Det är granskningsklasser, inte ett påstående att varje länk utan signum var felaktig.
- En ny sökning omfattade runsten, runristning, runbleck, runinskrift, runben, runor, runhäll, runfragment samt brakteat i kombination med runinskrift eller runor. Alla resultatsidor för dessa sökningar hämtades, totalt 584 unika föremål. Detta är en avgränsad sökning, inte en garanti om att alla relevanta föremål i hela SHM har hittats.
- Även föremål som identifierades vid granskningen av gamla länkar ingick som kandidater. Gamla kopplingar importerades aldrig utan en ny identitetskontroll.

## Krav för en ny koppling

1. SHM:s fält `Runsignum` måste exakt motsvara vårt signum eller ett registrerat alternativ. Endast skillnader i skiftläge, Unicode-normalisering och blanksteg normaliseras. Inga ungefärliga nummer-, orts- eller strängträffar godtas.
2. Om signumfält saknas kan en titel som i sin helhet är exakt samma signum användas. En titel får inte motsäga ett strukturerat signumfält. Tvetydiga signum som tillhör flera olika huvudposter godtas inte. Testposter utesluts även om signum råkar matcha.
3. Föremålssidan måste ange en bild hos `media.samlingar.shm.se`. Bilden hämtas och svaret kontrolleras som bilddata; HTML-felsidor godtas inte.
4. En ny källänk skapas per föremål och signum, med en verifierad miniatyr som ingång till föremålets bildgalleri. Flera fotografier av samma föremål blir inte flera identiska föremålslänkar.

## Exempel på tidigare felkopplingar

- Öl 37, Lerkaka, hade en bild av ett föremål från Resmo med signum Öl Fv1911;274C.
- Sm 32 och Sm 33, runstenar, hade bilder av en kam med signum Sm ATA344/37.
- En vävkniv med signum Vg 279 förekom under 51 andra Vg-signum.

## Slutresultat

- 714 gamla SHM-källänkar ersattes med 211 kontrollerade länkar till 209 föremål för 180 signum.
- 209 nya kopplingar stöds av strukturerat runsignum; två av exakt signum som titel (Sö 117, två delar av samma monument).
- Fem föremålskopplingar är nya jämfört med tidigare säkert kopplade föremål: två för Öl Köping74 och tre för U 6.
- Samtliga 211 miniatyrer har hämtats och verifierats som bilddata.
- 37 ytterligare exakta metadataträffar infördes inte: en var en testpost och 36 saknade bild i den kontrollerade bildvägen.
- Två blandade RAÄ/SHM-poster har fått RAÄ:s egna verifierade miniatyrer. En tredje togs bort då dokumentet saknar publicerade bildresurser.
- Oberoende jämförelse mot fullbackupen: totalt 715 borttagna rader, 211 tillagda rader och två ändrade miniatyrfält. Alla andra bildrader är identiska med backupen. Databasintegritet: `ok`.
- Fem tester för granskningsreglerna och 15 befintliga resolvertester passerar.

## Rapporter och återställning

- `before-reset-all-shm-links.csv`: samtliga gamla poster med alla bildfält, ursprungliga ID och signum, inklusive de tre blandade RAÄ-posterna.
- `existing-links.csv`: granskningsunderlag för de 714 SHM-källänkarna, med föremålsadresser och metadata.
- `searches.csv` och `discovery.csv`: sökningarnas omfattning och exakta signumträffar.
- `rebuild-proposed.csv`: nya kopplingar och bildkontrollens resultat.
- `rebuild-excluded.csv`: granskade föremål som inte klarade identitets- eller bildkraven.
- `rebuild-removed.csv` och `rebuild-inserted.csv`: exakt vilka rader som togs bort respektive lades till.
- `mixed-raa-thumbnail-corrections.csv`: RAÄ-källänkar vars SHM-miniatyrer ersatts med miniatyrer ur RAÄ:s egen dokumentmetadata. Två källänkar behålls; en bildpost utan publicerad RAÄ-bildresurs tas bort och redovisas i samma fil.
- `reset-summary.json`: slutliga antal och integritetskontroller.
- Fullständig SQLite-backup: `SHM/backups/runes-before-shm-reset-20261021.sqlite3`.
- Hämtade källsidor och kontrollbilder sparas lokalt i `pages/` och `images/`, vilka inte versionshanteras.

Återuppbyggnaden utförs i en databastransaktion efter kontroll mot återställningsfilen. Övriga bildposter jämförs före och efter för att säkerställa att de inte har ändrats. Ändrade RAÄ-miniatyrer redovisas separat. Databasens `PRAGMA integrity_check` måste returnera `ok`.

Verktyg: `utility/audit_shm_links.py` hämtar och granskar metadata utan databasändringar. `utility/rebuild_verified_shm_links.py` förbereder säkra kopplingar; `--apply` utför den dokumenterade engångsåteruppbyggnaden. Skripten använder daterade rapporter och cache och ska inte köras som en generell, odaterad uppdatering.
