# Fejlesztői indulás

## 🟦 Környezet

Windows 10 22H2 / Windows 11 **x64**, x64 Windows PowerShell 5.1 vagy újabb.
A rögzített interpreter **CPython 3.11.18**, az eszköz **uv 0.13.10**.
A setuphoz nem kell előtelepített Python, PATH-módosítás vagy venv-aktiválás.
A telepítő a repó `.tools/` és `.venv/` könyvtárába dolgozik; ezeket ne commitold.

Az OS Microsoft Visual C++ v14 x64 futtatókörnyezete szükséges lehet a natív
csomagokhoz. DLL-betöltési hiba esetén a [Microsoft hivatalos x64 runtime-ját](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
telepítsd; ezt a setup nem telepíti rendszerjogosultsággal. A tiszta OS-ellenőrzés
nyitott feladat: [#28](https://github.com/tnyari/RoboAssist/issues/28).

## 🧭 Telepítés

A repó gyökerében, x64 PowerShellből:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-dev.ps1
```

Ez a parancs explicit, hálózatos **fejlesztői telepítés**:

1. A PyPI-ról letölti az uv 0.13.10 Windows x64 wheeljét, ellenőrzi a scriptbe
   rögzített SHA-256-ot, majd kicsomagolja a `.tools/uv-bootstrap/` alá.
2. Az uv-val telepíti a `.python-version` szerinti Python 3.11.18 x64-et a
   `.tools/python/` alá. Ez az Astral Python Standalone Builds CPython-buildje;
   az uv rögzített kiadásának letöltési katalógusa és integritásellenőrzése alapján.
   A telepítéshez a PyPI/pythonhosted és a standalone Python kiadási tárhelye elérhető kell legyen.
3. Létrehozza a `.venv/` környezetet, majd a teljes `requirements.lock` alapján
   `--require-hashes --only-binary :all:` módban szinkronizálja a függőségeket.
4. A `conda-av-win64.lock` explicit, SHA-256-tal rögzített conda-forge zárja alapján
   PyAV 17.1.0 + FFmpeg 8.1.2 LGPL runtime-ot készít, és a zár pontos PyAV
   csomagját, DLL-függőségi láncát, licencfájljait és build receptjeit `.tools/`
   alatt stage-eli. A micromamba 2.10.0 projektlokális bootstrap csomagjának
   hash-e ellenőrzött; semmi nem települ globálisan.
5. A helyi projektet editable módban, **offline**, `--no-deps --no-build-isolation`
   opciókkal telepíti. A build backend, az `editables` és tranzitív függőségeik is a lockban vannak.
6. Függőségellenőrzést és konfigurációvalidálást futtat. Meglévő venvnél ellenőrzi
   az interpreter pontos verzióját és a 64 bites architektúrát; nem törli a környezetet.

Az újbóli futtatás ugyanazt a Python- és conda lockot használja, nem frissít
csomagverziót. A sync eltávolítja a lockon kívüli Python csomagokat; a helyi
projektet utána újratelepíti.
Másik tiszta virtuális környezethez:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-dev.ps1 -Venv .venv-repro
```

A `-Venv` csak `.venv` vagy `.venv-<név>` lehet közvetlenül a repóban. A setup
nem indít alkalmazást, mikrofont, modelltelepítőt vagy modellletöltést.

## 🪟 Windows alkalmazás indítása

Fejlesztői módban előbb telepíts vagy offline importálj egy modellt a
[modellútmutató](../models/README.md) szerint; a GUI nem kezdeményez hálózati
letöltést. Ezután a repó gyökeréből:

```powershell
.\.venv\Scripts\roboassist.exe
```

Vagy futtasd modulból: `python -m offline_stt.ui`. Saját beállításfájlhoz add meg
a `--config <útvonal>` kapcsolót. A GUI a helyi modellek között csak a telepített
modelleket kínálja fel. A Windows felület használatáról és adatkezeléséről a
[felhasználói útmutató](user-guide.md) szól.

## 📦 Hordozható Windows csomag építése

Online build és hiányzó buildfüggőségek előkészítése:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-app.ps1
```

Már előkészített `.venv`, PyInstaller, micromamba és pontos conda csomagcache
esetén a build offline is futtatható:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-app.ps1 -Offline
```

A script verziózott, PyInstaller one-directory könyvtárat és ZIP-et készít a
`dist/` alá, továbbá SHA-256 fájlt ad a ZIP mellé. A ZIP nem tartalmaz modell-
súlyokat. A felhasználó a modellútmutató szerint külön, ellenőrzött bundle-ből
importálhatja a modellt. Modelltelepítésen kívül az app nem igényel futás közbeni
hálózatot. A csomag `licenses/` könyvtára megőrzi a Python wheelek és a natív
PyAV/FFmpeg DLL-zár licencszövegeit, hash-eit és forrás/build receptjeit.

Az offline buildhez a letöltött Python wheel cache mellett a pontos 98
conda-forge artifactot tartalmazó micromamba cache is szükséges. A `-Offline`
kapcsoló a conda runtime előkészítését hálózat nélkül végzi, és hiányzó csomagnál
hibával leáll. A friss buildet a [#24 csomagolási jegy](https://github.com/tnyari/RoboAssist/issues/24)
követi; tiszta Windows 10/11 telepítési próba és kiadási/licencátvétel még
nincs kész eredményként rögzítve.

## 📌 Függőségek és lock frissítése

A `pyproject.toml` a közvetlen függőségek és build-metaadatok forrása.
A `requirements.lock` az összes futásidejű, fejlesztői és build-csomag pontos
verzióját és a PyPI disztribúcióinak SHA-256 hash-eit tartalmazza. A feloldás célja
**Python 3.11.18 / x86_64-pc-windows-msvc**; ez nem más Python/OS/architektúra lockja.
A telepítés csak kompatibilis wheeleket fogad el, forrásbuildre nem vált át.

```powershell
# Meglévő tranzitív verziók megtartása, ha kompatibilisek:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/update-lock.ps1
# Szándékos tranzitív frissítés, külön issue/PR keretében:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/update-lock.ps1 -Upgrade
```

Frissítéskor ellenőrizd a diffet, futtasd újra a setupot új venvbe és az alábbi
ellenőrzéseket. A közvetlen `==` verziók cseréjéhez a `pyproject.toml` módosítása
is kell. A bootstrap uv-verzióváltásához a script URL/hash, a dev-lista és a lock
együttes frissítése szükséges. Ne szerkeszd kézzel a generált hash-eket.

Futásidejű készlet: faster-whisper, NumPy, sounddevice, **PyAV** és **PySide6 Essentials**.
Az Essentials az [önálló hivatalos Qt/PySide6 csomag](https://doc.qt.io/qtforpython-6/package_details.html),
amely tartalmazza a QtCore/QtGui/QtWidgets modulokat. A tervezett M1 feliratablakhoz nem kell
Addons vagy WebEngine. A [Qt 6.12 platformleírása](https://doc.qt.io/qtforpython-6/overviews/qtdoc-windows.html)
még támogatja a Windows 10-et. Új UI-modul vagy resampler/VAD/packaging eszköz
bevezetése az érintett implementációs issue-ban történjen.

## 🧪 Helyi ellenőrzések

```powershell
.\.venv\Scripts\python.exe -m offline_stt --config configs/default.toml
.\.venv\Scripts\roboassist-config.exe --config configs/default.toml
.\.venv\Scripts\python.exe -m ruff check src tests scripts/check-environment.py
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts/check-environment.py
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/check-environment.py
```

A smoke ellenőrzi a natív DLL/import kompatibilitást, a CPU INT8 támogatás jelzését,
az ONNX CPU provider és a PortAudio betöltését, valamint egy offscreen Qt felirat
kirajzolását. Python socket-szinten tiltja a DNS/TCP kísérleteket. Nem végez
modellinference-t, hangrögzítést vagy teljes operációsrendszer-szintű hálózatfigyelést.

A tényleges eredményeket és korlátokat a [#16 riportja](reports/issue-16-environment.md)
tartalmazza. A felhasználó által kijelölt Windows 10 célgép setupja, 32+32 tesztje,
natív smoke-ja és audioformátum-lekérdezése sikeres; ugyanebben a riportban a #28
kiegészítés tartalmazza a gépleltárt és a futtatott parancsokat. Ez nem tiszta
OS-/Windows 11-próba, és nem modellinference-benchmark. A tiszta Windows-próba
a felhasználó döntése alapján egyelőre halasztott (#28); a fejlesztés ezen a gépen folytatódik.
Windows CI: [workflow és hatókör](ci.md), [#17](https://github.com/tnyari/RoboAssist/issues/17).
Replay integráció: #20; modellbenchmark és hardveres/offline/stabilitási ellenőrzések
a későbbi M1 jegyekben. M2 előtt az M1 kapu (#10) kötelező.

## ⚙️ Konfiguráció

A [mikrofon és WAV replay leírása](audio.md) tartalmazza az audioforrás-szerződést,
az eszközlistázó és az explicit, memóriában futó mikrofonpróba parancsait.
Audioellenőrzési bizonyíték: [#4 riport](reports/issue-4-audio.md).

A [helyi engine szerződése](engine.md), [külön modelltelepítő](../models/README.md)
és [#5 ellenőrzési riport](reports/issue-5-engine.md) írja le a base/small CPU INT8
baseline-t. A normál pytest szintetikus fixture-ökkel fut; a valódi modellek smoke-ja
külön, előzetes explicit telepítés után indítható.

A [VAD/session pipeline](pipeline.md) és [#6 riport](reports/issue-6-pipeline.md)
tartalmazza a bounded queue, partial/final események, Windows spawn és Stop/hiba
életciklus szerződését. A teljes TOML új `[pipeline]` táblája és VAD-küszöbmezői
kötelezők; korábbi saját konfigurációnál vedd át őket az aktuális mintából.

`offline_stt.config.load_config(path)` egy explicit útvonalú, teljes schema-v1 TOML-t
olvas és változtathatatlan dataclass struktúrát ad vissza. A mintát a
`configs/default.toml` tartalmazza. Hiányzó/ismeretlen mező, téves típus, sérült
TOML vagy tiltott beállítás `ConfigError`; a CLI ilyenkor 2-es kóddal lép ki.
Nincs részleges konfiguráció csendes alapértékpótlással.

- Alapnyelv `hu`; más 2–3 kisbetűs nyelvkód megadható.
- Csak offline mód, telemetria nélkül; faster-whisper, CPU/INT8, automatikus letöltés nélkül.
- A pipeline célformátuma 16000 Hz mono; frame 10/20/30 ms. A natív mikrofonráta
  és a resampling implementációja #4 feladata.
- VAD: pozitív max. szegmens legfeljebb 60000 ms; pre-roll nemnegatív, végcsend pozitív,
  mindkettő a max. szegmensnél kisebb.
- Audio/átirat mentése alapból kikapcsolva; ezek explicit konfigurációs opt-innel
  engedélyezhetők. `export_requires_user_action = true` kötelező marad.
- A modell logikai azonosítója önmagában nem igazol helyi telepítést. A helyi
  feloldást/hiányhibát a helyi engine (#5) végzi; a config CLI nem tölt be modellt.

A loader csak olvas. Az engine és a későbbi export/UI köteles a validált szabályokat
érvényesíteni; a beállítások létezése nem igazol kész STT/export funkciót.

A RoboAssist saját forráskódjának licence a tulajdonos döntése alapján MIT;
a [harmadik fél jegyzék](../THIRD_PARTY_NOTICES.md) és a részletes
[#25 audit](reports/issue-25-license-audit.md) követi a függőségek és a csomag
terjesztési feltételeit.
