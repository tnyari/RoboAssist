# VAD, korlátos ütemezés és session pipeline

**Feladat:** [#6](https://github.com/tnyari/RoboAssist/issues/6), aljegyek #18/#19/#20,
EOF-drain regresszió #38. A [#4 audioforrásokat](audio.md) és a
[#5 helyi engine-t](engine.md) köti össze. A Windows UI bekötése #7 feladata.

## Feldolgozás és szálak

```mermaid
flowchart LR
  OWNER[Session tulajdonos / későbbi UI] --> CHILD[Windows spawn session-folyamat]
  CAP[Forrás saját callback-puffere] --> READ[Audio reader szál]
  READ --> FQ[Korlátos frame queue]
  FQ --> VAD[Energia-VAD és szegmensütemező]
  VAD --> JOBS[Final FIFO + legfeljebb egy partial]
  JOBS --> DEC[STT decoder szál]
  DEC --> PIPE[Csak esemény és metrics IPC]
  PIPE --> OUT[Korlátos tulajdonosi eseménypuffer]
  OUT --> OWNER
```

A forrás létrehozása/start/read/close műveleteit egy reader szál végzi. A capture
callback a #4 rövid, korlátos ring-pufferét használja; nem VAD-ol és nem dekódol.
A frame queue `put_nowait` művelete nem vár kapacitásra. A VAD a session-folyamat
főszálán fut; a modell létrehozása, egyszeri load/warm-up, reset/push/decode/close
mind egyetlen STT decoder szálon történik. A UI csak immutable eseményeket olvas.

A session saját [Python 3.11 spawn folyamatot](https://docs.python.org/3.11/library/multiprocessing.html#contexts-and-start-methods)
használ. Így a beragadt forrásolvasás vagy natív inference is megszüntethető Stop
timeout esetén. A factory legyen importálható modulban definiált, pickelhető
callable, amely csak a meghíváskor nyit erőforrást. Élő stream/modell nem adható át.
A lifecycle metódusokat a tulajdonos sorosan hívja; UI-n ezek vezérlő workerre
valók. A `drain_events()` és `stats` másik szálról is olvasható.

## Beállítások és memóriahatár

A teljes, szigorú schema-v1 [TOML](../configs/default.toml) két VAD-mezővel és új
`[pipeline]` táblával bővült. Régi saját konfigurációnál ezeket a mezőket át kell
venni a mintából; hiányzó mező továbbra is látható `ConfigError`, nincs csendes
alapértékpótlás. A privacy/export-szabályok változatlanok.

| Beállítás | Alapérték / jelentés |
|---|---|
| vad.pre_roll_ms | 250 ms; pontos mintaszámú előzmény |
| vad.end_silence_ms | 500 ms; frame-végre kerekített végpont |
| vad.max_segment_ms | 12000 ms; hosszú beszéd nem átfedő finalokra vágva |
| vad.energy_threshold_db | −42,0 dBFS; RMS-alapú beszédkezdési küszöb |
| vad.hysteresis_db | 6,0 dB; aktív szakasznál alacsonyabb elengedési küszöb |
| pipeline.partial_interval_ms | 750 ms; audiominta-óra szerinti frissítés, frame-végre kerekítve |
| pipeline.partial_window_ms | 5000 ms; gördülő partial, a max. szegmensre is korlátozva |
| pipeline.frame_queue_capacity | 64, legfeljebb 480 mintás / 30 ms frame |
| pipeline.final_queue_capacity | 4 pending final + legfeljebb 1 pending partial |
| pipeline.event_queue_capacity | 64, eseményenként legfeljebb 32768 szövegkarakter |
| pipeline.stop_timeout_ms | 5000 ms, megengedett tartomány 1000–60000 ms |

A session 100 ms-onként küldött számlálója az aktuális bemeneti RMS-szintet dBFS-ben
(`input_level_dbfs`, −120 dBFS padló), valamint a decoder foglaltságát (`decoder_busy`)
is tartalmazza. Ezek a GUI jelszintmérőjét és feldolgozásjelzését táplálják; nem
helyettesítik a #8 CPU/RAM-, késleltetés- vagy minőségi benchmarkját.

A kezdő VAD egyszerű energia-kapu, nem neurális beszédfelismerő. Hangos zajt is
beszédnek vehet, halk beszédet kihagyhat. Küszöb/hiszterézis és végpont hangolása,
zajos/valós magyar beszédmérés a #8 benchmarkhoz tartozik; ezek nem mért minőségi
állítások. Nincs új függőség, VAD-modell vagy letöltés.

Az audiomemória a pre-roll, egy max. szegmens, a frame queue, a korlátos pending
finalok/partial és egy in-flight decode ablak összege szerint korlátozott; nem nő
a session hosszával. A decoder saját belső modellmemóriája külön erőforrás.
A [queue](https://docs.python.org/3.11/library/queue.html#queue.Queue.put_nowait)
kapacitására a producer nem vár. Frame/full-final túlterhelés látható hibát ad,
mert audiohézagból nem készítünk sikeres átiratot. A #38 javítás producer-done után
újraolvassa a frame sort: az Empty és done közé érkezett utolsó blokk sem vész el.

## Ütemezés és események

A Whisper ablakosan újradekódol, nem natív streaming. A partial a legutóbbi 5 s
ablak, a final az egész, legfeljebb 12 s VAD-szegmens. Final FIFO elsőbbséget kap;
a pending partial lecserélhető. A már futó natív decode nem preemptálható: ha
közben elavul vagy final érkezik, eredménye nem kerül a kimenetre. A következő
munka final lesz. Nem ígérünk 750 ms-os tényleges feliratkésleltetést.

A `TranscriptEvent` mezői:

| Mező | Szerződés |
|---|---|
| schema_version | 1 |
| session_id | Új Startnál új UUID hex; restartból régi esemény nem olvasható |
| segment_id | Session-azonosító + monoton szegmenssorszám |
| revision | Szegmensen belül növekvő, a consumer kihagyott revíziót is kaphat |
| source / language | microphone vagy wav / explicit konfigurált nyelv |
| type | partial vagy final |
| audio_start_ms / audio_end_ms | Session-relatív 16 kHz mintaszámból; nincs falióra |
| text | Teljes szegmenshipotézis; ugyanazon azonosítón cserélendő, nem appendelendő |
| emitted_monotonic_ms | Decoder-worker indulása óta eltelt monoton idő, load/warm-up alatt is telik |
| stable_prefix | Két egymást követő hipotézis közös szóprefixe; partialnál még felülvizsgálható |
| confidence | None; nincs kalibrált valószínűség |

A consumer `(session_id, segment_id)` alapján cseréli a partialt. Időben átfedő
ablakoknál kisbetű/írásjel-normalizálással közös suffix/prefix illesztés történik;
azonos ablak új szövege felülírja a korábbit. Bizonytalan illesztésnél a partial
felülvizsgálható: a végleges szöveg a teljes VAD-szegmens final dekódolásából jön.
Csak az átfedő idejű, azonos backend-szegmenseket deduplikáljuk; a külön időben
elhangzó „igen igen” megmarad. Ez a baseline nem ad szószintű igazolt időbélyeget.

Final ugyanazon szegmensre legfeljebb egyszer készül, immutable dataclassként.
Régi partial vagy újabb decode nem módosíthatja. Üres final megengedett: így a
rövid szegmens téves partialja törölhető; tiszta csend nem indít szegmenst.
A kimeneti puffer partialokat összevon/eldob; final nem vész el csendben. Ha a
consumer nem olvas, és csak finalokkal megtelik, a session látható hibát kap és
leállítást kér. A tulajdonosnak rendszeresen drain-elnie kell.

## Életciklus és használat

```python
from offline_stt.config import load_config
from offline_stt.pipeline import LocalEngineFactory, Session, WavSourceFactory

def main():
    config = load_config("configs/default.toml")
    session = Session(config, WavSourceFactory("explicit-input.wav"),
                      LocalEngineFactory(config, "models/manifest.json", "models/cache"))
    try:
        session.start()  # külön folyamat: load/warm-up és source.start
        while True:
            done = session.wait(0.05)
            events = session.drain_events()  # a UI számára memóriában
            if done:
                break
        if session.error:
            raise RuntimeError(session.error)
    finally:
        session.close()

if __name__ == "__main__":  # Windows spawn belépési védelem kötelező
    main()
```

Mikrofonhoz például pickelhető `functools.partial(MicrophoneSource, device=...,
sample_rate=..., channels=...)` source factory adható meg; Start explicit nyitja
meg. Nem indul automatikus mikrofonfelvétel. Az eszközparaméterekhez lásd #4.

- `start(timeout=30)`: új session, egy helyi modell-load/warm-up; hiányzó modellnél
  látható hiba, capture nem indul. Startup timeout után külön Stop budget takarít.
- `wait(timeout)`: EOF-ra vár, timeoutnál False; nem kényszerít leállítást.
- `stop(timeout=...)`: új input leállítása, elfogadott frame-ek drain-je, maradék
  szegmens egyszeri finalja. Ismételhető. Timeoutnál terminate/kill, a befejezetlen
  szegmens eldobott és PipelineError látható; nincs sikernek jelölt hamis final.
- Forrás-/decoder-/cleanup hiba: ERROR, pending kimenet törölve; a tulajdonos
  Stop/close hívással érvényesíti a leállítási határidőt. Új Start tiszta folyamatot
  és új session_id-t kap. Egy korábbi session modellje nem marad futó folyamatban.
- `reset()`: Stop + erőforráslezárás, események/session_id törlése, IDLE.
- `close()`: ugyanez véglegesen CLOSED állapottal. A kimeneti memória törlődik;
  a consumerhez korábban átadott objektumok kezeléséért a consumer felel.

A timeout a kényszerleállításra is tartalékol időt. OS-szintű megszüntetési hiba
látható PipelineError, nem sikerjelzés. A session saját IPC-csöve lezárás után
eldobódik, restart nem használja újra. Az állapotot és error mezőt minden session
végén ellenőrizni kell; normál Stop is jelezhet forrás- vagy decoderhibát.

## Metrikák és explicit replay smoke

A `stats` frame-/mintaszámot, dropped frame/sample számlálót, aktuális/maximális
frame/job backlogot, eldobott partial/rejected final számot, külön partial/final
decode darabszámot/időt, összes és újradekódolt audiomintát, egyszeri load/warm-up
számlálót és forced termination/kimeneti túlterhelést ad. A backlog periodikus
pillantkép, nem időzítési szinkronizációs feltétel. A repeated_decode_samples az
ugyanazon szegmens korábban dekódolt tartományával vett metszetet számolja.

```powershell
.\.venv\Scripts\python.exe -m offline_stt.pipeline --wav C:\Audio\explicit-input.wav
```

A modell előzetesen, külön és explicit telepített kell legyen. A parancs csak
metaadatot/eseményszámot ír ki, átiratot nem. Nem ment hangot, átiratot vagy
metrikafájlt. A [#6 riport](reports/issue-6-pipeline.md) különíti el a szintetikus
CI-t és a célgépen, valódi helyi modellekkel futtatott működési próbákat.
