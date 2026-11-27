# #25 projekt- és függőséglicenc-audit

**Frissítve:** 2026-11-27  
**Állapot:** részleges; a licencválasztás rögzítve, a Windows terjesztési átvétel nyitva.

## 🟦 Saját projektlicenc

A tulajdonos a feladat során **MIT** licencet választott a RoboAssist saját
forráskódjához. A [LICENSE](../../LICENSE) és a [harmadik fél közleményei](../../THIRD_PARTY_NOTICES.md)
ezt rögzítik. A választás nem vonatkozik a függőségekre vagy modellekre, és nem
minősíti a teljes Windows csomag terjesztési feltételeit.

## 🔍 Vizsgálati hatókör

Az audit a [Python hash lockra](../../requirements.lock), a
[conda-forge Windows x64 lockra](../../conda-av-win64.lock), a modellek
[verzió- és hash-manifestjére](../../models/manifest.json), a PyInstaller build
specifikációjára és az elkészült licenc-bundle leltárára támaszkodik. A build a
függőségek licenceit és upstream közleményeit a csomag `licenses/` könyvtárába
másolja. Ez reprodukálható leltár, nem jogi vélemény.

## 📦 PyAV és FFmpeg runtime

A Windows x64 / CPython 3.11 runtime a rögzített conda-forge csomagokat használja.

| Csomag | Build | Licencmetaadat | Artifact SHA-256 |
|---|---|---|---|
| `av` 17.1.0 | `py311h06a8702_0` | BSD-3-Clause | `978c663178d010a4d5bc2c76976abb96b132e8533c9e4d258f400e77935d619a` |
| `ffmpeg` 8.1.2 | `lgpl_haba0ffa_812` | LGPL-2.1-or-later | `903a1428dddb6a7568d82e767f0c793b6abcc621bd740bdde325be1889008f08` |

A teljes natív környezet **98 hash-rögzített conda-forge artifactból** áll. A
stage-elt DLL-zár 65 fájl, összesen 123,033,664 bájt; a manifest a fájlok
hash-eit és a 44 csomagtulajdonos licenc- és buildmetaadatait rögzíti. A pontos
zárhoz és buildhez tartozó licencszövegek, FFmpeg-receptek és manifest a
`licenses/av-runtime/` könyvtár része. A PE importzár vizsgálata nem talált
x264/x265 GPL-only DLL-t; ez a DLL-listára vonatkozó ellenőrzés, nem codec- vagy
terjesztési jogi minősítés.

### Rögzített FFmpeg 8.1.2 forrás és buildkonfiguráció

