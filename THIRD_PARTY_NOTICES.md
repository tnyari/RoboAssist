# Harmadik fél komponensei

🟨 **Előkészítés alatt.** A #16 függőségei verzió- és hash-rögzítettek a `requirements.lock` fájlban. Az alábbi lista a ténylegesen telepített wheel-metaadatok kiinduló leltára, nem végleges terjesztési licencjegyzék. A #5 modellek külön leltára lent szerepel.

A teljes ellenőrzés és projektlicenc-döntés: [STT-008-C #25](https://github.com/tnyari/RoboAssist/issues/25).

## 🟦 #16 – telepített fő komponensek

Forrás: a Windows x64 / Python 3.11.18 környezet `importlib.metadata` által olvasott
`License` / `License-Expression` mezői, 2026-11-26. A több lehetőséget felsoroló
mezőből ez a jegyzék nem választ licencet. A tranzitív és beágyazott natív
komponensek teljes notices-gyűjtése és terjesztési ellenőrzése #25 feladata.

| Csomag és verzió / forrás | Telepített metaadat licencmezője |
|---|---|
| [PySide6-Essentials 6.12.0](https://pypi.org/project/PySide6-Essentials/6.12.0/) és [shiboken6 6.12.0](https://pypi.org/project/shiboken6/6.12.0/) | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| [faster-whisper 1.2.1](https://pypi.org/project/faster-whisper/1.2.1/) | MIT |
| [CTranslate2 4.9.1](https://pypi.org/project/ctranslate2/4.9.1/) | MIT |
| [sounddevice 0.5.6](https://pypi.org/project/sounddevice/0.5.6/) | MIT; a mellékelt PortAudio külön ellenőrzendő |
| [NumPy 2.4.6](https://pypi.org/project/numpy/2.4.6/) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| [ONNX Runtime 1.32.0](https://pypi.org/project/onnxruntime/1.32.0/) | MIT License |
| [PyAV 18.1.1](https://pypi.org/project/av/18.1.1/) | BSD-3-Clause; a mellékelt FFmpeg külön ellenőrzendő |

## 🧩 Még ellenőrizendő a végleges csomaghoz

A #5 alatt a Systran többnyelvű base és small modellek helyileg telepítve és
hash-ellenőrizve lettek. A [modelljegyzék](models/README.md) és
[manifest](models/manifest.json) rögzíti a pontos immutable forrásokat, minden fájl
SHA-256 értékét és a modellkártyák MIT jelölését. Az upstream OpenAI Whisper
[MIT licencszövege](models/WHISPER_LICENSE.txt) rögzített forrásból származik,
telepítéskor a modell mellé kerül. Súly nincs Gitben. Ez nem dönt a projekt
licencéről és nem váltja ki a #25 teljes terjesztési auditját.

| Ellenőrizendő jelölt a tervből | Rögzítendő bizonyíték |
|---|---|
| PySide6 / Qt | Pontos verzió, licenc, terjesztési kötelezettségek |
| sounddevice / PortAudio, resampler | Verzió, forrás, licenc |
| faster-whisper / CTranslate2 és modell-súlyok | Külön kód- és modelllicenc, hash, letöltési forrás |
| whisper.cpp, sherpa-onnx, Silero VAD | Csak tényleges használat esetén, konkrét verzió és modell |
| PyInstaller és egyéb csomagolt függőségek | Verzió, licenc, csomagolásra vonatkozó feltételek |

A projekt saját licence még nincs eldöntve. A projektterv MIT-javaslata nem helyettesíti a tulajdonos döntését. Harmadik fél kódja és modellje a saját feltételei alatt marad.
