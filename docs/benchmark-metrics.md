# Benchmark metrikák

## Adatgyűjtés

- A `PipelineStats` tartalmazza a bemeneti hangidőt, a részleges és végső dekódolások idejét, az ismételten feldolgozott mintákat, a várólisták csúcsát és az eldobásokat. Az RTF nevezője az elfogadott és eldobott hangminták összege; az eldobás külön mező marad, az ismételt munka pedig külön idő- és aránymutató.
- A `MainWindow` opcionális `presentation_callback` függvénye az elfogadott esemény aktuális verzióját és a Qt-festés befejezése utáni monotonic időbélyeget adja át. Az opcionális `stats_callback` a legutóbbi `PipelineStats` pillanatképet küldi, 100 ms-os UI lekérdezési ütemben. Mindkét callback legyen gyors, csak memóriába írjon, és ne dekódoljon.
- Az `evaluate_annotations()` az annotált beszédkezdet/vég és a megfestett partial/final események alapján számolja a késleltetést. A VAD végpontkésés külön szerepel. Az időbélyegekhez a `PipelineStats.source_started_monotonic_ns` értékét használd.
- Windows alatt a `ProcessTreeSampler` a RoboAssist folyamatot és pillanatnyilag élő leszármazottait méri. Először baseline mintát kell venni, utána azonos időközönként mintázni. A CPU százalék a teljes gép logikai processzorkapacitására normalizált; a working set a folyamatfán összeadott pillanatnyi érték, a riport pedig a minták maximumát tárolja.
- A modellbetöltés és warm-up a replayforrás indulása előtt történik, ezért az audioalapú WER/RTF/késleltetés nem tartalmazza. A folyamatfa CPU-átlaga a startupot is tartalmazza; a riport ezt a paraméterben jelzi.

## Riport és adatvédelem

`BenchmarkReport` tartalmazza a hardver-, modell-, hash-, verzió-, szál-, nyelv-, teszt- és paraméteradatokat. Az `export_report()` JSONL, CSV és Markdown összesítést ír új, run ID-val jelölt könyvtárba. A meglévő futáskönyvtárat nem írja felül. Nyers referencia és hipotézis alapértelmezés szerint nem kerül exportba; a `transcripts.jsonl` csak az `include_transcript=True` explicit kapcsolóval jön létre.

## Replay futtatása

A fejlesztői környezet aktiválása után minden konfiguráció egyedi run ID-val indítható a repo gyökeréből:

```powershell
python -m offline_stt.benchmark_replay `
  --wav C:\Benchmark\approved-test.wav `
  --annotations C:\Benchmark\approved-test.jsonl `
  --run-id hu-mid-base-2t-r1 `
  --test-id hu-approved-v1 `
  --hardware-category mid `
  --model base-multilingual `
  --threads 2 `
  --output-parent C:\Benchmark\results
```

Futtasd konfigurációnként legalább három egyedi run ID-val, majd ismételd meg az elérhető 2/4/8 threadszámokkal. A hardware kategóriát a futtató adja meg; a riport külön rögzíti a CPU nevét és a logikai processzorszámot. A runner 20 ms-os helyi WAV replayt használ, lokálisan ellenőrzi a modellt, és kényszeríti a HF offline/telemetry tiltást. Modellletöltést nem indít.

Az annotációs JSONL minden sora az `utterance_id`, `speech_start_ms`, `speech_end_ms`, `reference_text` és `critical_fields` mezőket tartalmazza. A kritikus mezők értéke `{ "value": "...", "kind": "text|integer|decimal|identifier" }` alakú. Példa egy teljesen szintetikus annotációra:

```json
{"utterance_id":"synthetic-1","speech_start_ms":0,"speech_end_ms":900,"reference_text":"Minta utca tizenkettő","critical_fields":{"address_number":{"value":"12","kind":"integer"}}}
```

Az audiofájl és az annotáció a helyi útvonalán marad; riportba nyers átirat csak a külön `--include-transcript` kapcsolóval kerül. `--output-parent` megadása szükséges, és létező run könyvtár soha nem íródik felül.

A metrikák számítását szintetikus, ismert példák fedik le. Ez a metrikakód és az export ellenőrzése, nem beszédpontossági vagy teljesítménybenchmark. A jóváhagyott, annotált magyar korpusz és az M1 hardverkategóriás futások a #21/#23 feladatokban készülnek; addig teljesítménycél eléréséről nem teszünk állítást.
