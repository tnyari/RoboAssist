# Harmadik fél komponensei

🟨 **A kiadási licencaudit folyamatban van.** A PyInstaller próba-ZIP-be a Python
disztribúciók licencfájljai, a PyAV/FFmpeg runtime DLL-zár licencfájljai és a
conda-forge build-recept metaadatai bekerülnek. Ez még nem bizonyítja, hogy
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
| [av 17.1.0](https://pypi.org/project/av/17.1.0/) | BSD-3-Clause | A Windows build a rögzített conda-forge PyAV 17.1.0 + FFmpeg 8.1.2 LGPL artefaktumot használja; pontos artifact hash, DLL-zár és receptek a csomag licencmappájában. A kiadási/licencátvétel a #42/#25-ben még nyitott. |
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

## Modellek

A [manifest](models/manifest.json) a base és small modellt immutable revisionnel,
fájlmérettel és SHA-256 hash-sel rögzíti. Mindkét modellkártya MIT licencet jelöl;
az installer a rögzített [OpenAI Whisper MIT licencszöveget](models/WHISPER_LICENSE.txt)
helyezi a telepített modell mellé. A súlyok nem kerülnek ebbe a Git repóba.

## Windows terjesztési próba állapota

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
mappát másolja a kiadási onedir könyvtárba. A végleges terjesztési ellenőrzés,
a tiszta Windows próba és az M1 hangbenchmark még nem teljesült.
