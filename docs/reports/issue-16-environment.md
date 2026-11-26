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
