# Qt/PySide licenc- és attribution bundle audit

**Ellenőrzött artifact:** `RoboAssist-0.1.0-windows-x64.zip`  
**SHA-256:** `7c066f60e55163ab5f193dfc3e762f9e8ab1b493232376c9bb616761eec37301`  
**GitHub követés:** [#54](https://github.com/tnyari/RoboAssist/issues/54), a #25 audit része.

## ✅ Mit tartalmaz a csomag

- Az `_internal/licenses/upstream-sources/` mappában négy hash-ellenőrzött
  Qt/PySide 6.12.0 source archive található.
- Az `_internal/licenses/qt/` mappában **174** upstream licenc-,
  copyright-, attribution- és notice-fájl szerepel, az eredeti forrásútvonalat,
  fájlméretet és SHA-256 értéket rögzítő `manifest.json` mellett.
- A manifest külön indexeli a négy forrásmodulból kinyert **76**
  `qt_attribution.json` fájlt. Ezek a Qt source komponens-, verzió-, license ID-
  és konfigurációs információi; a vendor binary összeállítását nem bizonyítják.
- A bundle tartalmazza a QtBase, QtSvg, Qt Image Formats és PySide forráscsomagok
  `LICENSES/` fájljait; köztük az LGPL-3.0-only, GPL-2.0-only és GPL-3.0-only
  szövegeket.
- A képkodekek upstream attributionjei és notice-ai is könnyen megtalálhatók:
  - `qjpeg.dll` → libjpeg-turbo 3.2.0. A Qt source szerint `-system-libjpeg`
    nélkül használja; a bundle tartalmazza a libjpeg-turbo LICENSE, IJG license,
    README.ijg, copyright és `qt_attribution.json` fájlját.
  - `qtiff.dll` → libtiff 4.7.2. A Qt source szerint rendszer-lib nélkül
    használja; a bundle tartalmazza a libtiff license/copyright és attribution
    fájlját.
  - `qwebp.dll` → libwebp 1.6.0. A Qt source szerint rendszer-lib nélkül
    használja; a bundle tartalmazza a COPYING és attribution fájlját.

Az upstream pluginfeltételek és verziók a source archive-ok
`src/3rdparty/*/qt_attribution.json` fájljaiból származnak. A bundle
`manifest.json` a fenti útvonalakat és a hozzájuk tartozó archive hashét rögzíti.

## 🔍 Ellenőrzési módszer

A `scripts/prepare-qt-license-bundle.py` a négy archive teljes SHA-256 hashét
ellenőrzi, majd a megadott archívumgyökéren belüli licenc- és notice-fájlokat
olvassa ki. Elutasítja az archive gyökerétől eltérő útvonalat, a `..` útvonal-
elemet, a hiányzó kötelező fájlokat és a váratlan
archive hash-t. A staging könyvtár kizárólag a workspace `.tools/qt-license-bundle`
mappája lehet. A PyInstaller spec ezt a fát az `_internal/licenses/qt/` alá
csomagolja.

A nem regular tar tagokat (például symlinket) a kinyerő kihagyja; nem bontja ki
őket a staging könyvtárba.

A tényleges ZIP-ből újraszámoltam a ZIP sidecar hashét, a manifestben felsorolt
174 licenc-/notice-fájl hashét és méretét, mind a 76 source attribution fájl
hashét, valamint mind a 33 rögzített Qt runtime DLL/PYD fájl hashét és méretét.
A ZIP 1 427 bejegyzést tartalmaz. Benne van mind a négy Qt/PySide source archive;
a runtime lock eltéréseinek száma nulla. A ZIP-ben 3 `.exe` van (két alkalmazás és a Microsoft VC
Redistributable installer); modellsúly nincs benne.

## ⚠️ Nyitva maradó feltételek

Ez az audit a hash-zárt upstream source archívumok szövegeinek jelenlétét és
integritását bizonyítja. **Nem bizonyítja**, hogy a PyPI PySide/Qt vendor
binárisai ezekből a source tree-kből készültek, hogy a felsorolt harmadik fél
kód valóban be van linkelve a csomagolt pluginokba, vagy hogy valamely GPL-only
komponens nem került a csomagba. A source `qt_attribution.json` feltételes
konfigurációs információ; a vendor build opcióit nem tartalmazza.

Az LGPL út a relinkelhető alkalmazás biztosítását, a szükséges telepítési
információt és felhasználói tájékoztatást is igényel. A binárisok provenance-a,
a pontos third-party closure, a felhasználói relink/install út, a Microsoft VC
Redistributable terjesztési jogcíme és az alkalmazandó licencút kiadási
átvétele továbbra is nyitott a #54 és #25 jegyen. Ez forrás- és fájlleltár,
nem jogi minősítés.

## 🧪 Ténylegesen futtatott ellenőrzések

- A bundle generálása négy hash-zárt archive-ból: **174 fájl**; közte 76 source attribution dokumentum.
- `ruff check scripts/prepare-qt-license-bundle.py`: sikeres.
- `ruff format --check scripts/prepare-qt-license-bundle.py`: sikeres.
- Offline PyInstaller release build: sikeres.
- A release ZIP sidecar hash és tartalom: **1 427 bejegyzés**, hash egyezik.
- Qt licenc-/notice fájlok: **174/174** hash és méret egyezik.
- Qt source attribution fájlok: **76/76** hash egyezik.
- Qt runtime lock: **33/33** DLL/PYD hash és méret egyezik.
- A csomagolt `RoboAssistModels.exe --help` kilépési kódja **0**.
- Tiszta Windows gépes telepítés/eltávolítás: nem futott, mert a felhasználó
  jelezte, hogy jelenleg nincs elérhető tesztgép vagy VM.


## 🧭 Kiegészítő hivatalos licencforrás-ellenőrzés · 2026-11-27

- A Qt for Python dokumentációja a közösségi disztribúciót LGPLv3/GPLv3 licencútként, a Commercial változatot külön kiadásként írja le. A PySide6-Essentials projekt PyPI-oldala azt jelzi, hogy a PyPI a telepítés ajánlott forrása, és a wheel-tartalom mindkét licencelési esetre használható. Ez alátámasztja, hogy a wheelben található Commercial hivatkozás önmagában nem bizonyít Commercial-only licencet.
- A PyPI 6.12.0 release oldalán a Windows x86-64 wheel szerepel, a release-hez provenance attesztáció nincs; az oldalon source distribution sem szerepel. Így a kiadott wheel eredetének és buildbeállításainak kriptográfiai bizonyítéka továbbra sem áll rendelkezésre.
- A Qt hivatalos LGPL útmutatója teljes corresponding source vagy írásos forrásajánlatot, dinamikus linkelési/relinkelési lehetőséget, a módosított könyvtár futtatásához szükséges eszközöket és telepítési információt, teljes licencszöveget és jól látható tájékoztatást sorol fel. Ezek kiadási feltételek; Qt útmutatója maga is egyedi jogi minősítést nem vállal.
- **Értékelés:** az LGPLv3/GPLv3 Community licencút elérhető a Qt for Python termékhez, de a jelen csomagolt PySide/Qt binary closure, az esetleges GPL-only komponensek, a wheel–source build megfeleltetése, valamint a felhasználói relink/install eljárás nincs igazolva. A #54 checklist nyitva marad.

Források: [Qt for Python – Commercial Use / Community Edition](https://doc.qt.io/qtforpython-6/commercial/index.html), [PySide6-Essentials 6.12.0 release és licensing metaadat](https://pypi.org/project/PySide6-Essentials/6.12.0/), [Qt – LGPL/GPL kötelezettségek](https://www.qt.io/development/open-source-lgpl-obligations), [Qt Open Source Licensing FAQ](https://www.qt.io/faq/qt-open-source-licensing).


## 🟩 Friss artifact-ellenőrzés · 2026-11-27

- A javított Start/Stop átmeneti állapotú UI-val az offline `scripts/build-app.ps1 -Offline` build sikeres; új ZIP SHA-256: `7c066f60e55163ab5f193dfc3e762f9e8ab1b493232376c9bb616761eec37301`.
- Statikus ellenőrzés: 1 427 bejegyzés, 108 DLL, 3 EXE, modellsúly nélkül; 6 upstream source archive. A Qt licenc/notice fájlok 174/174, attribution dokumentumok 76/76, Qt runtime DLL/PYD lock 33/33 méret+SHA egyezés.
- A csomagolt `RoboAssist.exe --help` és `RoboAssistModels.exe --help` kilépési kódja egyaránt 0. Ez parancssori smoke; a grafikus felületet és mikrofont nem indítottam el.
- A Windows CI [#107](https://github.com/tnyari/RoboAssist/actions/runs/45994614436) sikeres a [92b07d05d4ef](https://github.com/tnyari/RoboAssist/commit/92b07d05d4ef41f9358c06cdee021a7d50ff6c03) kód+teszt headen. A helyi UI csomagtesztek **6 passed**, Ruff lint/format és mypy (35 source files) sikeres.
- A tiszta Windows 10/11 install/start/stop/uninstall átvétel továbbra sem futott, mert külön tesztgép/VM nem áll rendelkezésre.


## 🔬 Qt plugin-források SPDX-mintavétele · 2026-11-27

A ZIP-be csomagolt Qt platform-, stílus-, TLS-, hálózati információs, SVG- és
képkodek pluginekhez tartozó Qt source könyvtárakban a `.cpp`, `.h` és `.c`
fájlok SPDX fejlécét ellenőriztem. A vizsgált source archive-ok SHA-256 értéke:

- QtBase: `a951bd163c7b80fc6b8c88d7668fb56abf91c152373e13c10666763238131307`
- Qt Image Formats: `0943132b5db8de6b6a7f1d162682173e8763c7ed94e80fd39113292845f67762`
- QtSvg: `e4ab39534ec97987b1b9b60ef7f4d3253d5912a69f8c713a01753174a4029331`

| Forrásmodul és plugin könyvtár | Fájl | Egységes SPDX-kifejezés |
|---|---:|---|
| QtBase: Windows platform | 110 | `LicenseRef-Qt-Commercial OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` |
| QtBase: offscreen, minimal, Direct2D platform | 36 | ugyanaz |
| QtBase: modern Windows stílus | 10 | ugyanaz |
| QtBase: Network List Manager | 3 | ugyanaz |
| QtBase: Schannel, OpenSSL, cert-only TLS | 28 | ugyanaz |
| QtBase: JPEG, GIF, ICO képkodek | 9 | ugyanaz |
| Qt Image Formats: ICNS, TGA, TIFF, WBMP, WebP | 17 | ugyanaz |
| QtSvg: SVG kép- és ikon pluginek | 6 | ugyanaz |
| **Összesen** | **219** | **minden fájlban megtalálható** |

Ez bizonyítja, hogy a forrásrelease e fájljaihoz az LGPLv3 választási lehetőség
is közzé van téve; nem jelöl ki automatikusan egyetlen alkalmazandó licencet.
Nem azonosítja, hogy a PyPI wheelben lévő DLL/PYD/plugin binárisok melyik
licencválasztással és milyen buildbeállítással készültek, és önmagában nem zárja
ki a GPL-only buildösszetevőt vagy harmadik fél kódját. Ezért a #54 első három
licencátvételi feltétele továbbra is nyitott.

**Ténylegesen futtatott ellenőrzés:** a hash-zárt QtBase, Qt Image Formats és
QtSvg archive-okban a felsorolt 219 plugin-forrás `.cpp`/`.h`/`.c` SPDX
fejléceinek automatizált összesítése; az összes fájlban ugyanaz az alternatív
licenckifejezés található, fejléc nélküli fájl nem volt. Ez forrásfájl-minta és
nem bináris provenance- vagy jogi megfelelőségi vizsgálat.

