# RoboAssist · Offline STT

🟦 **Fejlesztésre előkészített repó** · Windows 10/11 x64 · magyar beszédfelismerés

A cél helyi, CPU-n is futó, közel valós idejű feliratozás. **M1:** mikrofon → Windows feliratablak. **M2:** kiválasztott Chrome/Edge fül → ugyanaz a helyi STT core → böngészős felirat.

Elkészült a Python 3.11 x64 fejlesztői setup, a verzió- és hash-rögzített dependency lock, valamint a konfigurációbetöltő és validáló CLI. A [Windows CI workflow](docs/ci.md) a meglévő ellenőrzéseket futtatja; futtatható STT alkalmazás még nincs.

A [mikrofon capture, állapottartó resampling és időzített WAV replay](docs/audio.md) közös 16 kHz mono float32 audioforrást ad. Eszközlistázás és explicit, hangmentés nélküli mikrofonpróba a fejlesztői parancssorból indítható.

A [helyi SpeechEngine](docs/engine.md) workerből használható CPU INT8 adaptert,
korlátos audiopuffert és reset/flush életciklust ad. A [base/small modellek](models/README.md)
külön, explicit telepíthetők, rögzített revision/SHA/licenc alapján. Az UI és a
session pipeline bekötése a következő M1 feladatok része.

## 🧭 Indulás

- [Fejlesztési ütemterv és összes főjegy](https://github.com/tnyari/RoboAssist/issues/2)
- [Eredeti projektterv](PROJECT_PLAN.md)
- [Fejlesztői előkészítés és következő feladatok](docs/development.md)
- [Munkakövetési szabályok](docs/github-workflow.md)
- [Hozzájárulás](CONTRIBUTING.md) · [Agent szabályok](AGENTS.md)
- [Architektúra és repo struktúra](docs/architecture.md)

Fejlesztői setup a repó gyökeréből: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-dev.ps1`. [Parancsok és előfeltételek](docs/development.md), [tényleges ellenőrzési riport](docs/reports/issue-16-environment.md).

A fejlesztés a már ellenőrzött Windows 10 gépen folytatódik. A [#16 környezetfeladat](https://github.com/tnyari/RoboAssist/issues/16) tiszta Windows gépes ellenőrzése [#28](https://github.com/tnyari/RoboAssist/issues/28) alatt a felhasználó döntése alapján egyelőre halasztott; a Windows CI [#17](https://github.com/tnyari/RoboAssist/issues/17) feladata. Az STT-001 főjegy a vállalt feltételek teljesüléséig nyitva marad.

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
