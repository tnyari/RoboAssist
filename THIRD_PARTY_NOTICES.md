# Harmadik fél komponensei

🟨 **A kiadási licencaudit folyamatban van.** Ez a jegyzék a rögzített környezetből
és a függőségek saját metaadataiból készült kiinduló leltár. Nem bizonyítja, hogy
minden beágyazott bináris terjesztési feltétele teljesült. A részletes bizonyítékok
és korlátok: [#25 licencaudit-riport](docs/reports/issue-25-license-audit.md).

## Saját forráskód

A RoboAssist saját forráskódjának licence [MIT](LICENSE), a döntés az
[STT-008-C #25](https://github.com/tnyari/RoboAssist/issues/25) jegyen szerepel.
Ez nem terjed ki a külön licencelt függőségekre, modellekre vagy a belőlük készült
csomagra.

## Közvetlen runtime függőségek

| Csomag / pontos verzió | Telepített metaadat | Terjesztési megjegyzés |
|---|---|---|
| [av 18.1.1](https://pypi.org/project/av/18.1.1/) | BSD-3-Clause | A PyPI Windows wheel FFmpeg binárisokat is tartalmaz. A licencút és az ehhez tartozó forrásanyag tisztázásáig ne tekintsd késznek a binary redisztribúciót: [#42](https://github.com/tnyari/RoboAssist/issues/42). |
| [faster-whisper 1.2.1](https://pypi.org/project/faster-whisper/1.2.1/) | MIT | A PyAV külön tranzitív/bundled függőség. |
| [CTranslate2 4.9.1](https://pypi.org/project/ctranslate2/4.9.1/) | MIT | A teljes tranzitív verziólista a riportban van. |
| [NumPy 2.4.6](https://pypi.org/project/numpy/2.4.6/) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Az adott wheel saját license fájljai is megőrzendők. |
| [PySide6-Essentials 6.12.0](https://pypi.org/project/PySide6-Essentials/6.12.0/) és [shiboken6 6.12.0](https://pypi.org/project/shiboken6/6.12.0/) | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | A Qt for Python közösségi kiadása LGPL/GPL feltételek alatt érhető el; a konkrét binary csomag, a Qt komponensek és a relink/source biztosítása még nem lett kiadási csomagon ellenőrizve. |
| [sounddevice 0.5.6](https://pypi.org/project/sounddevice/0.5.6/) | MIT | A wheel PortAudio DLL-t is hoz; annak külön license szövegét és verzióját a riport rögzíti. |
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

## Windows terjesztés előtt szükséges

- [ ] A #42 tisztázza a PyAV/FFmpeg/x264/x265 Windows wheel pontos licencútját és a
  hozzá tartozó forrás/notices anyagokat.
- [ ] A #24 tényleges PyInstaller csomagjából össze kell gyűjteni a Qt, ONNX Runtime,
  PortAudio és a többi beágyazott komponens licenceit/notices fájljait.
- [ ] A csomag átadási módjának teljesítenie kell a kiválasztott Qt LGPL licencút
  feltételeit, ha ilyen utat választunk.
- [ ] A függőségek sérülékenység-ellenőrzése még nem adott eredményt. Ezt a
  [#25 riport](docs/reports/issue-25-license-audit.md) rögzíti.

Addig ez a fájl a forrás-repó leltára, nem a kiadás teljes és ellenőrzött
third-party notices csomagja.

