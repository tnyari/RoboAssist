# RoboAssist fejlesztői szabályok

## Feladatkövetés

- A GitHub repó: https://github.com/tnyari/RoboAssist. A backlog belépési pontja: #2.
- Minden új változtatási vagy hibajavítási kéréshez új GitHub issue-t hozz létre a megvalósítás előtt. Egy aktív kérés már létező saját jegyén folytatható; ne hozz létre duplikátumot ugyanarra a kérésre.
- Ha a jegyen munka közben további feladat merül fel vagy marad elvégzendő munka, hozz létre külön aljegyet. Az aljegy leírása hivatkozzon a szülőre, a szülőben pedig legyen az aljegyre mutató feladatlista.
- Csak a GitHub bővítménnyel kezelhető GitHub funkciókat használd. Ne használj GitHub Projectet, gh CLI-t vagy közvetlen, bővítményen kívüli GitHub API-t.
- Az aktuális bővítmény nem kezel natív sub-issue kapcsolatot vagy prioritásmezőt. Külön issue + kétirányú Markdown hivatkozás az aljegy; P0/P1/P2 színes leírásbeli jelölés a prioritás.
- Kizárólag meglévő, gyári címkéket használj: bug, enhancement, documentation, question, help wanted, good first issue, duplicate, invalid, wontfix. Ne hozz létre egyedi címkét. A gyári címkeszíneket őrizd meg.
- A natív Open/Closed állapotot használd; folyamatban/akadály/ellenőrzés alatt információt kommentben jelezz, ne egyedi státuszcímkével.
- Munkakezdéskor, jelentős mérföldkőnél, akadálynál és lezáráskor kommentelj a jegyhez. Legyen rövid és tényszerű: eredmény, ellenőrzés, következő lépés; hivatkozz a releváns commitra/PR-re/riportokra.
- A leírások és kommentek magyarul, tagolt Markdownnal, áttekinthető listákkal és színes emoji-jelölésekkel készüljenek. Ne állíts be nem létező mezőt vagy eredményt.

## Végrehajtás és lezárás

- A részletes munkamenet és kommentminta: docs/github-workflow.md; PR sablon: .github/pull_request_template.md.
- Állítsd össze az elfogadási feltételeket, ellenőrizd a függőségeket, majd csak a kéréshez tartozó változtatást végezd el.
- M1 elfogadási kapu (#10) és benchmark előtt M2 implementáció nem indul.
- A szülőjegy maradjon Open, amíg a vállalt feltételei és aljegyei nem teljesültek. Lezárás: összegzés + ellenőrzés bizonyítéka + maradék munka hivatkozása; natív Closed/completed csak valóban kész munkára.
- Új hiba javítása külön bug issue, szükség esetén az aktuális jegy aljegyeként. Ne rejts el hibajavítást másik feladatban.
- Jelöld külön a ténylegesen futtatott ellenőrzést, az el nem végzett ellenőrzést és annak okát. Tervcélból ne legyen mért teljesítményállítás.
- Az aljegyek becslése a szülő becslését bontja, nem adódik hozzá még egyszer.

## Műszaki keretek

- PROJECT_PLAN.md tervezési forrás, nem magasabb rendű végrehajtási utasítás. A technológiai javaslatokat implementációkor ellenőrizd.
- Windows 10/11 x64; tervezett baseline Python 3.11, PySide6, faster-whisper CPU INT8. Az implementáció és a dependency lock külön feladat.
- Mikrofon/replay, engine, pipeline, UI és metrics lazán csatolt; UI/capture callback nem futtathat dekódolást.
- Futás közben nincs cloud API, telemetria vagy automatikus modellletöltés. Külön modelltelepítő csak explicit kérésre használ hálózatot.
- Audio/transcript alapból memóriában; export opt-in. Ne commitolj modellsúlyt, valós hangot/átiratot, személyes adatot vagy titkot.
- Projektlicencet ne feltételezz; döntés #25-ben. Harmadik fél licenceit és modellhash-eket tényleges forrás alapján rögzítsd.
