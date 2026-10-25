# Commons-förslag och bildtäckning i DB, 24 oktober 2026

Underlag: de 23 filtrerade Commons-filerna i `/Users/sost7972/Desktop/Rundata  test/Rundata Common links`, från arbetet den 10 juli 2026. Enbart kandidatposter med poäng 90–100 ingår.

Kandidatens signum har slagits upp med exakt text i dagens `signatures`-tabell. Alias har följts genom `parent_id` till huvudsignum och därefter till dess aktuella post i `meta_information`. Äldre meta-ID från kandidatfilerna har inte använts för kopplingen. Alla kandidatetiketter kunde matchas.

Bildtäckningen räknar samtliga befintliga poster i `runes_imagelink` för det aktuella meta-ID:t, oavsett bildkälla och oavsett om direktlänk finns. Noll betyder alltså inga bildposter alls för signumet, inte enbart avsaknad av Commons-bilder. Äldre poster med text i meta_id sammanfaller inte med något av de identifierade 62 tomma huvudsignumen.

Ett huvudsignum med både 100-poängs- och 90–99-poängsförslag redovisas i 100-gruppen för att inte räknas två gånger. Kandidatbilder har deduplicerats per huvudsignum och avkodad Commons-filadress; högsta poäng behålls när samma bild förekommer via flera alias. Antalet bilder är inte antalet globalt unika fotografier.

- `alla-signum-90-100.md` / `.csv`: komplett lista med ett huvudsignum per rad.
- `signum-utan-bildlankar.md` / `.csv`: de huvudsignum som helt saknar bildposter i dagens DB.
- `commons-kandidater-90-100.csv`: kandidatbilder med matchningsskäl, fotograf och licens enligt det äldre underlaget.
- `summary.json`: exakta totalsiffror.

Ingen databasändring eller import har utförts. Commons-sidorna har inte verifierats på nytt och poängen innebär inte manuell bildgranskning.

## Komplettering: förslag under 90 poäng

Samma metod har tillämpats på de 5 507 filtrerade kandidatposterna under 90 poäng. De motsvarar 1 060 huvudsignum, varav 64 saknar bildposter i aktuell DB. Av dessa huvudsignum har 32 även förslag med 90–100 poäng. Bland de 64 utan bilder finns två även i det högre poängintervallet.

1 028 huvudsignum har enbart förslag under 90; av dem saknar 62 bildposter. Grupperna räknas efter huvudsignum, vilket gör att olika alias kan ge träffar i båda poängintervallen även efter det ursprungliga filtret per signumetikett.

- `alla-signum-under-90.md` / `.csv`: komplett lista över 1 060 huvudsignum.
- `signum-under-90-utan-bildlankar.md` / `.csv`: samtliga 64 utan bildposter.
- `enbart-under-90-utan-bildlankar.md` / `.csv`: de 62 utan bilder som saknar högre poängsatta Commons-förslag.
- `commons-kandidater-under-90.csv`: kandidatbilder och matchningsskäl.
- `summary-under-90.json`: totalsiffror.

Ingen databasändring eller import har utförts.
