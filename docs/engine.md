# Helyi SpeechEngine és CPU INT8 baseline

**Feladat:** [#5](https://github.com/tnyari/RoboAssist/issues/5).
Az adapter a [#4 audioforrások](audio.md) `AudioFrame` blokkjait fogadja.
A szerződés UI- és backendfüggetlen; a VAD, queue, ütemezés és stabil események a
[#6/#19 session pipeline-ban](pipeline.md) vannak. A UI bekötése #7 feladata.

## Szerződés

Minden engine-hívást ugyanaz a worker végezzen sorosan. A modellbetöltés és a
dekódolás szinkron, UI/capture callbackből nem hívható. Az objektum konstrukciója
nem tölt modellt és nem használ hálózatot.

| Művelet | Viselkedés |
|---|---|
| `load()` | Minden helyi modellfájl méret/SHA ellenőrzése, egyszeri CPU INT8 betöltés, külön warm-up; siker után ismételve nincs újratöltés |
| `push_audio(frame)` | 16 kHz mono float32 blokk másolása korlátos pufferbe; nincs dekódolás |
| `preview()` | Az aktuális ablak nyers, változható hipotézise, a puffer megtartásával |
| `flush()` | Teljes ablak dekódolása és elfogyasztása; ismételt üres flush nem adja vissza újra |
| `reset(start_sample=0)` | Session audio és időalap törlése/újrakezdése; a sikeresen betöltött modell megmarad |
| `close()` | Puffer ürítése, modell felszabadítása; ismételhető, utána új objektum kell |

A bemeneti mintaszámláló folytonos legyen; egy ablakban nem keverhetők a források.
`EngineInputError` vagy `EngineBufferFull` esetén a blokk nem fogyott el, javítás
vagy flush után újraadható. Az alap ablak 12 másodperc; nincs csendes eldobás.

A `DecodeResult` abszolút mintaszámokkal, nyelvvel, immutable szegmensekkel,
`final` jelzővel és dekódolási idővel tér vissza. A szegmensidők az ablakra
korlátozottak. A `final` az ablak elfogyasztását jelzi; a stabil, session-szintű
`TranscriptEvent` és deduplikáció #19 feladata. A lazy SDK generátor teljesen
elfogy a visszatérés előtt; hiba után nincs fél eredmény. Decode-hibánál explicit
reset kell, sikertelen load után reset + új load, vagy új engine.

```python
from offline_stt.config import load_config
from offline_stt.engines import FasterWhisperEngine, LocalModelStore

config = load_config("configs/default.toml")
store = LocalModelStore("models/manifest.json", "models/cache")
engine = FasterWhisperEngine.from_config(config, store)
try:
    engine.load()  # worker: fájlellenőrzés, betöltés és warm-up
    # engine.push_audio(frame)  # audioforrás olvasójától
    result = engine.flush()
finally:
    engine.close()
```

## Konfiguráció és életciklus

A TOML engine része továbbra is `faster-whisper`, `cpu`, `int8`, automatikus
letöltés nélkül. A `from_config` a modellazonosítót, nyelvet és VAD max. ablakát
használja. A `base-multilingual` és `small-multilingual` modellek a manifestben
szerepelnek; ismeretlen azonosító hiba. A beállítások nem indítanak capture-t.

Az `EngineOptions` alapértékei: `language="hu"`, `cpu_threads=4`,
`max_audio_seconds=12.0`, `max_new_tokens=224`. Korlátok: 1–64 szál,
0,02–60 másodperc, 1–448 új token. Explicit nyelv, beam=1, best_of=1,
temperature=0, előző szöveg nélküli dekódolás; nincs backend VAD vagy szóidőbélyeg.
Az állapot `UNLOADED`, `READY`, `ERROR` vagy `CLOSED`; a hiba látható kivétel és
`error` mező. Az unload hiba is látható, az engine ekkor is lezárt.

A `stats` modellbetöltés-, warm-up- és dekódolásszámot, külön időket, puffer- és
session-mintaszámot ad. A modellfájlok hash-elése nem része a load idejének;
a warm-up nem része a decode számlálónak/idejének. Reset a session számlálóját
törli, a modell élettartamára vonatkozó adatokat megtartja. Ezek alapmérések,
nem a #8 benchmark és nem teljes pipeline latency.

## Modellbiztonság és offline működés

A [modelltelepítés külön CLI](../models/README.md). A futásidejű modul nem
importálja a hálózati installert. Az engine minden szükséges fájlt ellenőriz,
csak ellenőrzött helyi könyvtárat ad át a faster-whispernek, `local_files_only=True`
módban. A tokenizer is helyi. HF offline és telemetriatilalmi változókat állít be.
Nincs modellnévvel indított SDK-letöltés, automatikus pótlás vagy float32 fallback;
az ellenőrzött tényleges compute típus `int8` vagy `int8_float32` lehet CPU-n.

A manifest rögzített revisiont, méretet, hash-t és licencforrást tartalmaz.
Symlink/útvonal-kiszökés, hiányzó/sérült fájl vagy ellenőrizetlen extra konfiguráció
hiba. Az install-receipt tájékoztató; a fájlokat a manifesthez ellenőrizzük.
A lokális fájlok használat közbeni külső módosítása ellen nem ad OS-szintű zárolást.

Audio és szöveg alapból memóriában marad; nincs export. Reset/close üríti a
belső audiopuffert, a hívónál korábban átadott eredmények kezeléséért a hívó felel.

## Ellenőrzések

Az offline fixture-tesztek szintetikus fájlokkal és lazy fake decoderrel
ellenőrzik a lifecycle-t, időbélyegeket, pufferkorlátot, hibákat és SDK opciókat.
A socket DNS/TCP tiltott. Nincs valódi súly vagy privát hang a CI-ben.
A [#5 riport](reports/issue-5-engine.md) külön rögzíti a valódi base/small
helyi telepítését és inference próbáját, valamint az el nem végzett ellenőrzéseket.
