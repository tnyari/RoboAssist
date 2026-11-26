# RoboAssist · Offline STT

🟦 **Fejlesztésre előkészített repó** · Windows 10/11 x64 · magyar beszédfelismerés

A cél helyi, CPU-n is futó, közel valós idejű feliratozás. **M1:** mikrofon → Windows feliratablak. **M2:** kiválasztott Chrome/Edge fül → ugyanaz a helyi STT core → böngészős felirat.

Ez a repó jelenleg tervet, feladatbontást, munkaszabályokat, issue-sablonokat és könyvtárvázat tartalmaz. Futtatható STT alkalmazás, dependency lock és sikeresen futó CI még nincs.

## 🧭 Indulás

- [Fejlesztési ütemterv és összes főjegy](https://github.com/tnyari/RoboAssist/issues/2)
- [Eredeti projektterv](PROJECT_PLAN.md)
- [Fejlesztői előkészítés és következő feladatok](docs/development.md)
- [Munkakövetési szabályok](docs/github-workflow.md)
- [Hozzájárulás](CONTRIBUTING.md) · [Agent szabályok](AGENTS.md)
- [Architektúra és repo struktúra](docs/architecture.md)

Első végrehajtható feladat: [Python 3.11 x64 környezet és lock (#16)](https://github.com/tnyari/RoboAssist/issues/16), majd [Windows CI (#17)](https://github.com/tnyari/RoboAssist/issues/17). Az STT-001 főjegy ezek lezárásáig nyitva marad.

## 🚦 Sorrend és elfogadás

| Szakasz | Eredmény | Kapu |
|---|---|---|
| 🟦 M1 | Offline mikrofonos magyar felirat, benchmark, Windows csomag | [STT-008 #10](https://github.com/tnyari/RoboAssist/issues/10) |
| 🟪 M2 | Tab capture, native host, böngészős UI, VCC teszt | Csak elfogadott M1 után; [STT-105 #15](https://github.com/tnyari/RoboAssist/issues/15) |

A terv becslése M1: **44–75 h**, M2: **35–63 h**. Az aljegyek a szülő becslését bontják; nem összeadandó többletbecslések. A teljesítménycélok pilot célok, nem mért eredmények.

## 📝 GitHub munkarend

Minden új változtatási vagy hibajavítási kéréshez **új issue** készül a munka előtt. Munka közben felmerülő vagy megmaradó feladat külön aljegy, mindkét irányban hivatkozva. Kezdéskor, fontos mérföldkőnél, akadálynál és lezáráskor rövid komment készül.

Gyári címkék: `enhancement`, `bug`, `documentation`; natív állapot: **Open/Closed**. 🔴 P0 / 🟠 P1 / 🟡 P2 a leírás prioritásjelölése. Nincs GitHub Project, egyedi címke vagy külön státuszmező. Az aljegyek összekapcsolt issue-k, nem a bővítményben nem elérhető natív sub-issue objektumok.

## 🔒 Offline működés és adatok

A modell előzetes telepítése után az STT internet nélkül működjön, cloud API és telemetria nélkül. Rögzítés csak explicit Start után, látható állapottal. Audio/transcript alapból memóriában; mentés csak tudatos exporttal. Modellsúlyok, valós ügyfélhang, átiratok és titkok nem kerülnek Gitbe.

## 📄 Forrás és licenc

A [PROJECT_PLAN.md](PROJECT_PLAN.md) a kapott `OFFLINE_STT_PROJECT_PLAN.md` változatlan tartalmú másolata. Tervezési bemenet; technológiai javaslatai és hivatkozásai implementációkor ellenőrzendők. A munkarendet a felhasználói kérés és a repó szabályai határozzák meg.

A projektlicenc még nincs kiválasztva. A terv MIT-javaslata nem licencengedély. [Licencdöntés és harmadik fél feltételei (#25)](https://github.com/tnyari/RoboAssist/issues/25), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
