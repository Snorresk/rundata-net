#!/usr/bin/env python3
"""Fill draft English translations for image-caption rows in the audit CSV."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


DEFAULT_AUDIT_CSV = Path("translation_audit/high_value_metadata_image_captions.csv")

EXACT_TRANSLATIONS = {
    "Bilde vist i innskriftsseksjonen (ingen egen bildetekst oppgitt).": (
        "Image shown in the inscription section (no separate caption provided)."
    ),
    "Bilder og tekst fra Unimus-portalen om gjenstanden. ⇗": (
        "Images and text from the Unimus portal about the object. ⇗"
    ),
    "Alle bilder og tegninger er fra Norges Indskrifter med de ældre Runer, A.W. Brøhhers Bogtrykkeri, Christiania 1891-1924": (
        "All images and drawings are from Norges Indskrifter med de ældre Runer, A.W. Brøhhers Bogtrykkeri, Christiania 1891-1924"
    ),
    "Foto fra Norges Indskrifter med de ældre Runer, A.W. Brøhhers Bogtrykkeri, Christiania 1891-1924. Public Domain": (
        "Photo from Norges Indskrifter med de ældre Runer, A.W. Brøhhers Bogtrykkeri, Christiania 1891-1924. Public Domain"
    ),
    "Tegning fra Ole Worm. Public Domain": "Drawing from Ole Worm. Public Domain",
    "Tegning fra Nytt om runer nr. 8, 1993. CC-BY-SA 4.0": (
        "Drawing from Nytt om runer no. 8, 1993. CC-BY-SA 4.0"
    ),
    "Tegning Erik Moltkes rekonstrusjon av runeteksten": (
        "Drawing of Erik Moltke's reconstruction of the runic text"
    ),
    "Wegners tegning fra 1639 av innskriften N 261 Hauske stavkirke": (
        "Wegner's drawing from 1639 of the inscription N 261 Hauske stave church"
    ),
    "Wilhelm F.K. Christies tegning av dørringen fra Tønjum stavkirke. Public Domain": (
        "Wilhelm F. K. Christie's drawing of the door ring from Tønjum stave church. Public Domain"
    ),
    "Bearbeidet bilde av runeinnskriften. Tegning: K. Jonas Nordby, UiO. CC-BY-SA 4.0": (
        "Edited image of the runic inscription. Drawing: K. Jonas Nordby, UiO. CC-BY-SA 4.0"
    ),
    "Bilde av av trestykkets A-side. Foto: Trond Sverre Kristiansen, Vitenskapsmuseet, NTNU. CC-BY-SA 4.0": (
        "Image of side A of the piece of wood. Photo: Trond Sverre Kristiansen, NTNU University Museum. CC-BY-SA 4.0"
    ),
    "Bilde av av trestykkets B-side. Foto: Trond Sverre Kristiansen, Vitenskapsmuseet, NTNU. CC-BY-SA 4.0": (
        "Image of side B of the piece of wood. Photo: Trond Sverre Kristiansen, NTNU University Museum. CC-BY-SA 4.0"
    ),
    "Bilde av plasseringen av runeinnskriften på døpefonten. Foto: Ragnar Kjellberg, Kulturhistorisk Museum. CC-BY-SA 4.0": (
        "Image showing the location of the runic inscription on the baptismal font. Photo: Ragnar Kjellberg, Museum of Cultural History. CC-BY-SA 4.0"
    ),
    "Detaljbilde av vokstavlen. Foto: Eirik Irgens Johnsen, Kulturhistorisk museum. CC-BY-SA 4.0": (
        "Detail image of the wax tablet. Photo: Eirik Irgens Johnsen, Museum of Cultural History. CC-BY-SA 4.0"
    ),
    "Detaljebilde av nålen. Foto: Trond Sverre Kristiansen, Vitenskapsmuseet, NTNU. CC-BY-SA 4.0": (
        "Detail image of the needle. Photo: Trond Sverre Kristiansen, NTNU University Museum. CC-BY-SA 4.0"
    ),
    "Detljebilde av nålens A-side. Foto: Trond Sverre Kristiansen, Vitenskapsmuseet, NTNU. CC-BY-SA 4.0": (
        "Detail image of side A of the needle. Photo: Trond Sverre Kristiansen, NTNU University Museum. CC-BY-SA 4.0"
    ),
    "Detljebilde av nålens B-side. Foto: Trond Sverre Kristiansen, Vitenskapsmuseet, NTNU. CC-BY-SA 4.0": (
        "Detail image of side B of the needle. Photo: Trond Sverre Kristiansen, NTNU University Museum. CC-BY-SA 4.0"
    ),
    "Fargebilde av A-innskriften. Foto: Mårten Teigen, Kulturhistorisk Museum. CC-BY-SA 4.0": (
        "Color image of the A inscription. Photo: Mårten Teigen, Museum of Cultural History. CC-BY-SA 4.0"
    ),
    "Fargebilde av B-innskriften. Foto: Mårten Teigen, Kulturhistorisk Museum. CC-BY-SA 4.0": (
        "Color image of the B inscription. Photo: Mårten Teigen, Museum of Cultural History. CC-BY-SA 4.0"
    ),
    "Fargebilde av C-innskriften. Foto: Mårten Teigen, Kulturhistorisk Museum. CC-BY-SA 4.0": (
        "Color image of the C inscription. Photo: Mårten Teigen, Museum of Cultural History. CC-BY-SA 4.0"
    ),
    "Innskriften er datert til 1200-1300-tallet og er ristet på en dokumentskrin av tre. Skrinet har på bunden to runeinnskrifter, N 545 er i bildet til venstre og N 546 er bildet til høyre": (
        "The inscription is dated to the 13th-14th century and is carved on a wooden document chest. The chest has two runic inscriptions on the bottom; N 545 is in the image on the left and N 546 is in the image on the right."
    ),
    "Tegning: Ukjent, Trøndelag Folkemuseum. Tegning av døren og runeinnskriftens plassering. CC-BY-SA 4.0": (
        "Drawing: Unknown, Trøndelag Folkemuseum. Drawing of the door and the location of the runic inscription. CC-BY-SA 4.0"
    ),
    "Oddernessteinens antatte opprinnelige plassering. Tegning: Ukjent. CC-BY-SA 4.0": (
        "The Oddernes stone's presumed original location. Drawing: Unknown. CC-BY-SA 4.0"
    ),
    "Bilde av blyamuletten. Foto: Olav Heggø, Kulturhistorisk museum. CC-BY-SA 4.0": (
        "Image of the lead amulet. Photo: Olav Heggø, Museum of Cultural History. CC-BY-SA 4.0"
    ),
    "Bilde av blyamuletten. Foto: Eirik IrgensLisens Johnsen, Kulturhistorisk museum. CC-BY-SA 4.0": (
        "Image of the lead amulet. Photo: Eirik Irgens Johnsen, Museum of Cultural History. CC-BY-SA 4.0"
    ),
    "Bilde av døpefonten. Foto: Ragnar Kjellberg, Kulturhistorisk Museum. CC-BY-SA 4.0": (
        "Image of the baptismal font. Photo: Ragnar Kjellberg, Museum of Cultural History. CC-BY-SA 4.0"
    ),
    "Døpefont fra Os stavkirke. Tegning: Olav Espevoll. CC-BY-SA 4.0": (
        "Baptismal font from Os stave church. Drawing: Olav Espevoll. CC-BY-SA 4.0"
    ),
    "Etter Peder Alfssøns akvarell fra 1627 av alterduken. Foto: steinhuset.org. CC-BY-SA 4.0": (
        "After Peder Alfssøn's watercolor from 1627 of the altar cloth. Photo: steinhuset.org. CC-BY-SA 4.0"
    ),
    "Foto: steinhuset.org. CC-BY-SA 4.0. Etter Peder Alfssøns akvarell fra 1627 av alterduken": (
        "Photo: steinhuset.org. CC-BY-SA 4.0. After Peder Alfssøn's watercolor from 1627 of the altar cloth"
    ),
    "Kiste av eik fra 1200-tallet med runeinnskrift. Foto: Kulturhistorisk museum, Oslo.CC-BY-SA 4.0": (
        "Oak chest from the 13th century with runic inscription. Photo: Museum of Cultural History, Oslo. CC-BY-SA 4.0"
    ),
    "N 135 Høyjord stavkirke, Tellepinne med runeinnskrift. Foto: www.arild-hauge.com. ©": (
        "N 135 Høyjord stave church, tally stick with runic inscription. Photo: www.arild-hauge.com. ©"
    ),
    "Hedal runeinnskrift nr. II, III, IV og V. Foto: Aslak Liestøl. CC-BY-SA 4.0": (
        "Hedal runic inscriptions no. II, III, IV, and V. Photo: Aslak Liestøl. CC-BY-SA 4.0"
    ),
    "Foto og tegning av runeinnskriften av Karen Langsholt Holmqvist. CC-BY-SA 4.0": (
        "Photo and drawing of the runic inscription by Karen Langsholt Holmqvist. CC-BY-SA 4.0"
    ),
    "Foto av innskriften (Aslak Liestøl) og tegning av E. Knirk. CC-BY-SA 4.0": (
        "Photo of the inscription (Aslak Liestøl) and drawing by E. Knirk. CC-BY-SA 4.0"
    ),
    "Kalkereing av innskriften. Kalkering: Magnus Olsen. CC-BY-SA 4.0": (
        "Tracing of the inscription. Tracing: Magnus Olsen. CC-BY-SA 4.0"
    ),
    "Tegninger av runeinnskiften av J.C. Schive (1792-1878). Public Domain": (
        "Drawings of the runic inscription by J. C. Schive (1792-1878). Public Domain"
    ),
    "Hedal runeinnskrift nr. VI. Foto: Aslak Liestøl. CC-BY-SA 4.0": (
        "Hedal runic inscription no. VI. Photo: Aslak Liestøl. CC-BY-SA 4.0"
    ),
    "Tegning av lønnruneinnskriften. Tegning: K. Jonas Nordby, OiU. CC-BY-SA 4.0": (
        "Drawing of the cryptic runic inscription. Drawing: K. Jonas Nordby, UiO. CC-BY-SA 4.0"
    ),
    "Tegnning av runeinnskriften. Tegning: Ukjent. CC-BY-SA 4.0": (
        "Drawing of the runic inscription. Drawing: Unknown. CC-BY-SA 4.0"
    ),
}

PHRASE_REPLACEMENTS = [
    ("Nasjonalbiblotekets database", "National Library database"),
    ("Nasjonalbibliotekets database", "National Library database"),
    ("Kulturhistorisk Museum", "Museum of Cultural History"),
    ("Kulturhistorisk museum", "Museum of Cultural History"),
    ("Vitenskapsmuseet, NTNU", "NTNU University Museum"),
    ("NTNU Vitenskapsmuseet", "NTNU University Museum"),
    ("Universitetsmuseet i Bergen", "University Museum of Bergen"),
    ("Norges Artiske Universitetsmuseum", "Norwegian Arctic University Museum"),
    ("Arkeologisk museum, Stavanger", "Museum of Archaeology, Stavanger"),
    ("Norsk Folkemuseum", "Norwegian Museum of Cultural History"),
    ("Riksantikvarieämbetet", "Swedish National Heritage Board"),
    ("Universitetets Oldsaksamling", "University Collection of Antiquities"),
    ("Historisk museum", "Historical Museum"),
    ("Fotoarkiv", "Photo Archive"),
    ("fotoarkiv", "photo archive"),
    ("Fotobasen", "photo database"),
    ("Kirkemuseum", "Church Museum"),
    ("Norges Indskrifter med de ældre Runer", "Norges Indskrifter med de ældre Runer"),
    ("Norges Innskrifter med de yngre runer", "Norges Innskrifter med de yngre runer"),
    ("Norges innskrifter med de yngre runer", "Norges innskrifter med de yngre runer"),
    ("Nytt om runer nr.", "Nytt om runer no."),
    ("Fra Viking 1947", "from Viking 1947"),
    ("Fra Ludvig Wimmer", "from Ludvig Wimmer"),
    ("Fra Nicolaysen, Fornl.", "from Nicolaysen, Fornl."),
    ("Etter P. Alfsen", "after P. Alfsen"),
    ("Korrigert av Ole Worm", "corrected by Ole Worm"),
    ("gjengitt hos Worm", "reproduced by Worm"),
    ("Ukjent", "Unknown"),
    ("ukjent", "unknown"),
    ("Public Domian", "Public Domain"),
    ("Public Dominan", "Public Domain"),
    ("Public Damain", "Public Domain"),
    ("Public Domian", "Public Domain"),
    ("Public Domain", "Public Domain"),
    ("Public domain", "Public Domain"),
    ("Skjermdump fra 3D modell fra NIKU", "screenshot from 3D model from NIKU"),
    ("Bilde vist i inscription section", "Image shown in the inscription section"),
    ("ingen egen image caption oppgitt", "no separate caption provided"),
    ("Bilde av A-runeinnskriften", "Image of the A runic inscription"),
    ("Bilde av B-runeinnskriften", "Image of the B runic inscription"),
    ("Bilde av A-runeinnskfiften", "Image of the A runic inscription"),
    ("Bilde av B-runeinnskfiften", "Image of the B runic inscription"),
    ("Bilde av A-innskriften", "Image of the A inscription"),
    ("Bilde av B-innskriften", "Image of the B inscription"),
    ("Bilde av innskriftene", "Image of the inscriptions"),
    ("Bilde av innskriften", "Image of the inscription"),
    ("Bilde av runeinnskriften", "Image of the runic inscription"),
    ("Bilde av runrinnskriften", "Image of the runic inscription"),
    ("Bilde av runrinnskiften", "Image of the runic inscription"),
    ("Bilde av hele runestenen", "Image of the whole runestone"),
    ("Bilde av runestenen", "Image of the runestone"),
    ("Bilde av runesteinen", "Image of the runestone"),
    ("Bilde av runepinnen", "Image of the rune stick"),
    ("Bilde av runekjevlens A-side", "Image of side A of the rune stick"),
    ("Bilde av runekjevlens B-side", "Image of side B of the rune stick"),
    ("Bilde av runekjevlen", "Image of the rune stick"),
    ("Bilde av runebenets A-side", "Image of side A of the rune bone"),
    ("Bilde av runebenets B-side", "Image of side B of the rune bone"),
    ("Bilde av runebenet", "Image of the rune bone"),
    ("Bilde av benstykket", "Image of the bone piece"),
    ("Bilde av trepinnen", "Image of the wooden stick"),
    ("Bilde av trestykket", "Image of the piece of wood"),
    ("Bilde av merkelappens A-side", "Image of side A of the label tag"),
    ("Bilde av merkelappens B-side", "Image of side B of the label tag"),
    ("Bilde av merkelappen", "Image of the label tag"),
    ("Bilde av gjenstanden", "Image of the object"),
    ("Bilde av fragmentet", "Image of the fragment"),
    ("Bilde av kammen", "Image of the comb"),
    ("Bilde av kammem", "Image of the comb"),
    ("Bilde av kniven", "Image of the knife"),
    ("Bilde av nålens A-side", "Image of side A of the needle"),
    ("Bilde av nålens B-side", "Image of side B of the needle"),
    ("Bilde av svastikaet med de fire pentagrammeene", "Image of the swastika with the four pentagrams"),
    ("Bilde av Kirkeruinen", "Image of the church ruin"),
    ("Bilde av Fløkstad Kjøttkniv", "Image of the Fløkstad meat knife"),
    ("Bilde av Strøm runebryne", "Image of the Strøm rune whetstone"),
    ("Bilde av NIæR", "Image of NIæR"),
    ("Bilder og tekst fra", "Images and text from"),
    ("Alle bilder og tegninger er fra", "All images and drawings are from"),
    ("Sammensatt bilde av innskriften", "Composite image of the inscription"),
    ("Samling av diverse avtegninger av runeinnskrift", "Collection of various drawings of runic inscription"),
    ("Nærbilde av runeinnskriften", "Close-up of the runic inscription"),
    ("Nærbilde av runrinnskriften", "Close-up of the runic inscription"),
    ("Nærbilde av innskriften", "Close-up of the inscription"),
    ("Foto fra", "Photo from"),
    ("Foto av", "Photo by"),
    ("Foto:", "Photo:"),
    ("Tegning av A-innskriften", "Drawing of the A inscription"),
    ("Tegning av B-innskriften", "Drawing of the B inscription"),
    ("Tegning av hele beslaget", "Drawing of the whole fitting"),
    ("Tegning av gjenstanden", "Drawing of the object"),
    ("Tegning av innskriften", "Drawing of the inscription"),
    ("Teging av innskriften", "Drawing of the inscription"),
    ("Tefning av", "Drawing of"),
    ("Tegnning av", "Drawing of"),
    ("Tegning av kammem", "Drawing of the comb"),
    ("Tegning av lønnruneinnskriften", "Drawing of the cryptic runic inscription"),
    ("Tegning av lønnrunene", "Drawing of the cryptic runes"),
    ("Tegning av oljelampen", "Drawing of the oil lamp"),
    ("Tegning av rinnskriften", "Drawing of the inscription"),
    ("Tegning av runeinnskriften", "Drawing of the runic inscription"),
    ("Tegning av runepinnen", "Drawing of the rune stick"),
    ("Tegning av runesteinen", "Drawing of the runestone"),
    ("Tegning av runestenen", "Drawing of the runestone"),
    ("Tegning av runesøkkets a- og b-side", "Drawing of the runic sinker's A and B sides"),
    ("Tegning av side A", "Drawing of side A"),
    ("Tegning av treskiven", "Drawing of the wooden disk"),
    ("Tegning av Trå-øsen", "Drawing of the Trå scoop"),
    ("Tegninger av runeinnskiften", "Drawings of the runic inscription"),
    ("Tegning fra", "Drawing from"),
    ("Tegning:", "Drawing:"),
    ("Teging:", "Drawing:"),
    ("Tegning.", "Drawing."),
    ("Kalkering:", "Tracing:"),
    ("Kalkering", "Tracing"),
    ("Kart over runeinnskriftens plassering", "Map showing the location of the runic inscription"),
    ("Grunnriss med runeinnskriftens plassereing", "Plan showing the location of the runic inscription"),
    ("Innskriftsplassering i", "Location of the inscription in"),
    ("Plassering av runeinnskriftene i", "Location of the runic inscriptions in"),
    ("Plassering av runeinnskriftene", "Location of the runic inscriptions"),
    ("Plasseringen av runeteksten", "Location of the runic text"),
    ("Runeinnskriftenes plassering i", "Location of the runic inscriptions in"),
    ("Runeinnskriftenes plassering på vestvegg i", "Location of the runic inscriptions on the west wall in"),
    ("Runeinnskriftenes plassering på", "Location of the runic inscriptions on"),
    ("Runeinnskriftens plassering", "Location of the runic inscription"),
    ("Infotavle fra stedet", "Information board at the site"),
    ("Stolpe med runeinnskrift", "Post with runic inscription"),
    ("Paaskes (1626) tegning av runesteinen", "Paaske's (1626) drawing of the runestone"),
    ("Trekors som erstatning for et stenkors", "wooden cross as a replacement for a stone cross"),
    ("Beslaget delt i tre deler", "the fitting divided into three parts"),
    ("Stavkirke", "Stave Church"),
    ("stavkirke", "stave church"),
    ("Nidarosdomen", "Nidaros Cathedral"),
    ("Sakshaug kirke", "Sakshaug Church"),
    ("Værnes kirke", "Værnes Church"),
    ("vestvegg", "west wall"),
    ("runesten", "runestone"),
    ("runestenen", "runestone"),
    ("runesteinen", "runestone"),
    ("Kjølviksteinen", "the Kjølvik stone"),
    ("Tunesteinen", "the Tune stone"),
    ("stenkors", "stone cross"),
    ("stenen", "stone"),
    ("brakteat", "bracteate"),
    ("runesøkke", "runic sinker"),
    ("dørringen", "door ring"),
    ("avskrift", "copy"),
    ("rekonstrusjon", "reconstruction"),
    ("runeteksten", "the runic text"),
    ("runeinnskrift", "runic inscription"),
    ("innskriften", "the inscription"),
    ("innskrift", "inscription"),
    ("runeside", "rune side"),
    ("runeinnskriften", "the runic inscription"),
    ("gjenstanden", "the object"),
    ("tegninger", "drawings"),
    ("bilder", "images"),
    ("Bilde", "Image"),
    ("Tegning", "Drawing"),
    ("Teging", "Drawing"),
    ("Foto", "Photo"),
    ("foto", "photo"),
    ("hele", "whole"),
]

REGEX_REPLACEMENTS = [
    (re.compile(r"\bFoto;"), "Photo:"),
    (re.compile(r"\bOiU\b"), "UiO"),
    (re.compile(r"\bUio\b"), "UiO"),
    (re.compile(r"\bJanas Nordby\b"), "Jonas Nordby"),
    (re.compile(r"\bChtristie\b"), "Christie"),
    (re.compile(r"\bOlsrn\b"), "Olsen"),
    (re.compile(r"\bTeging\b"), "Drawing"),
    (re.compile(r"\bTefning\b"), "Drawing"),
    (re.compile(r"\bTegnning\b"), "Drawing"),
    (re.compile(r"\bNærbilde\b"), "Close-up"),
    (re.compile(r"\bside ([AB])\b"), r"side \1"),
    (re.compile(r"\b([AB])-side\b"), r"side \1"),
    (re.compile(r"\ba- og b-side\b"), "A and B sides"),
    (re.compile(r"\bside (\d+)\b", re.IGNORECASE), r"page \1"),
    (re.compile(r"\bbind ([IVX\d]+)\b", re.IGNORECASE), r"volume \1"),
    (re.compile(r"\bdel (\d+)\b", re.IGNORECASE), r"part \1"),
    (re.compile(r"\bDel (\d+)\b"), r"Part \1"),
    (re.compile(r"\b(\d+) - (\d+)\b"), r"\1-\2"),
    (re.compile(r"\s+"), " "),
]

OBJECT_EXACT_TRANSLATIONS = {
    "1. detalje av innskriften": "detail 1 of the inscription",
    "2. detalje av innskriften": "detail 2 of the inscription",
    "3. detalje av innskriften": "detail 3 of the inscription",
    "4. detalje av innskriften": "detail 4 of the inscription",
    "A-delen av runeinnskriften": "part A of the runic inscription",
    "B-delen av runeinnskriften": "part B of the runic inscription",
    "C-delen av runeinnskriften": "part C of the runic inscription",
    "A-siden": "side A",
    "A-siden av runekjevlen": "side A of the rune stick",
    "B-siden av runekjevlen": "side B of the rune stick",
    "A-sidens runeinnskrift": "the runic inscription on side A",
    "B-sidens runeinnskrift": "the runic inscription on side B",
    "begge sider av amuletten": "both sides of the amulet",
    "av trestykkets A-side": "side A of the piece of wood",
    "av trestykkets B-side": "side B of the piece of wood",
    "runeinnskriften på isleggen (skjøyten)": "the runic inscription on the bone skate",
    "isleggene": "the bone skates",
    "vokstavlen før konservering": "the wax tablet before conservation",
    "plankene ned runer": "the planks with runes",
    "runestenen sammentatt": "the reconstructed runestone",
    "runestenen stående på Veum, før den brakk i to": "the runestone standing at Veum before it broke in two",
    "N A71, N A72 og N A77 runepinner": "the rune sticks N A71, N A72, and N A77",
    "N 572 Gol stavkirke VIII": "N 572 Gol stave church VIII",
    "N 170 Vinje Stavkirke": "N 170 Vinje stave church",
    "N 171 Vinje Stavkirke": "N 171 Vinje stave church",
    "Bilde av Julianehøj": "Julianehøj",
    "dørringen av www.arild-hauge.com. ©": "the door ring. Photo: www.arild-hauge.com. ©",
    "innskriften av Aslak Liestøl. CC-BY-SA 4.0": "the inscription. Photo: Aslak Liestøl. CC-BY-SA 4.0",
    "runesteinen av Aslak Liestøl. CC-BY-SA 4.0": "the runestone. Photo: Aslak Liestøl. CC-BY-SA 4.0",
}

OBJECT_TERM_TRANSLATIONS = [
    ("runeinnskriften (Merket VII)", "the runic inscription (marked VII)"),
    ("runeinnskriften (Merket III)", "the runic inscription (marked III)"),
    ("runeinnskriften (Merket II)", "the runic inscription (marked II)"),
    ("runeinnskriften (Merket I)", "the runic inscription (marked I)"),
    ("runeinnskriften", "the runic inscription"),
    ("runeinnskrift", "runic inscription"),
    ("runeinnskriftsiden", "the runic-inscription side"),
    ("runeinnskrioften", "the runic inscription"),
    ("runeinnskrften", "the runic inscription"),
    ("runrbenet", "the rune bone"),
    ("runebenets", "the rune bone's"),
    ("runebenet", "the rune bone"),
    ("runekjevlens", "the rune stick's"),
    ("Runekjevlens", "the rune stick's"),
    ("runekjevlen", "the rune stick"),
    ("runekjevle", "the rune stick"),
    ("runekjeppen", "the rune stick"),
    ("runepinnens", "the rune stick's"),
    ("runepinnen", "the rune stick"),
    ("runepinner", "rune sticks"),
    ("runestaven", "the rune staff"),
    ("runesteinsfragmentet", "the runestone fragment"),
    ("runestenens", "the runestone's"),
    ("runestenen", "the runestone"),
    ("runesteinen", "the runestone"),
    ("reunestenen", "the runestone"),
    ("runstenen", "the runestone"),
    ("runeside", "runic side"),
    ("A-runeinnskriften", "the A runic inscription"),
    ("B-runeinnskriften", "the B runic inscription"),
    ("C-runeinnskriften", "the C runic inscription"),
    ("A-runeinnskfiften", "the A runic inscription"),
    ("B-runeinnskfiften", "the B runic inscription"),
    ("A-innskriften", "the A inscription"),
    ("B-innskriften", "the B inscription"),
    ("C-innskriften", "the C inscription"),
    ("innskriftens", "the inscription's"),
    ("innskriftene", "the inscriptions"),
    ("innskriften", "the inscription"),
    ("innskriten", "the inscription"),
    ("innskrift", "inscription"),
    ("nnnskriften", "the inscription"),
    ("hele runestenen", "the whole runestone"),
    ("hele runstenen", "the whole runestone"),
    ("hele skoen", "the whole shoe"),
    ("hele lokket", "the whole lid"),
    ("hele runstenen", "the whole runestone"),
    ("gjenstandens", "the object's"),
    ("gjenstanden", "the object"),
    ("gjenstanden av klebersten", "the soapstone object"),
    ("gjenstanden med runeinnskrift", "the object with runic inscription"),
    ("trestykket med runeinnskrift", "the piece of wood with runic inscription"),
    ("trestykkets", "the piece of wood's"),
    ("trestykket", "the piece of wood"),
    ("trepinnens", "the wooden stick's"),
    ("trepinnes", "the wooden stick's"),
    ("trepinnen", "the wooden stick"),
    ("trebiten", "the piece of wood"),
    ("trekarbundens", "the wooden vessel base's"),
    ("trekarbunnen", "the wooden vessel base"),
    ("treskålen", "the wooden bowl"),
    ("treslåen", "the wooden latch"),
    ("treskiven", "the wooden disk"),
    ("trekorsets", "the wooden cross's"),
    ("trekorset", "the wooden cross"),
    ("dyrehode av tre", "the wooden animal head"),
    ("det knivformet treredskap", "the knife-shaped wooden implement"),
    ("benstykket", "the bone piece"),
    ("bennålen", "the bone needle"),
    ("hvalbenet", "the whale bone"),
    ("blyblekkamuletten", "the lead-sheet amulet"),
    ("blyamuletten", "the lead amulet"),
    ("blykorset", "the lead cross"),
    ("den brettede blyremsen", "the folded lead strip"),
    ("brakteaten", "the bracteate"),
    ("Kirkeklokken", "the church bell"),
    ("klokkehammeren", "the bell clapper"),
    ("døpefonten", "the baptismal font"),
    ("døren med jernbeslag", "the door with iron fittings"),
    ("døren med beslag", "the door with fittings"),
    ("dørbeslaget", "the door fitting"),
    ("dørringen", "the door ring"),
    ("drikkehornet", "the drinking horn"),
    ("en anden innskrift på hornet med inskrift ran", "another inscription on the horn with the inscription ran"),
    ("fiskesøkket", "the fishing sinker"),
    ("futeralets oppbevaringsrom", "the case's storage compartment"),
    ("futeralets runeinnskrift", "the case's runic inscription"),
    ("futeralet med runeinnskrift", "the case with runic inscription"),
    ("glimmerskiven", "the mica disk"),
    ("halsringen", "the neck ring"),
    ("hårnålen med runeinnskrift", "the hairpin with runic inscription"),
    ("høvelen", "the plane"),
    ("høvlen fra alle kanter", "the plane from all sides"),
    ("kammen med runeinnskrift", "the comb with runic inscription"),
    ("kammen", "the comb"),
    ("karvestokken", "the carved block"),
    ("kisten fra Logtun kirke", "the chest from Logtun church"),
    ("kiste fra Lomen stavkirke", "the chest from Lomen stave church"),
    ("kniven", "the knife"),
    ("lysholderen", "the candleholder"),
    ("lønnrunen i innskriften som utgjør u-runen", "the cryptic rune in the inscription that forms the u-rune"),
    ("lønnrunenene på runepinnen", "the cryptic runes on the rune stick"),
    ("merkelappens", "the label tag's"),
    ("merkelappen", "the label tag"),
    ("murstenen", "the brick"),
    ("målepinnen", "the measuring stick"),
    ("nålens", "the needle's"),
    ("nålen", "the needle"),
    ("nøkkelskaft", "the key handle"),
    ("overlæret med runer", "the upper leather with runes"),
    ("pilspissen", "the arrowhead"),
    ("skjeskaftet", "the spoon handle"),
    ("snellehjulet", "the spindle whorl"),
    ("spinnehjulets", "the spindle whorl's"),
    ("spinnehjulet", "the spindle whorl"),
    ("spennes", "the brooch's"),
    ("spennens", "the brooch's"),
    ("Spennen", "the brooch"),
    ("spennen", "the brooch"),
    ("strengestolen", "the string bridge"),
    ("sverdsliren", "the sword scabbard"),
    ("sverdets", "the sword's"),
    ("vevskjeen", "the weaving batten"),
    ("vokstavlen", "the wax tablet"),
    ("filkloen", "the file claw"),
    ("gravplassen", "the burial site"),
    ("helleggraven", "the slab grave"),
    ("hellegraven", "the slab grave"),
    ("likstenen", "the gravestone"),
    ("melbingen", "the flour bin"),
    ("skjoldbuen", "the shield bow"),
    ("skjoldet", "the shield"),
    ("skrinet", "the chest"),
    ("skrivetavlen", "the writing tablet"),
    ("spillebrikken", "the gaming piece"),
    ("stavngerkorsset", "the Stavanger cross"),
    ("stenen med ornamenter", "the stone with ornaments"),
    ("stenen med runeinnskrift", "the stone with runic inscription"),
    ("stenen på sokkel", "the stone on a plinth"),
    ("stenen", "the stone"),
    ("amuletten", "the amulet"),
    ("fragmentet", "the fragment"),
    ("Kirkeruinen", "the church ruin"),
    ("bautasteinen", "the standing stone"),
    ("bautastenen", "the standing stone"),
    ("banketreet", "the beater"),
    ("høyre portal i Nesland stavkirke", "the right portal in Nesland stave church"),
    ("venstre portal i Nesland stavkirke", "the left portal in Nesland stave church"),
    ("portalen med runeinnskriften", "the portal with the runic inscription"),
    ("kopi av runestenen", "a copy of the runestone"),
    ("kopi Galtelandstenen", "a copy of the Galteland stone"),
    ("Røykjenessteinens informasjonstavle", "the Røykjenes stone's information board"),
    ("Skafså gapestokk", "Skafså pillory"),
    ("Skafså steinmerr", "Skafså stone mare"),
    ("Skafså Kirke", "Skafså Church"),
    ("Hårbergstenens runeinnskrift", "the Hårberg stone's runic inscription"),
    ("Gørlev runesten", "the Gørlev runestone"),
    ("Tunestenen", "the Tune stone"),
    ("Tustenen", "the Tu stone"),
    ("Vatn runesten", "the Vatn runestone"),
    ("Oddernes stenen", "the Oddernes stone"),
    ("Røykjenessteinen", "the Røykjenes stone"),
    ("Skolevollstenen", "the Skolevoll stone"),
    ("Eggestenen", "the Egge stone"),
    ("Dynnastenen", "the Dynna stone"),
    ("Eigersundstenen", "the Eigersund stone"),
    ("Fåbergstenen", "the Fåberg stone"),
    ("Galtelandstenen", "the Galteland stone"),
    ("Hårbergstenen", "the Hårberg stone"),
    ("Husebystenen", "the Huseby stone"),
    ("Kulistenen", "the Kuli stone"),
    ("Søgnestenen", "the Søgne stone"),
    ("Kårstad Fjellinnskrift", "the Kårstad rock inscription"),
    ("Mauland Medaljonen", "the Mauland medallion"),
    ("Runestenen", "the runestone"),
]


def translate_object_phrase(phrase: str) -> str:
    phrase = phrase.strip()
    if phrase in OBJECT_EXACT_TRANSLATIONS:
        return OBJECT_EXACT_TRANSLATIONS[phrase]

    for pattern, replacement in [
        (r"^([ABC])-delen av runeinnskriften$", r"part \1 of the runic inscription"),
        (r"^([ABC])-siden av runekjevlen$", r"side \1 of the rune stick"),
        (r"^([ABC])-sidens runeinnskrift$", r"the runic inscription on side \1"),
        (r"^(.+?)ens ([ABC])-side$", r"side \2 of \1"),
        (r"^(.+?)ets ([ABC])-side$", r"side \2 of \1"),
        (r"^(.+?)s ([ABC])-side$", r"side \2 of \1"),
        (r"^(.+?)ens ([ABC])-siden$", r"side \2 of \1"),
        (r"^(.+?)ens bakside$", r"the back of \1"),
        (r"^(.+?)s bakside$", r"the back of \1"),
        (r"^(.+?)ens forside$", r"the front of \1"),
        (r"^(.+?)s forside$", r"the front of \1"),
        (r"^(.+?)ens runeside$", r"the runic side of \1"),
        (r"^(.+?)s runeside$", r"the runic side of \1"),
        (r"^(.+?)ens dekorside$", r"the decorated side of \1"),
        (r"^(.+?)ens nedre del$", r"the lower part of \1"),
        (r"^(.+?)ens øvre del$", r"the upper part of \1"),
        (r"^([ABC])-stenen$", r"stone \1"),
    ]:
        match = re.match(pattern, phrase)
        if match:
            result = re.sub(pattern, replacement, phrase)
            return translate_object_phrase(result)

    for separator, english in ((" på ", " on "), (" med ", " with "), (" fra ", " from "), (" og ", " and ")):
        if separator in phrase:
            left, right = phrase.split(separator, 1)
            return f"{translate_object_phrase(left)}{english}{translate_object_phrase(right)}"

    if " av " in phrase and not re.search(r" av [A-ZÅÄÖÆØ]", phrase):
        left, right = phrase.split(" av ", 1)
        return f"{translate_object_phrase(left)} of {translate_object_phrase(right)}"

    translated = phrase
    for source, target in sorted(OBJECT_TERM_TRANSLATIONS, key=lambda item: len(item[0]), reverse=True):
        translated = re.sub(rf"(?<!\w){re.escape(source)}(?!\w)", target, translated)
    translated = translated.replace("the the ", "the ")
    translated = translated.replace("the rune stick's side", "side of the rune stick")
    translated = translated.replace("the wooden stick's side", "side of the wooden stick")
    translated = translated.replace("side A of the rune stick's", "side A of the rune stick")
    translated = translated.replace("side B of the rune stick's", "side B of the rune stick")
    translated = translated.replace("side C of the rune stick's", "side C of the rune stick")
    translated = translated.replace("side A of the wooden stick's", "side A of the wooden stick")
    translated = translated.replace("side B of the wooden stick's", "side B of the wooden stick")
    translated = translated.replace("side C of the wooden stick's", "side C of the wooden stick")
    translated = translated.replace("the label tag's side", "side of the label tag")
    translated = translated.replace("the needle's side", "side of the needle")
    translated = translated.replace("the rune bone's side", "side of the rune bone")
    translated = translated.replace("the object 's", "the object's")
    return translated


OBJECT_CAPTION_PATTERNS = [
    (re.compile(r"^Bilde av (.*?)(?=(?:\. Foto|\. Tegning|\. Norges|\. Public|$))"), "Image of "),
    (re.compile(r"^Nærbilde av (.*?)(?=(?:\. Foto|\. Tegning|\. Public|$))"), "Close-up of "),
    (re.compile(r"^Detalje av (.*?)(?=(?:\. Foto|$))"), "Detail of "),
    (re.compile(r"^Detajle av (.*?)(?=(?:\. Foto|$))"), "Detail of "),
    (re.compile(r"^Kalkering av (.*?)(?=(?:\. Kalkering|\. Foto|$))"), "Tracing of "),
    (re.compile(r"^Klakering av (.*?)(?=(?:\. Kalkering|$))"), "Tracing of "),
    (re.compile(r"^Tegning av (.*?)(?=(?:\. Tegning|\. Public|$))"), "Drawing of "),
    (re.compile(r"^Bilde og tegning av (.*?)(?=(?:\. Foto|$))"), "Image and drawing of "),
    (re.compile(r"^Foto og tegning av (.*?)(?=(?:\. CC-|$))"), "Photo and drawing of "),
]

BROAD_OBJECT_REPLACEMENTS = {
    "runesten",
    "runestenen",
    "runesteinen",
    "Kjølviksteinen",
    "Tunesteinen",
    "stenkors",
    "stenen",
    "brakteat",
    "runesøkke",
    "dørringen",
    "avskrift",
    "rekonstrusjon",
    "runeteksten",
    "runeinnskrift",
    "innskriften",
    "innskrift",
    "runeside",
    "runeinnskriften",
    "gjenstanden",
    "tegninger",
    "bilder",
    "hele",
}


def translate_object_caption_prefix(text: str) -> str:
    for pattern, prefix in OBJECT_CAPTION_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        original_object = match.group(1)
        translated_object = translate_object_phrase(original_object)
        return text[: match.start()] + prefix + translated_object + text[match.end() :]
    return text


def translate_segment(text: str) -> str:
    text = text.strip()
    if text in EXACT_TRANSLATIONS:
        return EXACT_TRANSLATIONS[text]

    translated = translate_object_caption_prefix(text)
    for source, target in PHRASE_REPLACEMENTS:
        if source in BROAD_OBJECT_REPLACEMENTS:
            continue
        translated = translated.replace(source, target)
    for pattern, target in REGEX_REPLACEMENTS:
        translated = pattern.sub(target, translated)

    translated = translated.replace("Photo by www.arild-hauge.com", "Photo: www.arild-hauge.com")
    translated = translated.replace("Drawing of the inscription of ", "Drawing of the inscription by ")
    translated = translated.replace("Drawing of the runic inscription of ", "Drawing of the runic inscription by ")
    translated = translated.replace("Drawing of the runestone. Drawing of ", "Drawing of the runestone. Drawing: ")
    translated = translated.replace("Drawing of the inscription. Drawing of ", "Drawing of the inscription. Drawing: ")
    translated = translated.replace("Drawing. K. Jonas", "Drawing: K. Jonas")
    translated = translated.replace("Photo by Aslak", "Photo: Aslak")
    translated = translated.replace("Photo by Ogneslav", "Photo: Ogneslav")
    translated = translated.replace("Photo by the inscription", "Photo of the inscription")
    translated = translated.replace("Photo og tegning", "Photo and drawing")
    translated = translated.replace("Drawing av ", "Drawing by ")
    translated = translated.replace("Tracing av ", "Tracing by ")
    translated = translated.replace("Tracing of the inscription av ", "Tracing of the inscription by ")
    translated = translated.replace("Tracing of the runic inscription av ", "Tracing of the runic inscription by ")
    translated = translated.replace("Drawing of the inscription av ", "Drawing of the inscription by ")
    translated = translated.replace("Drawing of the runic inscription av ", "Drawing of the runic inscription by ")
    translated = translated.replace("Image of the inscription av ", "Image of the inscription by ")
    translated = translated.replace("Image of the runestone av ", "Image of the runestone by ")
    translated = translated.replace("from 1626 av ", "from 1626 by ")
    translated = translated.replace('from artikkel "Om Runemonumenter i Bergens Stift" av ', 'from the article "Om Runemonumenter i Bergens Stift" by ')
    translated = translated.replace("Fra Norges innskrifter med de yngre runer", "from Norges innskrifter med de yngre runer")
    translated = translated.replace("fra Norges innskrifter med de yngre runer", "from Norges innskrifter med de yngre runer")
    translated = translated.replace("Fra Norges Indskrifter med de ældre Runer", "from Norges Indskrifter med de ældre Runer")
    translated = translated.replace("Norges inscriptioner med de yngre runer", "Norges innskrifter med de yngre runer")
    translated = translated.replace("Drawing: Fra ", "Drawing: from ")
    translated = translated.replace("Photo:Drawing:", "Photo/drawing:")
    translated = translated.replace("utstillingen Kyss meg", 'the exhibition "Kyss meg"')
    translated = translated.replace("Hedal runic inscription nr. II, III, IV og V", "Hedal runic inscriptions no. II, III, IV, and V")
    translated = translated.replace("N 360 og N 361", "N 360 and N 361")
    translated = translated.replace("A og B side", "sides A and B")
    translated = translated.replace("Fra oven og ned er", "From top to bottom are")
    translated = translated.replace(" og N ", " and N ")
    translated = translated.replace("A-siden", "side A")
    translated = translated.replace("de to sider", "the two sides")
    translated = translated.replace("rune stick's 4 sider", "four sides of the rune stick")
    translated = translated.replace("the back of spenne", "the back of the brooch")
    translated = translated.replace("the front of spenne", "the front of the brooch")
    translated = translated.replace("Informasjonstavle på stedet", "Information board at the site")
    translated = translated.replace("Gjenfunnet del av", "Rediscovered part of")
    translated = translated.replace(" i 2007", " in 2007")
    translated = translated.replace("Kiste av eik fra 1200-tallet med runic inscription", "Oak chest from the 13th century with runic inscription")
    translated = translated.replace("Tellepinne med runic inscription", "tally stick with runic inscription")
    translated = translated.replace("Dørbeslaget er gjengitt i to deler", "the door fitting is reproduced in two parts")
    translated = translated.replace("Image of dyrehode of tre", "Image of the wooden animal head")
    translated = translated.replace("Image of døren with jernbeslag", "Image of the door with iron fittings")
    translated = translated.replace("Image of døren with beslag", "Image of the door with fittings")
    translated = translated.replace("Image of en anden inscription on hornet with inskrift ran", "Image of another inscription on the horn with the inscription ran")
    translated = translated.replace("Image of en deltalje of lokket", "Image of a detail of the lid")
    translated = translated.replace("Image of futeralet with runic inscription", "Image of the case with runic inscription")
    translated = translated.replace("Image of the object of klebersten", "Image of the soapstone object")
    translated = translated.replace("Image of hårnålen with runic inscription", "Image of the hairpin with runic inscription")
    translated = translated.replace("Image of overlæret with runer", "Image of the upper leather with runes")
    translated = translated.replace("with runer", "with runes")
    translated = translated.replace("of merkelapp", "of the label tag")
    translated = translated.replace("of nål", "of the needle")
    translated = translated.replace("of trekors", "of the wooden cross")
    translated = translated.replace("of trepinn", "of the wooden stick")
    translated = translated.replace("of trepinne", "of the wooden stick")
    translated = translated.replace("of trekarbund", "of the wooden vessel base")
    translated = translated.replace("Fonnås spennen", "Fonnås brooch")
    translated = translated.replace("dørbeslag", "door fitting")
    translated = translated.replace("hele beslaget", "the whole fitting")
    translated = translated.replace("Universitetes Oldsaksamling", "University Collection of Antiquities")
    translated = translated.replace("Stavkirkene, deres egenart og historie", "Stavkirkene, deres egenart og historie")
    translated = translated.replace("Stave Churchne", "stave churches")
    translated = translated.replace("deres egenart og historie", "their character and history")
    translated = translated.replace("Diverse avtegninger av runeinnskriften", "Various drawings of the runic inscription")
    translated = translated.replace("Flere avtegninger av runeinnskriften", "Several drawings of the runic inscription")
    translated = translated.replace("B.C de Fines tegning av innskriften", "B. C. de Fine's drawing of the inscription")
    translated = translated.replace("de Fines tegning fra 1745 av innskriften", "de Fine's drawing from 1745 of the inscription")
    translated = translated.replace("Gerhard Munthes tegning av innskriften", "Gerhard Munthe's drawing of the inscription")
    translated = translated.replace("Kalkereing av the inscription", "Tracing of the inscription")
    translated = translated.replace("Klakering av the inscription", "Tracing of the inscription")
    translated = translated.replace("Tegnning av runeinnskriften", "Drawing of the runic inscription")
    translated = translated.replace("lønnrunic inscriptionen", "cryptic runic inscription")
    translated = translated.replace("Image of NIæR", "Image of NIæR")
    translated = translated.replace("Image of the the", "Image of the")
    translated = translated.replace("Drawing of the the", "Drawing of the")
    translated = translated.replace("Close-up of the the", "Close-up of the")
    translated = translated.replace("runic inscription i ", "runic inscription in ")
    translated = translated.replace("runic inscriptions i ", "runic inscriptions in ")
    translated = translated.replace("inscription i ", "inscription in ")
    translated = translated.replace("inscriptions i ", "inscriptions in ")
    translated = translated.replace("the runic inscriptionens", "the runic inscription's")
    translated = translated.replace("runic inscriptionens", "runic inscription's")
    translated = translated.replace("the inscriptionens", "the inscription's")
    translated = translated.replace("inscriptionens", "inscription's")
    translated = translated.replace(" .", ".")
    translated = translated.replace(" ,", ",")
    translated = translated.strip()
    if translated and translated[0].islower():
        translated = translated[0].upper() + translated[1:]
    return translated


def translate_caption(text: str) -> str:
    parts = [translate_segment(part) for part in text.split(" ¤ ")]
    return " ¤ ".join(parts)


def fill_translations(audit_csv: Path) -> int:
    with audit_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    changed = 0
    for row in rows:
        if row.get("source_table") != "runes_imagelink" or row.get("source_field") != "info":
            continue
        translated = translate_caption(row["original"])
        if row.get("suggested_en") != translated:
            row["suggested_en"] = translated
            row["review_status"] = "draft"
            changed += 1

    with audit_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-csv", type=Path, default=DEFAULT_AUDIT_CSV)
    args = parser.parse_args()
    changed = fill_translations(args.audit_csv)
    print(f"Updated {changed} image-caption translation rows in {args.audit_csv}")


if __name__ == "__main__":
    main()
