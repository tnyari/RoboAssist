# #4 – audioforrások ellenőrzési riportja

**Dátum:** 2026-11-26 (Europe/Budapest) · **Jegy:** [#4](https://github.com/tnyari/RoboAssist/issues/4)
· **Driverhiba:** [#33](https://github.com/tnyari/RoboAssist/issues/33)

## 🟩 Megvalósítás és környezet

Alap: main `69db0ee642a1b900fbac2c826e5c1575b25c465c`, a #29/#30 integráció után.
Windows 10 Pro 22H2 x64 célgép, CPython 3.11.18 x64, PyAV 18.1.1,
sounddevice 0.5.6 / PortAudio 19.7.0-devel. A korábbi hardverleltár #16/#28 riportjában
szerepel; itt ugyanazon a gépen történt az explicit, csak memóriás capture.

- Közös AudioSource/AudioFrame szerződés, 16 kHz mono float32 és 20/30 ms framing.
- Előre lefoglalt, korlátos SPSC mikrofonpuffer; a callback nem resample-el,
  nincs benne STT/UI/fájlírás vagy lockvárakozás.
- Állapottartó PyAV/libswresample, számtani stereo downmix, pontos egész mintaszám,
  telített PCM16 adapter; helyi PCM8/16/24/32 WAV és abszolút időzített replay.
- Látható overflow/stall/streamvég hiba, restart és bufferürítés; #33 a hibás
  driverlezárás és késői callback külön javítása.

## 🎙️ Tényleges mikrofonpróbák ezen a gépen

Az `offline_stt.audio devices` 13 bemeneti API-végpontot jelzett, köztük a
beépített Intel mikrofontömb MME és Windows WASAPI végpontját. Ez nem 13 fizikai
mikrofon. A parancsok explicit capture-t indítottak, indítás/leállítás jelzéssel.
Hangfájl, beszélgetésszöveg vagy transcript nem készült; a kimenet számláló és
összesített jelszint. A riport nem tartalmaz nyers hangot.

### MME, eszközindex 1, 20 ms frame-ek

```powershell
.\.venv\Scripts\python.exe -m offline_stt.audio microphone --device 1 --rate 44100 --channels 1 --seconds 2
# Ugyanez channels=2, majd rate=48000 / channels=1 és 2.
```

| Kért bemenet | Output frame | Output minta | Dropped blokk/minta | Overflow | Max. queue blokk |
|---|---:|---:|---|---:|---:|
| 44 100 Hz mono | 100 | 32 000 | 0 / 0 | 0 | 2 |
| 44 100 Hz stereo | 100 | 32 000 | 0 / 0 | 0 | 2 |
| 48 000 Hz mono | 100 | 32 000 | 0 / 0 | 0 | 2 |
| 48 000 Hz stereo | 100 | 32 000 | 0 / 0 | 0 | 2 |

Mind a négy próba `status: passed`, folytonos 0..32 000 kimeneti mintaszám és
véges, nem nulla jelszint mellett. A kért Windows host API-formátumot ellenőriztük;
a fizikai ADC natív rátájára ez nem bizonyíték, a Windows/driver végezhet belső átalakítást.

### WASAPI, eszközindex 9, 48 kHz stereo, 30 ms, azonos forrás újraindítva

Két explicit Start–Stop ciklus ugyanazon `MicrophoneSource` példánnyal, ciklusonként
legalább egy másodpercnyi kimenettel:

| Ciklus | Output frame | Output minta | Dropped | Overflow | Max. queue | Stop utáni ring |
|---|---:|---:|---:|---:|---:|---|
| 1 | 34 | 16 320 | 0 | 0 | 1 | nullázva |
| 2 | 34 | 16 320 | 0 | 0 | 1 | nullázva |

Mindkét ciklus 0-ról induló kimeneti mintaszámot adott; nincs korábbi sessionből
átadott frame. A 16 320 minta 1,02 s teljes, 30 ms-os frame-eket jelent; az egy
másodperces cél nem okozott rövidített live capture frame-et. A forrás Close-zal lezárult.

## 🧪 Helyi automatizált ellenőrzések

| Ellenőrzés | Tényleges eredmény |
|---|---|
| Új normalizer/PCM/signal tesztek | **43 passed** |
| Forrásintegráció és driverhiba-regresszió | **34 teszt** a teljes futásban |
| Teljes meglévő + új tesztkészlet | **109 passed in 3.69s** |
| Ruff lint / formátum | All checks passed / 15 files already formatted |
| Strict mypy | Success: no issues found in 9 source files |
| Natív környezeti smoke | status: passed |
| Setup új lockkal | Sikeres; 45 kompatibilis disztribúció |
| Lockverziók összevetése az alappal | Mind a 44 külső csomag verziója változatlan |

A PyAV közvetlen függőséggé vált, mert az audio modul önállóan használja;
új csomag vagy verziófrissítés nem történt. Az új generált lock SHA-256 értéke:
`a3c62a0c94ed5c919df5fd5e38f4544675b6cdb5d90ea2bda5719b26885cceb3`.

A tesztek ellenőrzik a chunkhatároktól független hullámformát, 12 kHz-es jel
anti-alias szűrését 44,1/48 kHz bemenetről, amplitúdót és stereo átlagot, rövid
és tört frame-nyi WAV pontos mintaszámát, PCM szélsőértékeket, replay abszolút
határidőket és valódi faliórás pacinget, restartot és hibás/truncated WAV-ot.
A callback bemenetét a fake driver azonnal felülírja; a teszt igazolja a saját
puffermásolatot és azt, hogy a resampling csak readkor történik.

A pufferfull, driver overflow, váratlan streamvég/leválasztás, callback-stall és
abort/close kivétel **injektált driverhibával** ellenőrzött integrációs utak.
Valódi driverhibát vagy fizikai kihúzást nem állítunk. A #33 regressziós teszt
igazolja a close megkísérlését abort-hiba után, a késői callback elutasítását és
a bizonytalan driverlezárás utáni restart tiltását.

Reprodukció a projekt gyökeréből:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-dev.ps1
.\.venv\Scripts\python.exe -m ruff check src tests scripts/check-environment.py
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts/check-environment.py
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest --basetemp=.tools/issue-4/full-tmp -p no:cacheprovider
```

A helyi capture-számlálók `.tools/issue-4/microphone-*.json` és
`hardware-restart.json` alatt, a setup/lock kimenetek ugyanitt maradnak;
ezek Gitből kizártak, nyers hangot nem tartalmaznak. A hardveres eszközindexeket
új gépen/sessionben az aktuális listából kell kiválasztani.

## 🟨 Korlátok és külön munka

- **Fizikai USB/headset kihúzás/visszacsatlakoztatás:** nem történt; a kijelölt
  bemenet beépített mikrofontömb. A leválasztás és a hibás driver API-jelzése
  integrációban injektált; ezt nem nevezzük valós eszközkihúzásnak.
- **Tiszta Windows 10/11 / hiányzó runtime:** #28 alatt továbbra is felhasználói
  döntésre halasztott. A #3/#16 nyitott elfogadása megmarad.
- **Engine/VAD/worker/STT replay/UI:** #5/#6/#18/#20/#7. Ez az audioforrás,
  nem kész feliratozó alkalmazás. Külön pipeline replay integráció #20 marad.
- **RTF/latency/WER, többgépes benchmark, hosszú stabilitás és OS-szintű hálózati
  bizonyítás:** külön M1 feladatok. Az itt mért tesztidő nem STT teljesítményállítás.
- **CI:** a normál Windows CI automatikusan gyűjti az új szintetikus audio
  teszteket. A konkrét PR-futás linkje és eredménye #4-ben és a megvalósítási
  PR-ben rögzített; a helyi tesztsiker önmagában nem állított Actions-siker.

Technikai szerződés és források: [audio.md](../audio.md).
