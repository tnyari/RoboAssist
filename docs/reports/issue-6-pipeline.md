# #6 – VAD és session pipeline ellenőrzése

**Dátum:** 2026-11-26 · kijelölt Windows 10 gép · szülő #6, aljegyek #18/#19/#20,
EOF-drain javítás #38. [Szerződés, beállítások és korlátok](../pipeline.md).

## 🟩 Elkészült

- Energia-VAD: pontos 250 ms pre-roll, 500 ms végcsend, 12 s max. szegmens;
  RMS −42 dBFS küszöb és 6 dB hiszterézis, konfigurálható paraméterek.
- Korlátos frame-/munkasor, final prioritás, lecserélhető és elavult partial;
  750 ms ciklus, 5 s gördülő ablak, külön újradekódolási metrikák.
- Verziózott immutable TranscriptEvent: session/segment/revision, mintaszám-alapú
  audioidő, monoton kibocsátási idő; ideiglenes közös prefix és egyszeri final.
- Windows-spawn session-folyamat: elkülönített forrás-, VAD- és STT szál;
  Stop/drain/flush, timeout utáni kényszerleállítás, tiszta restart/close.
- #38: producer-done után újraolvasott frame queue, hogy a timeout/done közé
  érkezett utolsó blokk is bekerüljön. Determinisztikus regresszió készült.
- Az aktuális `[vad]`/`[pipeline]` konfiguráció kötelező mezői a TOML-mintában;
  régi saját v1 konfigurációt e mezőkkel ki kell egészíteni.

## 🟩 Tényleges helyi ellenőrzések

Környezet: Windows 10 Pro 22H2 x64/build 19045, i5-1135G7 4 mag/8 szál,
15,71 GiB RAM; Python 3.11.18 x64, faster-whisper 1.2.1, CTranslate2 4.9.1,
NumPy 2.4.6, PyAV 18.1.1. Nincs új függőség vagy lockváltozás.
Lock SHA-256: `a3c62a0c94ed5c919df5fd5e38f4544675b6cdb5d90ea2bda5719b26885cceb3`.

| Ellenőrzés | Futtatott eredmény |
|---|---|
| Ruff lint és formátum | Sikeres, 34 Python-fájl |
| Mypy strict | Sikeres, 23 forrásfájl |
| Teljes pytest | 191 passed in 35.01s |
| Pipeline komponensek | 18 teszt: csend/hiszterézis, pre-roll, rövid/gyors/hosszú szegmens, frame/final túlterhelés, final prioritás, prefix/revízió/ismétlés/session, #38 EOF-race |
| Pipeline integráció | 11 teszt Windows spawn-nal és fake decoderrel; valódi generált WAV olvasó |
| Config CLI és natív smoke | Sikeres; DLL/import, CPU INT8 támogatás és offscreen Qt |
| Új replay CLI | Sikeres a generált tesztjellel és a helyi base modellel; 90 frame, 1 final, csak metaadat-kimenet |

A pipeline integráció Stop–Start ismétlést és egyszeri flush-t, eszközleválasztást,
decoder- és unload hibát, hibából újraindítást, hiányzó helyi modellt, kimeneti és
final-munkasor túlterhelést, lezárt session tiltását ellenőrzi. Külön teszt 30 s-ra
beragasztott olvasást és külön dekódolást állít le 1 s Stop budgettel; a worker
nem marad életben, régi session-esemény nem olvasható. Az integrációs factory a
spawn gyermekben is tiltja a Python DNS/TCP-t. Ez nem OS-szintű hálózati audit.

A WAV teszt 0,5 s generált 220 Hz jelet és 0,6 s csendet hoz létre a pytest
tempjében. Igazi WavReplaySource → VAD → valódi engine adapter/fake decoder →
final útvonal fut; final vége 1000 ms, 1 load/1 warm-up és 1 final, több partial
decode, nincs új fájl/export. A normál Windows CI ezt a teljes pytesttel futtatja;
a lépés neve jelzi az audio/pipeline replay integrációt. Súlyt a CI nem használ.

