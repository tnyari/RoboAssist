# RoboAssist Windows csomag

Helyi, offline magyar beszédfelismerés Windows 10/11 x64 rendszeren. Az alkalmazás
nem küld hangot hálózatra, és a csomag modellsúlyt nem tartalmaz.

## Első használat

1. Bontsd ki a ZIP-et egy írható mappába.
2. Indítsd a `Start-RoboAssist.cmd` fájlt. Ez ellenőrzi a Microsoft Visual C++
   x64 futtatókörnyezetet; ha a legalább 14.52.37029.0 verzió hiányzik, a
   mellékelt, hash-rögzített Microsoft telepítő UAC-jóváhagyást kérhet. Az app
   saját futása nem igényel rendszergazdai jogot.
3. Telepíts vagy másolj át egy modellt a külön
   [modellútmutató](_internal/models/README.md)
   szerint. Az útmutató rögzíti a szükséges fájlokat és SHA-256 ellenőrzést.
4. Válassz mikrofont, modellt és nyelvet, majd
   kattints az **Indítás** gombra.

A `RoboAssistModels.exe` parancssori eszköz használata előtt futtasd egyszer a
`Prepare-RoboAssist.ps1` fájlt; hálózati modelltöltés továbbra is csak külön,
`--allow-network` kapcsolóval indítható.

A részletes használatot, adatkezelést, hibaelhárítást és eltávolítást a
[Windows felhasználói útmutató](_internal/docs/user-guide.md) írja le. A helyi WAV replay
benchmark és annak annotációs sémája a
[benchmark útmutatóban](_internal/docs/benchmark-metrics.md)
van; valós méréshez jóváhagyott, annotált hangforrás szükséges.

A RoboAssist FFmpeg könyvtárakat használ LGPLv2.1 licenc alatt. A megfelelő
FFmpeg/PyAV forrásarchívumok és a buildrecept az
`_internal/licenses/upstream-sources/` és
`_internal/licenses/av-runtime/` könyvtárban találhatók; a felületen a
**Súgó → Névjegy** ablak is megadja ezeket az útvonalakat.

A CPython 3.11.18 / OpenSSL 3.5.9 runtime eredetét, DLL-zárját és licencútját
az `_internal/licenses/python/python-runtime.json` rögzíti. A hozzá tartozó
CPython forrásarchívum, python-build-standalone buildforrás és runtime-archívum,
valamint az OpenSSL forrásarchívum az
`_internal/licenses/upstream-sources/` alatt, hash-ellenőrzötten kerül a ZIP-be.

A Qt/PySide közlemények és az upstream licencszövegek az
`_internal/licenses/qt/` mappában találhatók; az eredeti Qt/PySide
forrásarchívumok mellettük vannak az `_internal/licenses/upstream-sources/`
mappában. A Qt binary provenance, a pontos third-party linkelés és az LGPL
relink/telepítési út kiadási átvétele továbbra is nyitott.

## Qt/PySide fájlcsere · közösségi LGPL út vizsgálata

A ZIP az `_internal/licenses/qt/qt-runtime-file-lock.json` fájlban rögzíti a
csomagolt 33 Qt/PySide/shiboken DLL és PYD nevét, útvonalát, méretét és hashét.
A runtime fájlok külön állományok a `_internal/PySide6/`,
`_internal/PySide6/plugins/` és `_internal/shiboken6/` könyvtárakban. Az LGPL
közösségi út műszaki vizsgálatához a ZIP az eredeti QtBase, QtSvg, Qt Image
Formats és PySide forrásarchívumokat, valamint a belőlük kinyert licenceket és
notice-okat is tartalmazza.

A csomag dinamikus fájlelrendezése lehetővé teszi, hogy ugyanazon Qt 6.12-es
ABI-val kompatibilis, Windows x64 builddel a megfelelő DLL/PYD fájlokat azonos
relatív útvonalon cseréljék, majd a `Start-RoboAssist.cmd` fájllal indítsák az
alkalmazást. A csomagindító nem ellenőrzi a Qt/PySide runtime fájlok hashét; a
lock a kiadott változat alapállapotát rögzíti. A felhasználónak a cserebuildhez
alkalmazandó forrás-, módosítás- és buildadatokat is meg kell őriznie.

Ez előzetes technikai csereútmutató, nem végleges licencválasztás vagy jogi
megfelelőségi állítás. Módosított Qt/PySide DLL-lel/PYD-vel az alkalmazás nem
lett újraindítva; a vendor wheel binary provenance-a, a pontos third-party
closure, a GPL-only komponensek és az MSVC terjesztési jogcíme továbbra is
vizsgálat alatt áll a [#54 jegyen](https://github.com/tnyari/RoboAssist/issues/54).
A Qt hivatalos [LGPL kötelezettségei](https://www.qt.io/development/open-source-lgpl-obligations)
és [licenc FAQ-ja](https://www.qt.io/faq/qt-open-source-licensing) írják le a
source, relink, telepítési információ és felhasználói notice feltételeit.

A Microsoft VC Redistributable telepítőjének verzióját és hashét a csomag
`_internal/runtime/vc-runtime.json` fájlja rögzíti. A terjesztésre a Microsoft
Visual Studio licencfeltételei vonatkoznak; az audit a #54 jegyben követi ezt.

## Leállítás és eltávolítás

Állítsd le a felvételt az alkalmazásban, zárd be az ablakot, majd töröld a
kicsomagolt csomagmappát. A felhasználói adatkönyvtárba importált modell külön
marad; ha már nincs rá szükség, külön törölhető.

