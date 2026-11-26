# #5 – CPU INT8 engine és helyi modellek ellenőrzése

**Dátum:** 2026-11-26 · **gép:** a felhasználó kijelölt Windows 10 gépe.
Jegyek: [#5](https://github.com/tnyari/RoboAssist/issues/5),
[#35 importhiba](https://github.com/tnyari/RoboAssist/issues/35),
[#36 valódi modellpróba](https://github.com/tnyari/RoboAssist/issues/36).

## 🟩 Eredmény és környezet

Elkészült a [SpeechEngine szerződés és adapter](../engine.md), a szigorú helyi
modellverifikáció és a [külön explicit telepítő](../../models/README.md).
Függőség- és lockváltoztatás nincs. A felhasználó mindkét modell egyszeri letöltését
és ellenőrzését kifejezetten engedélyezte; mindkettő telepítése sikeres.

| Környezet | Tényleges érték |
|---|---|
| OS | Windows 10 Pro 22H2 x64, build 19045 |
| CPU / RAM | Intel Core i5-1135G7, 4 mag / 8 szál; 15,71 GiB RAM |
| Python | CPython 3.11.18 x64 |
| faster-whisper / CTranslate2 | 1.2.1 / 4.9.1 |
| NumPy / PyAV | 2.4.6 / 18.1.1 |
| Dekódolás | hu, CPU, 4 szál, kért int8, tényleges int8_float32 |
| Lock SHA-256 | `a3c62a0c94ed5c919df5fd5e38f4544675b6cdb5d90ea2bda5719b26885cceb3` |

## 🟩 Futtatott ellenőrzések

- Ruff lint és formátum: sikeres, 24 Python-fájl a meglévő ellenőrzési körben.
- Mypy strict: sikeres, 15 forrásfájl.
- Teljes pytest: **162 passed in 8.87s**; ebből 40 helyi modellkezelési és
  13 engine-integrációs teszt, 109 meglévő teszt.
- Telepített konfigurációs CLI és natív környezeti smoke: sikeres.
- Valódi modelltelepítés: mindkét modell 6 szükséges fájlja méret/SHA szerint
  ellenőrzött (5 upstream fájl és a mellékelt licenc), receipt létrejött.
- Meglévő modellek ismételt installerhívása `--allow-network` nélkül,
  Python DNS/TCP tiltással: sikeres újraellenőrzés, nincs új letöltés.
- A #35 hibajavításhoz túlméretes és azonos méretű sérült offline forrás
  regressziós tesztje sikeres; hibás forrásból nincs aktivált modell.

A sandboxban indított első teljes pytest a pytest által létrehozott ideiglenes
könyvtár Windows ACL-je miatt `WinError 5` hibát kapott, majd a takarítás is
hozzáférési hibával állt le. Ez nem sikeres tesztfutás. Ugyanaz a teljes készlet
engedélyezett sandboxon kívüli helyi futtatással, új `.tools/issue-5/verified-tests`
basetemp alatt a fenti 162 sikeres eredményt adta; termékkód-változtatás nélkül.

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests scripts/check-environment.py
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts/check-environment.py
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest --basetemp=.tools/issue-5/verified-tests -p no:cacheprovider
.\.venv\Scripts\roboassist-config.exe --config configs/default.toml
.\.venv\Scripts\python.exe scripts/check-environment.py
```

## 🟩 Valódi base/small modellpróba

| Modell | Rögzített revision | model.bin byte / SHA-256 |
|---|---|---|
| base-multilingual | `ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66` | 145217532 / `d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9` |
| small-multilingual | `536b0662742c02347bc0e980a01041f333bce120` | 483546902 / `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671` |

Az összes további fájl mérete/hash-e és a licencforrás a
[manifestben](../../models/manifest.json) szerepel. A valódi SDK multilingual
jelzője mindkettőnél igaz; enélkül az adapter load hibát adna.

| Tényleges megfigyelés | base | small |
|---|---|---|
| Sikeres modellbetöltések | 1 | 1 |
| Külön warm-up hívások | 1 | 1 |
| Reset utáni flush/decode hívások | 2 | 2 |
| Tényleges compute type | int8_float32 | int8_float32 |
| Két csendablak szegmensszáma | 0, 0 | 0, 0 |
| Load idő, hash-elés nélkül | 1,018 s | 1,770 s |
| Warm-up idő, decode-tól külön | 1,129 s | 2,088 s |
| Két decode összes ideje | 1,430 s | 4,601 s |
| Python DNS/TCP kísérlet | 0 | 0 |

A load kétszer lett meghívva: a második nem töltött újra. A warm-up 1 másodperc
szintetikus csend, legfeljebb 1 új token; a két inference ciklus egyenként
25 × 320 mintás blokk, összesen 0,5 másodperc csend, legfeljebb 16 új token.
Az SDK lazy generátora minden alkalommal végigfutott. Minden ciklus után az
üres flush üres maradt; a modell közben memóriában maradt, végül close sikeres.

Az offline harness a teljes CLI smoke alatt `socket.getaddrinfo`,
`socket.socket.connect` és `connect_ex` helyére kivételt dobó függvényt tett,
kísérletszámlálóval. Nullán maradt. A HF offline/telemetriatilalmi változókat az
adapter a lazy SDK import előtt állítja. Ez Python-szintű hálózati ellenőrzés,
nem OS-tűzfalas vagy csomagszintű audit. A normál smoke reprodukálható a
modelljegyzék parancsaival; a hálózattiltott harness lényege:

```python
import socket
import sys
from unittest.mock import patch
from offline_stt.engines.__main__ import main

attempts = []
def denied(*args, **kwargs):
    attempts.append(True)
    raise RuntimeError("Network forbidden during real inference")

sys.argv = ["offline_stt.engines", "smoke", "base-multilingual"]
with patch.object(socket, "getaddrinfo", denied), \
     patch.object(socket.socket, "connect", denied), \
     patch.object(socket.socket, "connect_ex", denied):
    assert main() == 0
assert not attempts
# Ugyanez külön Python-folyamatban small-multilingual azonosítóval is lefutott.
```

A gépi, csak metaadatot tartalmazó kimenetek helyben a `.tools/issue-5/`
`install-base.json`, `install-small.json`, `smoke-base-multilingual.json`,
`smoke-small-multilingual.json`, `native-smoke.json` fájljaiban maradtak.
Hang és átirat nem lett mentve; súly nem kerül Gitbe.

## 🟨 El nem végzett ellenőrzések és hatókör

- Magyar beszédpontosság, WER/RTF, hosszú futás és end-to-end latency nem mért:
  #8 és a későbbi M1 integrációs/benchmark feladatok része. A fenti egyszeri
  szintetikus csendidőkből nem következik beszédteljesítmény.
- Mikrofon → engine → UI teljes session még nincs bekötve: #6/#7/#19/#20.
- Tiszta Windows 10/11 és hiányzó VC++ runtime próba: #28, a felhasználó döntése
  szerint halasztott. A meglévő gép és Windows Server CI nem helyettesíti.
- Projektlicenc és teljes terjesztési licencaudit: #25.
- A Windows Actions eredményét a kapcsolódó PR és #5 mérföldkő-kommentje rögzíti;
  a normál CI nem tölt le és nem futtat valódi modellt.
