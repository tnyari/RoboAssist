# #16 – fejlesztői környezet ellenőrzése

**Dátum:** 2026-11-26 · **Jegy:** [#16](https://github.com/tnyari/RoboAssist/issues/16)
· **Szülő:** [#3](https://github.com/tnyari/RoboAssist/issues/3)

## 🟩 Ellenőrzött környezet és eredmény

| Tétel | Tényleges eredmény |
|---|---|
| Operációs rendszer | Windows 10 22H2 x64, `10.0.19045` |
| Setup shell | Windows PowerShell 5.1, `-NoProfile -ExecutionPolicy Bypass` |
| Interpreter | CPython 3.11.18 x64, uv-managed standalone build; a gép korábbi Python 3.10-ét nem használja a setup |
| Bootstrap/lock eszköz | uv 0.13.10; Windows x64 wheel SHA-256 a bootstrap scriptben rögzítve |
| Lock | 44 külső futásidejű/dev/build csomag, pontos verziókkal és SHA-256 hash-ekkel |
| Lock SHA-256 | `7472cc372365bcb9478600d0d48ce6692a7e32c44af39e961dc8f7540afb16fd` |
| Projekt | `roboassist-offline-stt==0.1.0`, offline editable install, külön a külső locktól |
| Új `.venv` | Telepítés sikeres; 45 telepített disztribúció, `uv pip check`: kompatibilis |
| Új `.venv-repro`, majd ismételt setup | Mindkét futás sikeres; lockon kívüli projekt eltávolítása és offline újratelepítése működik |
| Külön projektmásolat üres tool/Python/cache/venv állapottal | Teljes bootstrap és telepítés sikeres; a PATH csak Windows/system32/Windows PowerShell helyeket tartalmazott |

A külön másolat `.tools/clean-setup/` alatt a `pyproject.toml`, `requirements.lock`,
`.python-version`, `README.md`, `src/`, `scripts/`, `configs/` és `tests/` fájljaiból
készült, meglévő `.tools` vagy `.venv` másolása nélkül. Az interpretert és az összes
csomagot újra letöltötte; a setup nem támaszkodott a gépen regisztrált Pythonra.
Ez **tiszta projekt-/Python-környezet**, nem igazoltan frissen telepített OS.

## 🧪 Futtatott ellenőrzések

Az alábbi parancsok a repó gyökeréből futottak; mindegyik végső ellenőrzés sikeres.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-dev.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-dev.ps1 -Venv .venv-repro
# Ugyanez az alternatív környezetben még egyszer: sikeres ismétlés.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/update-lock.ps1
.\.venv\Scripts\python.exe -m offline_stt --config configs/default.toml
.\.venv\Scripts\roboassist-config.exe --config configs/default.toml
.\.venv\Scripts\python.exe -m ruff check src tests scripts/check-environment.py
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts/check-environment.py
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest --basetemp=.tools/pytest-tmp
.\.venv\Scripts\python.exe scripts/check-environment.py
.\.tools\uv-bootstrap\extracted\uv-0.13.10.data\scripts\uv.exe build --wheel --no-build-isolation --offline --python .venv/Scripts/python.exe --cache-dir .tools/uv-cache
```

| Ellenőrzés | Bizonyíték / kimenet |
|---|---|
| Konfiguráció és telepített entrypoint | `nyelv=hu, engine=faster-whisper, cpu/int8, offline=True, save_audio=False, save_transcript=False` |
| Ruff lint | `All checks passed!` |
| Ruff formátum | `7 files already formatted` |
| Strict mypy | `Success: no issues found in 3 source files` |
| Pytest a fő környezetben | **32 passed**: 30 konfigurációteszt + 2 subprocess CLI integráció |
| Pytest a külön bootstrapelt projektmásolatban | **32 passed**, az ott telepített csomagot importálva |
| Lock újragenerálás | Előtte/utána byte-azonos SHA-256 (fent) |
| Wheel build és tartalom | Sikeres; csak `offline_stt/` és a projekt `.dist-info/` tartalma, nincs modell/hang/titok |

A pytest ideiglenes könyvtára a munkamappa alá került, hogy a teszt ne igényeljen
hozzáférést a megosztott rendszer-temphez. A subprocess teszt más munkakönyvtárból
használja a telepített csomagot; nincs teszt-specifikus `PYTHONPATH` vagy `sys.path` módosítás.

### Natív csomagok smoke-eredménye

A `scripts/check-environment.py` a fő és a külön bootstrapelt környezetben is
`status: passed` eredményt adott:

| Komponens | Verzió / ellenőrzés |
|---|---|
| faster-whisper / CTranslate2 | 1.2.1 / 4.9.1; import sikeres |
| CPU compute types | `float32`, `int16`, **`int8`**, `int8_float32` |
| NumPy | 2.4.6; szintetikus 320 mintás tömb létrehozása |
| PySide6 Essentials / shiboken6 / Qt | 6.12.0; offscreen `QApplication` és `QLabel.grab()` sikeres |
| sounddevice | 0.5.6; PortAudio DLL betöltve |
| PortAudio | `PortAudio V19.7.0-devel, revision unknown` – ennél pontosabb build nem állapítható meg a visszatérési értékből |
| ONNX Runtime | 1.32.0; `CPUExecutionProvider` elérhető |
| PyAV | 18.1.1; szintetikus mono AudioFrame létrehozása |

A smoke `HF_HUB_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1` mellett futott, Python
socket DNS/TCP metódusokat hibára cserélve. Modellt nem példányosított, mikrofont
nem nyitott, audio-/átiratfájlt nem mentett. Ez a csomagok betölthetőségét igazolja;
CPU INT8 modellinference-t és teljes offline STT működést nem mér.

### Fejlesztés közbeni eltérések

Az első offline editable build a Hatchling dinamikus `editables` buildfüggőségének
hiányát jelezte. Az `editables==0.5` bekerült a build/dev deklarációba és a teljes
hash-lockba; ezután a setup, a külön bootstrap és a wheel build sikeres lett.
Az első sikertelen tesztgyűjtés a még nem települt projekttel történt; a fenti
32+32 sikeres teszt már a ténylegesen telepített csomagot ellenőrizte.

## 🟨 Nem elvégzett ellenőrzések és követés

- **Frissen telepített Windows 10/11**, illetve hiányzó VC++ runtime telepítési
  útja: nincs külön tiszta VM/gép ebben a munkakörnyezetben. A meglévő Windows 10
  OS-prerequisite készletét a külön projektmásolat nem törli. Külön aljegy:
  [#28](https://github.com/tnyari/RoboAssist/issues/28). Emiatt #16 és #3 nyitva marad.
- **GitHub Actions:** #17 külön implementáció, itt nem készült workflow és nincs
  állított CI-siker. A helyi parancsok szolgálnak a bekötés alapjául.
- **Modellinference, mikrofon/replay, resampler/VAD/pipeline és STT UI:** a megfelelő
  #4–#7/#20 jegyek részei, még nincs hozzá implementáció/modell.
- **Teljes DNS/HTTP forgalomfigyelés, teljesítménybenchmark és stabilitás:** későbbi
  M1 ellenőrzések; a socket smoke nem helyettesíti ezeket. Nincs mért RTF/latency/WER állítás.
- **Végleges függőség-/modelllicenc- és sérülékenységellenőrzés, projektlicenc:**
  #25; a metadataalapú főkomponens-leltár a `THIRD_PARTY_NOTICES.md` fájlban szerepel.

## 🔗 Ellenőrzött technológiai források

- [uv: lock és hash-generálás](https://docs.astral.sh/uv/pip/compile/)
- [uv: Python-verziók kezelése](https://docs.astral.sh/uv/guides/install-python/)
- [Qt for Python csomagfelosztás](https://doc.qt.io/qtforpython-6/package_details.html)
- [Qt 6.12 Windows platformok](https://doc.qt.io/qtforpython-6/overviews/qtdoc-windows.html)
- [faster-whisper 1.2.1 kiadási leírás és CPU INT8 használat](https://pypi.org/project/faster-whisper/1.2.1/)
- [Microsoft Visual C++ v14 x64 runtime](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)


## 🟩 #28 – a felhasználó által kijelölt célgép ellenőrzése

**Dátum:** 2026-11-26 (Europe/Budapest). A felhasználó ezt a meglévő gépet jelölte
ki a további munkához. Az alábbi vizsgálat ennek a gépnek a fejlesztői alkalmasságát
ellenőrzi; a tiszta Windows 10/11 elfogadási feltétel továbbra is nyitott.

### Gépleltár

| Tétel | Helyben lekérdezett eredmény |
|---|---|
| Windows | Windows 10 Pro 22H2 x64, build **19045.6466** |
| CPU | Intel Core i5-1135G7 @ 2,40 GHz; **4 fizikai mag / 8 logikai szál** |
| Fizikai RAM | 16 863 318 016 byte, **15,71 GiB** |
| Pillanatnyi szabad fizikai memória | A leltárkor **4,18 GiB**; háttérterheléstől függő pillanatfelvétel |
| C: szabad hely | Kezdetben **9,53 GiB**, az ellenőrzések után 10 205 982 720 byte (**9,51 GiB**) |
| Microsoft VC++ x64 runtime | Registry: Installed=1, **v14.51.36247.00**; System32 vcruntime140.dll, vcruntime140_1.dll és msvcp140.dll: 14.51.36247.0 |
| Shell | Windows PowerShell **5.1.19041.6456**, NoProfile |
| Projekt-Python / uv | CPython **3.11.18 x64**, uv **0.13.10** |
| Rendszer-Python | A PATH-on Python 3.10 található; a projekt saját 3.11 interpretert használ |
| Audio | A Windows két audioeszközének állapota OK; a PortAudio eszközfelsorolása sikeres |

A CPU/RAM/Windows/audio leltár CIM-lekérdezésből, a build UBR és a VC++ bejegyzés
registryből, a tárhelyadat DriveInfo-lekérdezésből származik. Gépnév, felhasználói
azonosító, sorozatszám, hálózati azonosító és hangadat nem került a riportba.

### Forrásazonosság és futtatott ellenőrzések

Ellenőrzési alap: [PR #29](https://github.com/tnyari/RoboAssist/pull/29),
[85cd16d7885d18f086034ba5277c95e000b6a0a3](https://github.com/tnyari/RoboAssist/commit/85cd16d7885d18f086034ba5277c95e000b6a0a3).
A PR mind a **19 módosított fájljának** helyi Git blob SHA-1 értéke byte-azonosan
egyezett a GitHub bővítményen keresztül olvasott commitfájlokéval, még a riport
jelen kiegészítése előtt. A lock SHA-256 értéke a telepítések után is változatlan:
`7472cc372365bcb9478600d0d48ce6692a7e32c44af39e961dc8f7540afb16fd`.

| Tényleges ellenőrzés | Eredmény |
|---|---|
| Meglévő fő `.venv` setup újrafuttatása | Sikeres; **45 kompatibilis disztribúció** |
| Új `.venv-host-check` létrehozása és setup | Sikeres; a projekt saját Pythonját és meglévő uv-cache-ét használta |
| `.venv-host-check` setup ismétlése | Sikeres, ugyanazzal a lockkal; offline editable újratelepítés működik |
| Fő környezet konfiguráció + telepített CLI | Sikeres, hu/CPU/INT8/offline, mindkét mentés kikapcsolva |
| Fő környezet pytest | **32 passed in 1.24s** |
| Új környezet konfiguráció + telepített CLI | Sikeres, azonos alapértékek |
| Új környezet pytest | **32 passed in 1.08s** |
| Natív smoke, mindkét környezet | **status: passed**; DLL/import, CPU INT8 elérhetőség, ONNX CPU provider, offscreen Qt render |
| Ruff lint / formátum | **All checks passed! / 7 files already formatted** |
| Strict mypy | **Success: no issues found in 3 source files** |

A tesztfutás ideje tesztbizonyíték, nem STT teljesítménybenchmark. A natív csomagok
verziói egyeznek a fenti #16 smoke-táblával; modellinference nem történt.

Reprodukáló parancsok a projekt gyökerében:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-dev.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-dev.ps1 -Venv .venv-host-check
# Ugyanez az utóbbi parancs másodszor is lefutott.
.\.venv\Scripts\python.exe -m offline_stt --config configs/default.toml
.\.venv\Scripts\roboassist-config.exe --config configs/default.toml
.\.venv\Scripts\python.exe -m pytest --basetemp=.tools/issue-28/pytest-native-venv -p no:cacheprovider
.\.venv\Scripts\python.exe scripts/check-environment.py
.\.venv-host-check\Scripts\python.exe -m offline_stt --config configs/default.toml
.\.venv-host-check\Scripts\roboassist-config.exe --config configs/default.toml
.\.venv-host-check\Scripts\python.exe -m pytest --basetemp=.tools/issue-28/pytest-native-venv-host-check -p no:cacheprovider
.\.venv-host-check\Scripts\python.exe scripts/check-environment.py
.\.venv\Scripts\python.exe -m ruff check src tests scripts/check-environment.py
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts/check-environment.py
.\.venv\Scripts\python.exe -m mypy
Get-FileHash requirements.lock -Algorithm SHA256
```

A helyi parancskimenetek a Gitből kizárt `.tools/issue-28/` könyvtárban maradnak:
`setup-main-network.log`, `setup-host-network.log`, `setup-host-repeat.log`,
`venv-*.log`, `venv-host-check-*.log`, a két `*-results.json`,
`provenance.json` és `audio-devices.json`. A sikeres tesztek új ideiglenes
könyvtárakat használtak; ezek csak ehhez az ellenőrzéshez tartoznak.

### Audiolekérdezés, rögzítés nélkül

A `sounddevice.query_devices()` **13 bemeneti API-végpontot** jelzett; ez nem
13 külön fizikai mikrofon. Elérhető host API-k: MME, Windows DirectSound,
Windows WASAPI és Windows WDM-KS. A jelenlegi alapbemenet MME végpontja
legfeljebb 4 csatornát és 44 100 Hz alapértelmezett rátát jelentett.

A `sounddevice.check_input_settings(device=1, channels=..., dtype='float32',
samplerate=...)` a 44 100 és 48 000 Hz ráták mindegyikén mono és stereo
formátumot is támogatottnak jelzett. Ez formátumlekérdezés: stream nem nyílt,
hangot nem rögzítettünk. A callback/capture működése, az állapottartó resampling,
a 16 kHz célformátum és az eszközleválasztás kezelése továbbra is #4 feladata.

### Futtatási korlát és megmaradó elfogadás

- Az első sandboxos setupkísérletek a hálózati proxynál kapcsolatmegtagadást
  kaptak, a sandboxos pytest pedig az általa létrehozott tempkönyvtár ACL-jénél
  WinError 5 hibát adott. A célgépen a sandboxkorláton kívül futtatott, azonos
  projektscriptek és tesztek sikeresek. Ez a különbség a végrehajtási környezet
  korlátja; a projektben hibajavítás nem történt.
- **Ezen a gépen a fejlesztői környezet használható.** A C: szabad helye és a
  szabad RAM pillanatfelvétel; modelltelepítés és későbbi benchmark előtt újra
  ellenőrizendő. Eredmény nélküli valós idejű STT alkalmassági állítás nincs.
- **Nem futott:** frissen telepített Windows 10, Windows 11, hiányzó VC++ runtime
  telepítési útja. A gép meglévő Windows 10 és runtime állapotát ellenőriztük;
  ezek a tiszta OS-feltételt nem helyettesítik. A maradék a meglévő [#28](https://github.com/tnyari/RoboAssist/issues/28)
  jegyen marad, #16 és #3 nyitott.
- Modellletöltés, modellinference, mikrofonrögzítés, replay/pipeline, OS-szintű
  hálózati bizonyítás, RTF/latency/WER és stabilitási mérés nem történt.
  Ezek továbbra is a saját M1 jegyeik feladatai.
