# Harmadik fél komponensei

🟨 **A kiadási licencaudit folyamatban van.** A PyInstaller próba-ZIP-be a Python
disztribúciók licencfájljai, a PyAV/FFmpeg runtime DLL-zár licencfájljai, az
upstream source tarballok és a conda-forge build-recept metaadatai bekerülnek. Ez még nem bizonyítja, hogy
minden terjesztési kötelezettség teljesült. A részletes bizonyítékok
és korlátok: [#25 licencaudit-riport](docs/reports/issue-25-license-audit.md).

## Saját forráskód

A RoboAssist saját forráskódjának licence [MIT](LICENSE), a döntés az
[STT-008-C #25](https://github.com/tnyari/RoboAssist/issues/25) jegyen szerepel.
Ez nem terjed ki a külön licencelt függőségekre, modellekre vagy a belőlük készült
csomagra.

## Közvetlen runtime függőségek

| Csomag / pontos verzió | Telepített metaadat | Terjesztési megjegyzés |
|---|---|---|
| [av 17.1.0](https://pypi.org/project/av/17.1.0/) | BSD-3-Clause | Artifact `py311h06a8702_0`, SHA-256 `978c663178d010a4d5bc2c76976abb96b132e8533c9e4d258f400e77935d619a`; source SHA-256 `7f1e71ff621b66253333926f948e00faae11d855b2442133c65128bca64cdeb3`, recipe commit `9fa9dab2c392eee688738ed9ecc47eb9fbfd87c5`. A recept hostja FFmpeg 8.1.1 LGPL, a külön tesztkörnyezet GPL FFmpeg-et és x264/x265-t kér; ez önmagában nem bizonyítja, hogy a kiadott PyAV artifact tartalmazza ezeket. A source archive, recept és LICENSE.txt bekerül a csomagba; a pontos licencút/#47 átvétele nyitott. |
| [faster-whisper 1.2.1](https://pypi.org/project/faster-whisper/1.2.1/) | MIT | A PyAV külön tranzitív/bundled függőség. |
| [CTranslate2 4.9.1](https://pypi.org/project/ctranslate2/4.9.1/) | MIT | A teljes tranzitív verziólista a riportban van. |
| [NumPy 2.4.6](https://pypi.org/project/numpy/2.4.6/) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Az adott wheel saját license fájljai is megőrzendők. |
| [PySide6-Essentials 6.12.0](https://pypi.org/project/PySide6-Essentials/6.12.0/) és [shiboken6 6.12.0](https://pypi.org/project/shiboken6/6.12.0/) | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | A Qt for Python közösségi kiadása LGPL/GPL feltételek alatt érhető el; a konkrét binary csomag, a Qt komponensek és a relink/source biztosítása még nem lett kiadási csomagon ellenőrizve. |
| [sounddevice 0.5.6](https://pypi.org/project/sounddevice/0.5.6/) | MIT | A PortAudio runtime saját licencszövege is bekerül a Python package licencmappájába, ha azt a pontos disztribúció tartalmazza. |
| [onnxruntime 1.32.0](https://pypi.org/project/onnxruntime/1.32.0/) | MIT | A wheelben található [ThirdPartyNotices](https://github.com/microsoft/onnxruntime/blob/main/ThirdPartyNotices.txt) állományt is meg kell őrizni a csomagban. |

Az összes további tranzitív runtime és csak fejlesztésre használt csomag verziója,
forrása és telepített licencmetaadata a [#25 auditriportban](docs/reports/issue-25-license-audit.md)
szerepel. A metaadat nem helyettesíti a wheelben vagy natív DLL-ben szállított
kódok licencének ellenőrzését.

## Qt for Python és MSVC runtime: LGPLv3 közösségi út vizsgálata

A tulajdonos az LGPLv3 közösségi út további vizsgálatát kérte; ez nem végleges
licencválasztás. A PySide6_Essentials és shiboken6 6.12.0 csomagmetaadata
LGPL/GPL alternatívákat jelez, de a ZIP Python licencbundle-jében mindkét
csomagnál csak a Qt Commercial licenc-referenciafájl található. A teljes
Community LGPL/GPL licencszöveg és a tényleges source/build átadási út nincs
lezárva.

A csomagban 5 Qt6 DLL, 20 Qt plug-in DLL, 4 PySide kötésmodul, shiboken
modulok és MSVC runtime DLL-ek vannak. A különálló Qt DLL-ek dinamikus
elrendezést mutatnak, de ez önmagában nem bizonyítja a felhasználói
relink/futtatás feltétel teljesítését. A Qt LGPLv3 út a Qt könyvtárak teljes
source átadását vagy ellenőrzött írásos forrásajánlatot, relinkelési és
telepítési információt, teljes licencszöveget és jól látható tájékoztatást
igényel a [Qt hivatalos útmutatója](https://www.qt.io/development/open-source-lgpl-obligations)
szerint. A Qt 6.12 GPL-only moduljai és a pluginok harmadik fél kódjai a
[#54 auditban](https://github.com/tnyari/RoboAssist/issues/54) maradnak
ellenőrzés alatt.

A Qt 6.12.0 qtbase forrásarchívum upstream elérhető (49 MB, SHA-256
**a951bd163c7b80fc6b8c88d7668fb56abf91c152373e13c10666763238131307**), de
jelenleg nem része a ZIP-nek. A QtSvg és a használt image-format pluginek
forrásait, a PySide pyside-setup forrásrefet és a corresponding buildláncot
még rögzíteni kell. A [PyPI PySide6-Essentials 6.12.0](https://pypi.org/project/PySide6-Essentials/6.12.0/)
release oldala csak wheel fájlokat és provenance nélküli artefaktumokat listáz.

A PySide6 és shiboken6 mappák MSVCP140/VCRUNTIME140 DLL-jei
14.44.35211.0 verziójúak és Microsoft Authenticode-aláírásuk érvényes. Ez nem
bizonyítja az adott fájlok RoboAssist általi terjesztési jogát. A
[Qt Windows telepítési útmutatója](https://doc.qt.io/qt-6.12/windows-deployment.html)
a gépről másolt egyedi MSVC runtime DLL-ek helyett a hivatalos VC Redistributable
csomagot javasolja; a Microsoft redisztribúciós feltételeit is teljesíteni kell.
Ez technikai leltár és nyitott licencvizsgálat, nem jogi minősítés.

## FFmpeg 8.1.2 forrás és buildbeállítás

A Windows x64 csomag az `ffmpeg-8.1.2-lgpl_haba0ffa_812` conda-forge artifactot
használja (SHA-256: `903a1428dddb6a7568d82e767f0c793b6abcc621bd740bdde325be1889008f08`).
A hozzá rögzített [FFmpeg 8.1.2 upstream forrásarchívum](https://ffmpeg.org/releases/ffmpeg-8.1.2.tar.gz)
SHA-256 értéke `32faba5ef67340d54724941eae1425580791195312a4fd13bf6f820a2818bf22`;
a conda-forge recept commitja `f639462076b7d4d708c8b0b5a447be6776ecf9cf`.
A recept nem-GPL ága `--disable-gpl` kapcsolót használ, a közös konfiguráció
pedig `--enable-version3`-at; a csomagolt FFmpeg bináris `-buildconf` kimenete
ezeket mutatta. A ZIP tartalmazza a receptet, az LGPLv2.1/LGPLv3 szövegeket és
az ellenőrzött `ffmpeg-8.1.2.tar.gz` source archive-ot.

A PyAV 17.1.0 rögzített conda-receptjének build hostja FFmpeg 8.1.1 LGPL,
viszont a recept külön tesztkörnyezete GPL FFmpeg-et és x264/x265 teszteket kér.
Ezek csak a recipe tesztkonfigurációját írják le; a tényleges Windows artifact
65 DLL-es leltárában x264/x265 DLL nincs, és a csomagolt FFmpeg bináris
`--disable-gpl` konfigurációt jelentett. A forrásrecept, artifact- és forráshash
a #25 riportban szerepel; a pontos licencút és source-átadás továbbra is nyitott.

Az FFmpeg és PyAV source archive-ok az `_internal/licenses/upstream-sources/`
könyvtárban vannak, hash-eiket a mappabeli README rögzíti; a hozzájuk tartozó
recept és patchfájlok az `_internal/licenses/av-runtime/packages/` alatt vannak.
Ez a csomagolt source és konfigurációs bizonyíték önmagában nem igazolja a teljes
licencfeltételek teljesítését. A #47/#25 kiadási átvétel nyitott; a DLL-lista
ellenőrzése nem jogi minősítés.

## Modellek

A [manifest](models/manifest.json) a base és small modellt immutable revisionnel,
fájlmérettel és SHA-256 hash-sel rögzíti. Mindkét modellkártya MIT licencet jelöl;
az installer a rögzített [OpenAI Whisper MIT licencszöveget](models/WHISPER_LICENSE.txt)
helyezi a telepített modell mellé. A súlyok nem kerülnek ebbe a Git repóba.

## Windows terjesztési próba állapota

- [ ] A [#54](https://github.com/tnyari/RoboAssist/issues/54) pontosítja a Qt
  Community LGPLv3 feltételeket, corresponding source/relink útját, plugin- és
  MSVC runtime terjesztési alapját.
- [ ] A #42 az exact PyAV/FFmpeg artefaktumok forrás- és receptláncát, licencszövegeit,
  hash-eit és DLL-zárát rögzíti; az x264/x265 GPL-only DLL nincs a staged runtime-ban.
- [ ] A #24 tényleges PyInstaller csomagjának Qt/ONNX Runtime/PortAudio függőségi
  fájlleltára és felhasználói indítása ellenőrzendő.
- [ ] A csomag átadási módjának teljesítenie kell a kiválasztott Qt LGPL licencút
  feltételeit, ha ilyen utat választunk.
- [x] Az aktuális zár 51 Python csomagjának uv/OSV sérülékenység-auditja 2026-11-27-én
  nem talált ismert sérülékenységet vagy adverse státuszt. Ez nem natív DLL-vizsgálat;
  a [#25 riport](docs/reports/issue-25-license-audit.md) rögzíti a módszert és korlátokat.

Az aktuális csomagpróba a `.tools/python-license-bundle` és
`.tools/av-vendor/av-runtime` leltárából készül; ezekből a spec a `licenses/`
mappát másolja a kiadási onedir könyvtárba. A külön hash-ellenőrzött source
tarballokat a `licenses/upstream-sources/` tartalmazza. A végleges terjesztési ellenőrzés,
a tiszta Windows próba és az M1 hangbenchmark még nem teljesült.

