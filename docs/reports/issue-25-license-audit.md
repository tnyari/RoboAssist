# #25 projekt- és függőséglicenc-audit

**Dátum:** 2026-11-26  
**Állapot:** részleges; az M1 terjesztési/licenc kapu nyitva marad.

## 🟦 Döntés és hatókör

A tulajdonos a RoboAssist saját forráskódjának licencét **MIT**-nek választotta
([#25 döntés](https://github.com/tnyari/RoboAssist/issues/25#issuecomment-7204253707)).
A repo gyökerében levő [LICENSE](../../LICENSE) ezt rögzíti. Ez a döntés nem
helyettesíti és nem módosítja a függőségek, modellek vagy a későbbi Windows csomag
saját feltételeit.

Az ellenőrzés a Windows x64 / Python 3.11.18 virtuális környezet telepített
disztribúcióinak importlib.metadata mezőit, a pyproject.toml kötéseit, a
[requirements.lock](../../requirements.lock) hash-eit, a modell-manifestet és a helyi
natív fájlokat vette alapul. A Windows markerrel értékelt runtime függőségi zárás
**29 csomag**, a fejlesztői csoport további **15 csomagja** külön szerepel. A
licencek itt a telepített csomagmetaadat állításai; nem bizonyítják automatikusan
a wheelbe csomagolt natív komponensek feltételeit.

## 📦 Runtime függőségi zárás

Az összes sor a [PyPI](https://pypi.org/) adott verziójának csomag-metaadatára mutat.
Az összetett/licencválasztást tartalmazó kifejezések változtatás nélkül szerepelnek.

| Csomag és verzió | Telepített licencmező |
|---|---|
| [anyio 4.16.0](https://pypi.org/project/anyio/4.16.0/) | MIT |
| [av 18.1.1](https://pypi.org/project/av/18.1.1/) | BSD-3-Clause |
| [cffi 2.1.1](https://pypi.org/project/cffi/2.1.1/) | MIT-0 |
| [click 8.5.1](https://pypi.org/project/click/8.5.1/) | BSD-3-Clause |
| [colorama 0.4.6](https://pypi.org/project/colorama/0.4.6/) | BSD License classifier |
| [ctranslate2 4.9.1](https://pypi.org/project/ctranslate2/4.9.1/) | MIT |
| [faster-whisper 1.2.1](https://pypi.org/project/faster-whisper/1.2.1/) | MIT |
| [filelock 4.3.1](https://pypi.org/project/filelock/4.3.1/) | MIT |
| [flatbuffers 25.12.19](https://pypi.org/project/flatbuffers/25.12.19/) | Apache 2.0 |
| [fsspec 2026.9.0](https://pypi.org/project/fsspec/2026.9.0/) | BSD-3-Clause |
| [h11 0.16.0](https://pypi.org/project/h11/0.16.0/) | MIT |
| [hf-xet 1.8.0](https://pypi.org/project/hf-xet/1.8.0/) | Apache-2.0 |
| [httpcore2 2.16.2](https://pypi.org/project/httpcore2/2.16.2/) | BSD-3-Clause |
| [httpx2 2.16.2](https://pypi.org/project/httpx2/2.16.2/) | BSD-3-Clause |
| [huggingface-hub 2.4.0](https://pypi.org/project/huggingface-hub/2.4.0/) | Apache-2.0 |
| [idna 3.20](https://pypi.org/project/idna/3.20/) | BSD-3-Clause |
| [numpy 2.4.6](https://pypi.org/project/numpy/2.4.6/) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| [onnxruntime 1.32.0](https://pypi.org/project/onnxruntime/1.32.0/) | MIT License |
| [packaging 26.4](https://pypi.org/project/packaging/26.4/) | Apache-2.0 OR BSD-2-Clause |
| [protobuf 7.36.2](https://pypi.org/project/protobuf/7.36.2/) | 3-Clause BSD License |
| [pycparser 3.12](https://pypi.org/project/pycparser/3.12/) | BSD-3-Clause |
| [PySide6-Essentials 6.12.0](https://pypi.org/project/PySide6-Essentials/6.12.0/) | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| [PyYAML 6.0.4](https://pypi.org/project/PyYAML/6.0.4/) | MIT |
| [shiboken6 6.12.0](https://pypi.org/project/shiboken6/6.12.0/) | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| [sounddevice 0.5.6](https://pypi.org/project/sounddevice/0.5.6/) | MIT |
| [tokenizers 0.23.3](https://pypi.org/project/tokenizers/0.23.3/) | Apache Software License classifier |
| [tqdm 4.70.1](https://pypi.org/project/tqdm/4.70.1/) | MPL-2.0 AND MIT |
| [truststore 0.10.5](https://pypi.org/project/truststore/0.10.5/) | MIT |
| [typing_extensions 4.16.0](https://pypi.org/project/typing-extensions/4.16.0/) | PSF-2.0 |

## 🛠️ Csak fejlesztői zárás

Ezek a verziók a development csoport és annak környezeti függőségei; a
runtime appnak nem szánt csomagok.

| Csomag és verzió | Telepített licencmező |
|---|---|
| [ast_serialize 0.13.1](https://pypi.org/project/ast-serialize/0.13.1/) | MIT |
| [editables 0.5](https://pypi.org/project/editables/0.5/) | MIT License classifier |
| [hatchling 1.33.0](https://pypi.org/project/hatchling/1.33.0/) | MIT |
| [iniconfig 2.3.1](https://pypi.org/project/iniconfig/2.3.1/) | MIT |
| [librt 0.17.0](https://pypi.org/project/librt/0.17.0/) | MIT |
| [mypy 2.4.1](https://pypi.org/project/mypy/2.4.1/) | MIT |
| [mypy_extensions 1.2.0](https://pypi.org/project/mypy-extensions/1.2.0/) | MIT |
| [pathspec 1.1.1](https://pypi.org/project/pathspec/1.1.1/) | MPL-2.0 |
| [pluggy 1.7.0](https://pypi.org/project/pluggy/1.7.0/) | MIT |
| [Pygments 2.21.0](https://pypi.org/project/pygments/2.21.0/) | BSD-2-Clause |
| [pytest 9.2.0](https://pypi.org/project/pytest/9.2.0/) | MIT |
| [ruff 0.17.6](https://pypi.org/project/ruff/0.17.6/) | MIT |
| [tomlkit 0.15.3](https://pypi.org/project/tomlkit/0.15.3/) | MIT |
| [trove-classifiers 2026.9.21.13](https://pypi.org/project/trove-classifiers/2026.9.21.13/) | Apache Software License classifier |
| [uv 0.13.10](https://pypi.org/project/uv/0.13.10/) | MIT OR Apache-2.0 |

## 🪟 Csomagba ágyazott és natív kód

### PyAV és FFmpeg

A lock Windows x64 / CPython 3.11 környezetéhez tartozó wheelje:

| Mező | Rögzített érték |
|---|---|
| Wheel | av-18.1.1-cp311-abi3-win_amd64.whl |
| Forrás | [PyPI av 18.1.1 release](https://pypi.org/project/av/18.1.1/) |
| PyPI SHA-256 | 2f93f859e0705abe2958889ef08699db44a3ff11964e1bbe2a6beb95a680e248 |
| Release fájlméret | 29.0 MB |
| Provenance | A PyPI a kiválasztott fájlhoz nem jelez provenance attestationt |

A telepített wheel cp311-abi3-win_amd64 tagje megegyezik a rögzített
artefaktummal; a SHA-256 a [requirements.lock](../../requirements.lock) engedélyezett
hash-ei között is megtalálható. A helyi csomag DLL-jei között FFmpeg, x264 és x265
fájlnevek látszanak. Az av disztribúció BSD-3-Clause metaadata csak a PyAV
forráslicencét jelzi, nem az egész binary wheel licence.

A PyAV maintainer az upstream [#2270 beszélgetésben](https://github.com/PyAV-Org/PyAV/issues/2270#issuecomment-4594631670)
a wheel licencútját „LGPLv2.1 vagy későbbi + kereskedelmi kivételek” vagy „GPLv2 vagy későbbi”
lehetőségként írta le. A beszélgetés az [8.1.2-1 vendor build tree-re](https://github.com/PyAV-Org/pyav-ffmpeg/tree/8.1.2-1)
és az [x265 licencelésre](https://www.x265.org/#licensing) mutat; az upstream maintainer
később azt írta, hogy az x265 kereskedelmi feltételei eseti megállapodás tárgyai
([#2270, 2026-10](https://github.com/PyAV-Org/PyAV/issues/2270#issuecomment-6409103808)).

**Nyitott döntés:** az adott wheelhez tartozó x264/x265 feltételek, a megfelelő
redisztribúciós út és a teljes corresponding-source/notices csomag nincs egyértelműen
lezárva. Ebből nem következik, hogy a wheel biztosan GPL, vagy hogy kereskedelmi
használatra engedélyezett. Követés: [#42](https://github.com/tnyari/RoboAssist/issues/42).
Amíg a terjesztési út nincs bizonyítva vagy a függőség nincs kiváltva, a Windows
kiadási csomag licencellenőrzése nem teljes.

### Qt for Python

A telepített PySide6-Essentials és shiboken6 metaadata LGPL-3.0-only OR
GPL-2.0-only OR GPL-3.0-only kifejezést ad. A [Qt for Python](https://doc.qt.io/qtforpython-6.10/index.html)
közösségi kiadása LGPLv3/GPLv3, külön commercial distribution is létezik.
Az [LGPL használat feltétele](https://doc.qt.io/qt-6/licensing.html), hogy a választott
licenc feltételei teljesüljenek. A jövőbeli PyInstaller csomagban a pontos Qt modulokat,
licencfájlokat és az alkalmazandó forrás/újralinkelési módot ellenőrizni kell.
Ez nem történt meg teljes kiadási artefaktumon; #24 és #25 nyitott.

### PortAudio és ONNX Runtime

A sounddevice wheel MIT metaadata önmagában nem azonosítja a hozzá csomagolt
PortAudio DLL licencét. A helyi wheelben a PortAudio bináris jelen van; upstream
license forrása a [PortAudio repó](https://github.com/PortAudio/portaudio/blob/master/LICENSE.txt).
Végleges csomagba a hozzá tartozó license/notice fájlt is be kell tenni.

Az ONNX Runtime Python wheel MIT metaadatot és külön
[ThirdPartyNotices.txt](https://github.com/microsoft/onnxruntime/blob/main/ThirdPartyNotices.txt)
fájlt tartalmaz. A fájl megőrzése és a pontos csomagverzióval való egyeztetése
a #24 csomagolási ellenőrzés része.

## 🗣️ Modellek

| ID | Forrás / immutable revision | Manifestben lévő fájlhash-ek | Kártyalicenc |
|---|---|---|---|
| base-multilingual | [Systran/faster-whisper-base](https://huggingface.co/Systran/faster-whisper-base/tree/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66), ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66 | [manifest](../../models/manifest.json) | MIT |
| small-multilingual | [Systran/faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small/tree/536b0662742c02347bc0e980a01041f333bce120), 536b0662742c02347bc0e980a01041f333bce120 | [manifest](../../models/manifest.json) | MIT |

A rögzített [OpenAI Whisper licencszöveg](../../models/WHISPER_LICENSE.txt)
SHA-256 értéke és forrása a manifestben található. A súlyokat nem commitoljuk.
A base modell hash-ellenőrzése helyben, hálózat nélkül sikerült a rögzített
revisionen; ez nem pontosságmérés vagy teljes modell-audit.

## 🔍 Sérülékenység-ellenőrzés

**Eredmény nem készült.** A repository requirements.lock fájlja pip stílusú,
uv.lock nincs. A telepített uv audit a projekt lockfájlját igényli és hálózatra
csatlakozik. Az izolált, figyelmen kívül hagyott auditmásolat zárolása offline módban
azért nem sikerült, mert az av 18.1.1 nem volt a cache-ben; a hálózatos
uv lock próbát a környezet PyPI felé menő kapcsolatát elutasító proxy szakította meg
(tcp connect error / os error 10061). Az audit parancs nem jutott el
sérülékenységi adatbázishoz, ezért nincs pass/fail vagy „nincs ismert hiba” állítás.

## ⏭️ M1 előtt nyitva marad

- [ ] [#42](https://github.com/tnyari/RoboAssist/issues/42): a PyAV Windows wheel és
  a beágyazott FFmpeg/kodek licencútja, forrásai és notices anyagai.
- [ ] #24: a pontos PyInstaller kiadás, Qt licencút, natív/third-party notices
  és telepítési út ellenőrzése.
- [ ] [#43](https://github.com/tnyari/RoboAssist/issues/43): sérülékenység-audit
  hálózati OSV/PyPI hozzáféréssel, a ténylegesen használt hash-rögzített verziókra.
- [ ] Szükséges license fájlok/notices tényleges beillesztése és ellenőrzése a
  csomagban.

Ezek maradása miatt a #25 és az [M1 kapu #10](https://github.com/tnyari/RoboAssist/issues/10)
Open állapotban marad. Ez a riport licencforrásokat és implementációs követelményeket
rögzít, nem jogi vélemény.