A lockolt `ffmpeg-8.1.2-lgpl_haba0ffa_812` conda-forge recept az upstream
[FFmpeg 8.1.2 forrásarchívumot](https://ffmpeg.org/releases/ffmpeg-8.1.2.tar.gz)
rögzíti (`SHA-256: 32faba5ef67340d54724941eae1425580791195312a4fd13bf6f820a2818bf22`).
A recept a conda-forge `ffmpeg-feedstock` `f639462076b7d4d708c8b0b5a447be6776ecf9cf`
commitjéből származik. A `recipe/build.sh` a `license_family != gpl` ágon
`--disable-gpl` kapcsolót ad át; a közös konfiguráció `--enable-version3`-at
állít be. Az elkészült FFmpeg 8.1.2 bináris `-buildconf` kimenete ugyanezeket a
kapcsolókat tartalmazza. A próbacsomag licencmappájában ellenőriztem a
`recipe/meta.yaml`, `recipe/build.sh`, `COPYING.LGPLv2.1` és `COPYING.LGPLv3`
bejegyzéseket.

Az FFmpeg 8.1.2 és PyAV 17.1.0 upstream source archive-ok a Windows ZIP-be
kerülnek (`_internal/licenses/upstream-sources/`); a source SHA-256 értékek és
URL-ek ottani README-ben vannak. A conda-forge build recipe-k, patchfájlok,
artifact metaadatok és licencszövegek `_internal/licenses/av-runtime/packages/`
alatt találhatók. Ez a csomagolt source és konfigurációs bizonyíték önmagában
nem igazolja a teljes licencfeltételek vagy a relinkelési út megfelelőségét.
Ezek a #47/#25 kiadási átvételi feltételei maradnak.

A korábbi PyPI `av` 18.1.0 kiadás yanked státuszt kapott memóriakorrupciós hiba
miatt. A hiba javítását a [PyAV 18.1.1 kiadási jegyzete](https://github.com/PyAV-Org/PyAV/releases/tag/v18.1.1)
rögzíti. Az aktuális csomag a conda-forge PyAV 17.1.0 LGPL FFmpeg buildjére
állt át; nem használja a korábbi PyAV wheelt.

### PyAV 17.1.0 forrás és recipe

A Windows artifact `av-17.1.0-py311h06a8702_0` SHA-256 értéke
`978c663178d010a4d5bc2c76976abb96b132e8533c9e4d258f400e77935d619a`. A recept az
[av 17.1.0 source archive](https://pypi.org/packages/source/a/av/av-17.1.0.tar.gz)
fájlt használja (`SHA-256: 7f1e71ff621b66253333926f948e00faae11d855b2442133c65128bca64cdeb3`),
a conda-forge `av-feedstock` receptcommitja `9fa9dab2c392eee688738ed9ecc47eb9fbfd87c5`.
A rögzített `recipe/meta.yaml` szerint a build host FFmpeg 8.1.1 LGPL
(`lgpl_h914209b_804`), míg az artifact futásidejű függősége `ffmpeg >=8.1.1,<9`;
a RoboAssist ZIP-ben lévő runtime FFmpeg 8.1.2 LGPL.

Ugyanennek a receptnek a külön tesztkörnyezet `ffmpeg * gpl*` függőséget kér,
és az x264/x265 kodekek jelenlétét ellenőrzi. Ez a recept tesztkörnyezetére
vonatkozó adat; önmagában nem bizonyítja, hogy az elkészült PyAV artifact GPL
kodeket linkelt. A tényleges csomag 65 DLL-es zárában nincs x264/x265 DLL, és a
csomagolt FFmpeg 8.1.2 `-buildconf` kimenete `--disable-gpl`-t mutat. A ZIP az
upstream PyAV source archive-ot, conda recept `meta.yaml` fájlját, patchfájlokat
és BSD-3-Clause `LICENSE.txt`-t tartalmazza. E bizonyítékok mellett is nyitva
marad a pontos PyAV/FFmpeg licencút; ez nem jogi minősítés.

## 🐍 Python disztribúciók és ismert sérülékenységek

A csomag **51 Python-disztribúció** licenc- és közleményfájlját, valamint a
név/verzió/licencmetaadatot tartalmazó manifestet állítja elő. A 2026-11-27-i
`uv audit` a hash lockból feloldott 51 Python csomagnál nem talált ismert
sérülékenységet vagy kedvezőtlen projektstátuszt. Ez az eredmény a Python
csomagnevekre és verziókra terjed ki; a 98 natív conda artifact külön OSV-auditja
nem történt meg.

A fő közvetlen komponensek licenceit és nyitott terjesztési kérdéseit a
[THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md) sorolja fel. Különösen:

- A PySide6 és a shiboken6 csomagmetaadata LGPL/GPL alternatívákat jelez; a
  választott Qt licencút, relink/source átadás és a végső binary csomag feltételei
  még kiadási átvételt igényelnek.
- PortAudio, ONNX Runtime és egyéb natív összetevők közleményeit a tényleges
  PyInstaller ZIP-ben kell ellenőrizni, nem csak a Python projektmetaadatból
  következtetni.
- A két rögzített Whisper modell külön, manifestben rögzített modellrevision és
  SHA-256 mellett kerül importálásra; a csomag nem terjeszti a modell súlyait.

### PySide6/Qt 6.12 közösségi LGPLv3 út vizsgálata

A tulajdonos a közösségi LGPLv3 út vizsgálatát kérte; ez nem végleges licencválasztás.
A próbacsomag PySide6_Essentials és shiboken6 6.12.0 metadata LGPL/GPL
alternatívákat jelez, a két licencmappában viszont csak
LicenseRef-Qt-Commercial.txt található. A csomagolt fájllista 5 Qt6 DLL-t,
20 plug-in DLL-t, 4 PySide .pyd modult és shiboken bindingfájlokat tartalmaz.
A végleges ZIP alatti összes Qt/PySide/shiboken DLL/PYD fájl pontos listája,
mérete, PE verziója és SHA-256 értéke a [Qt runtime lockban](qt-runtime-file-lock.json)
szerepel; ez 33 bináris fájlt és a hivatalos VC Redistributable minimumverzió/hash
adatait rögzíti. Ez egészíti ki az [#54 aljegyen](https://github.com/tnyari/RoboAssist/issues/54)
vezetett licencvizsgálatot.

A PySide .pyd modulok és Qt Qt6*.dll fájlok különállóak, így a csomag
dinamikus elrendezésű; ez önmagában nem bizonyítja a felhasználói relinkelést
vagy az LGPL feltételek teljesítését. A Qt hivatalos tájékoztatója corresponding
source átadást vagy írásos forrásajánlatot, módosított könyvtárral relinkelési
és futtatási lehetőséget, telepítési információt, teljes LGPL szöveget és
jól látható tájékoztatást ír le. A Qt Company nem ad jogi tanácsot a megfelelőség
egyedi minősítéséről. Forrás: [Qt LGPLv3 kötelezettségek](https://www.qt.io/development/open-source-lgpl-obligations),
[Qt licensing FAQ](https://www.qt.io/faq/qt-open-source-licensing).

Az exact QtBase, QtSvg, Qt Image Formats és PySide 6.12.0 upstream
source archive-ok letöltve és hash-ellenőrizve; az offline csomagbuild
mind a négyet az `_internal/licenses/upstream-sources/` könyvtárba teszi.
A PySide forrásarchívum tartalmazza a teljes `LICENSES/LGPL-3.0-only.txt`
licencszöveget. A PyPI PySide6-Essentials 6.12.0 release-oldalán öt wheel
szerepel, source distribution és provenance attesztáció nélkül. A Qt for Python
buildútmutató a pyside-setup forrásrepót és azonos verziójú Qt telepítést
használja; a jelenlegi wheel-hashből nem áll elő forrásból buildelt binary
chain. Források: [QtBase 6.12.0 source archive](https://download.qt.io/archive/qt/6.12/6.12.0/submodules/qtbase-everywhere-src-6.12.0.tar.xz),
[PyPI artifactlista](https://pypi.org/project/PySide6-Essentials/6.12.0/),
[Qt for Python buildútmutató](https://doc.qt.io/qtforpython-6/building_from_source/index.html).

A hivatalos forrásrepók pontos 6.12.0 tagjei is azonosíthatók: a
[pyside-setup v6.12.0](https://github.com/pyside/pyside-setup/tree/f50facb83fc3dc5f3240c854668c7a6dd93871b2)
commitja `f50facb83fc3dc5f3240c854668c7a6dd93871b2`, a
[qtbase](https://github.com/qt/qtbase/tree/025bdad181de241e81bf853c8a2d7bf3d19261a9)
commitja `025bdad181de241e81bf853c8a2d7bf3d19261a9`, a
[qtsvg](https://github.com/qt/qtsvg/tree/883a58532078d003cefef0a549bfe9f885ce41f5)
commitja `883a58532078d003cefef0a549bfe9f885ce41f5`, a
[qtimageformats](https://github.com/qt/qtimageformats/tree/dc13f2fbff1d579cfb2eb2d9092e3563b4d05b8e)
commitja `dc13f2fbff1d579cfb2eb2d9092e3563b4d05b8e`. A GitHub API ezeket
annotált, unsigned tagekhez rendeli; ez pontos source ref, de nem bizonyíték arra,
hogy a csomagolt wheelek/binarisok ezekből a fájlokból készültek. A source tree-k
archívumai a ZIP-be kerülnek; a vendor build konfiguráció, toolchain és binary
provenance továbbra sincs a ZIP-ben.

### MSVC runtime – hivatalos Redistributable csomagút

A fejlesztői PySide6/shiboken6 mappák 14.44.35211.0, az `av.libs` 14.52.37029.0,
a PyInstaller környezetből bekerülő gyökér DLL-ek 14.51.36231/36247.0, a NumPy
wheel pedig `numpy.libs/msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll` néven
14.40.33810.0 runtime-példányt hordoz. Ezek a fejlesztői inputok fájlverzió és
aláíró alapján kerültek leltárba; az aláírás önmagában nem terjesztési engedély.
A NumPy wheel `DELVEWHEEL` és `RECORD` állománya igazolja, hogy a hash-elt
MSVCP DLL a wheel része, és a két NumPy `.pyd` importálja. A build most egy
reprodukálható, csak `.tools/` alatti NumPy overlay-t készít: az ellenőrzött
2.4.6 wheel két érintett `.pyd` importnevében a privát, hash-elt DLL nevét a
szokásos `msvcp140.dll` névre cseréli, frissíti az overlay `RECORD`-ját, és a
privát DLL-t kihagyja. Az eredeti wheel és a fejlesztői virtuális környezet
változatlan marad. Ez technikai csomagolási megoldás; a Microsoft runtime
terjesztési feltételeinek átvételét nem zárja le.

A Qt 6.12 Windows deployment útmutatója a hivatalos Microsoft VC Redistributable
telepítőt várja release alkalmazásnál; a fordító gépéről átmásolt egyedi runtime
DLL-eket nem szabad közvetlenül szállítani. A Microsoft szerint a v14 telepítő
verziója legalább olyan friss legyen, mint az alkalmazáshoz használt Build Tools,
és a Redistributable terjesztése licencelt Visual Studio felhasználókra, illetve
a Visual Studio licencfeltételeire korlátozott.

Az új offline ZIP (`1b9522deec6168d68f21068c22038bee0159f4f38f4df7d31ddb6f0151ddf43b`)
ezért a Microsoft hivatalos `https://aka.ms/vc14/vc_redist.x64.exe` útvonalán
letöltött, 14.52.37029.0 x64 telepítőt tartalmazza
(`_internal/runtime/vc_redist.x64.exe`; SHA-256
`9c02c9ed120f671b900e6b9471d890e3b2414117a7e53f4ae2e855466fa2b7c9`, érvényes
Microsoft Authenticode aláírás). A PyInstaller build a szokásos MSVCP/VCRUNTIME,
`concrt140`, `vccorlib140` és UCRT runtime DLL-neveket kiszűri; root
`Start-RoboAssist.cmd` / `Prepare-RoboAssist.ps1` ellenőrzi a registry runtime
verziót, hash-t és aláírást, majd csak hiányzó/régebbi futtatókörnyezetnél kér
UAC-jóváhagyást. A ZIP-ből a NumPy privát, hash-elt runtime DLL hiányzik; a
csomagolt `RoboAssistModels.exe --help` parancs sikeresen lefutott ezzel a
NumPy builddel, de ez nem helyettesíti tiszta gépes ellenőrzést. A csomag
statikus leltára 1 230 bejegyzés, 108 DLL, két
alkalmazás-EXE és egy VC Redistributable telepítő (összesen három `.exe` fájl);
app-local szabványos MSVC/UCRT DLL és
Windows API-set contract fájl nincs benne; a modell-súlyok hiányoznak.

A Microsoft telepítő helyi verziója 14.52.37029.0, aláírása érvényes; hash-e
egyezik a ZIP-be csomagolt fájllal. A fejlesztői gép registry runtime-ja viszont
14.51.36247.0, tehát a csomag UAC útvonala ezen a gépen telepítene. A friss
`RoboAssist.exe` nem indult el újra, és tiszta Windows teszt nem történt; a
lokális runtime megléte nem helyettesíti a #24 clean-install próbáját. A
tesztkörnyezetben jelenleg nincs elérhető tiszta Windows gép vagy VM.

Források: [Qt Windows deployment](https://doc.qt.io/qt-6.12/windows-deployment.html),
[Microsoft VC fájlok terjesztése](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files),
[Microsoft v14 letöltés és minimumverzió](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist),
[Visual Studio 2022 REDIST-lista](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution).

A Qt DLL-ek, pluginek, PySide corresponding source/buildlánc, a tényleges
relink/telepítési út és az MSVC runtime átadása továbbra sincs lezárva; a
vizsgálatot a [#54 aljegy](https://github.com/tnyari/RoboAssist/issues/54)
követi. Ez a rész nem jogi minősítés.

## ✅ Ellenőrzések és korlátok

- ✅ A `requirements.lock` SHA-256-tal rögzíti a Python wheel artefaktumokat.
- ✅ A `conda-av-win64.lock` 98 explicit artifact URL-t és SHA-256-ot rögzít.
- ✅ A stage manifest az FFmpeg 8.1.2 buildjét LGPL-2.1-or-laterként jelöli, és
  rögzíti a DLL-zárat; x264/x265 DLL nincs benne.
- ✅ A csomagolt FFmpeg 8.1.2 és PyAV 17.1.0 source archive, buildrecept,
  patchfájlok, forrás URL/SHA-256, `--disable-gpl` buildág és tényleges bináris
  `-buildconf` egyezése ellenőrizve; a licencút teljes átvétele nyitott.
- ✅ A ZIP Microsoft VC Redistributable 14.52.37029.0 installerének Authenticode,
  verzió-, SHA-256- és csomaghash-ellenőrzése sikeres; a gyakori app-local
  MSVC/UCRT DLL-ek és a NumPy privát hash-elt runtime DLL-je kiszűrve. A build
  NumPy overlay importnév-módosítása és a csomagolt modell-CLI `--help`
  ellenőrzése sikeres. A Redistributable terjesztési jogosultsága és a tiszta
  gépes indítás továbbra sincs lezárva.
- ✅ A végleges ZIP-ből olvasott modellmanifest a base/small modellek rögzített
  revisionjét, fájlméretét és SHA-256 értékeit tartalmazza; mindkét rögzített
  model card MIT licencet jelöl. A csomagolt `WHISPER_LICENSE.txt` SHA-256-a
  (`b5d65a59060e68c4ff940e1eddfa6f94b2d68fdf58ed7f4dd57721c997e35e9d`) egyezik
  mindkét manifestbejegyzéssel. A runtime manifest forrás-URL-je, minimumverziója
  és hash-e egyezik a ZIP-ben lévő VC Redistributable telepítővel; modellsúly
  nincs a kiadási ZIP-ben.
- ✅ A `uv audit` 51 Python csomagra ismert sérülékenységet vagy kedvezőtlen
  projektstátuszt nem jelzett; a natív conda closure nem tartozott a vizsgálatba.
- ⏳ A ZIP-ben található Qt, ONNX Runtime, PortAudio és minden tranzitív notice
  tényleges átvétele a #24/#54 csomagolási és licencjegyekben marad nyitva.
- ⏳ A #24 tiszta Windows 10/11 gépes install/start/stop/uninstall próbája nem
  történt meg. A #28 külön fejlesztői bootstrap ellenőrzés, nem az M1 csomagpróba.
- ⏳ A magyar hangbenchmark (#21/#10) jóváhagyott, annotált hangforrásra vár;
  teljesítmény- vagy pontosságállítás nem készült.

A #25 és az M1 kapu (#10) maradjon nyitva, amíg a terjesztési/licencátvétel és a
M1 többi elfogadási feltétele nem teljesül.