Az első célzott parancsnál a `.tools/issue-6` szülőkönyvtár még hiányzott, ezért
a tmp_path-os tesztek előkészítési hibát kaptak; ezt a munkakönyvtár létrehozása
után újrafuttattuk. A fenti teljes eredmény sikeres futásból származik. A helyi
pytest a korábban igazolt Windows sandbox ACL-korlát miatt engedélyezett sandboxon
kívül futott; a termékkód ezen nem változtat.

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests scripts/check-environment.py
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts/check-environment.py
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest --basetemp=.tools/issue-6/full-tests -p no:cacheprovider
.\.venv\Scripts\roboassist-config.exe --config configs/default.toml
.\.venv\Scripts\python.exe scripts/check-environment.py
```

## 🟩 Valódi helyi modellek a pipeline-ban

A már explicit engedéllyel telepített, [manifest szerinti](../../models/manifest.json)
base és small modellekkel is lefutott a teljes session. Nincs új letöltés vagy
valós hangfelvétel. Bemenet 1,2 s generált 220 Hz jel + 0,6 s csend, 90 × 20 ms
frame / 28800 minta. A VAD végpont 1,7 s-nál finalizál, a maradék csend nem indít
új szegmenst. A valódi engine ellenőrzött CPU INT8 útja a #5 adaptere.

| Tényleges megfigyelés | base | small |
|---|---|---|
| Revision | ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66 | 536b0662742c02347bc0e980a01041f333bce120 |
| Model load / warm-up | 1 / 1 | 1 / 1 |
| Partial decode / final decode | 1 / 1 | 1 / 1 |
| Kibocsátott partial / final esemény | 0 / 1 | 0 / 1 |
| Eldobott elavult/pending partial munka | 2 | 2 |
| Dropped frame / rejected final | 0 / 0 | 0 / 0 |
| Max. frame / munka backlog | 1 / 1 | 1 / 1 |
| Újradekódolt minták | 12160 | 12160 |
| Partial decode idő | 1,404 s | 2,398 s |
| Final decode idő | 1,318 s | 2,245 s |
| Forced termination / kimeneti hiba | 0 / 0 | 0 / 0 |
| Python DNS/TCP-kísérlet | 0 | 0 |

A partial decode elavult, mielőtt a final sorra került, ezért nincs partial
kibocsátás. Ez a final prioritást és a stale-eredmény szűrését demonstrálja;
nem bizonyít partial latency célt vagy valós beszédsebességet. A külön idők
egyszeri szintetikus megfigyelések, nem RTF/WER benchmark.

A helyi harness a gyermek engine factoryjában tiltja `socket.getaddrinfo`,
`socket.socket.connect` és `connect_ex` hívását, számlálja a kísérleteket, és
close-kor bármely kísérletre hibát adna. Mindkét session tisztán leállt; a parent
az eseményeket csak memóriában számolta, szöveget nem írt ki és nem mentett.
Helyi metaadat: `.tools/issue-6/real-base-multilingual.json`,
`real-small-multilingual.json`; harness `real-pipeline-smoke.py`; a generált
tesztjel `synthetic-tone.wav`. Ezek nem Git-artefaktumok és nem személyes adatok.

## 🟨 El nem végzett ellenőrzések

- Valódi magyar beszéd pontossága, zajos VAD/minőséghangolás, WER/RTF,
  end-to-end UI latency, 30 perces/8 órás stabilitás és hardvermátrix: #8/#10.
- A session mikrofon factoryt fogad, és az eszközhibát injektált source-szal
  teszteltük. Ebben a körben nem futott új fizikai mikrofonos beszédpróba;
  az audiohardver korábbi #4 riportja nem teljes STT-bizonyítás.
- PySide6 UI bekötés: #7; nincs kész teljes feliratozó alkalmazás.
- Tiszta Windows 10/11, hiányzó VC++ runtime: #28, kifejezett döntésre halasztott.
- Projektlicenc és teljes csomagolási licencaudit: #25; M2 nem indult.
- A PR-hez tartozó tényleges Windows Actions eredményt #6 és a PR kommentje
  rögzíti; e riport nem helyettesíti a főági integrációt.
