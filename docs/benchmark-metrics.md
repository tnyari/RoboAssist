# Benchmark metrikák

## Adatgyűjtés

- A `PipelineStats` tartalmazza a bemeneti hangidőt, a részleges és végső dekódolások idejét, az ismételten feldolgozott mintákat, a várólisták csúcsát és az eldobásokat. Az RTF nevezője az elfogadott és eldobott hangminták összege; az eldobás külön mező marad, az ismételt munka pedig külön idő- és aránymutató.
- A `MainWindow` opcionális `presentation_callback` függvénye az elfogadott esemény aktuális verzióját és a Qt-festés befejezése utáni monotonic időbélyeget adja át. Az opcionális `stats_callback` a legutóbbi `PipelineStats` pillanatképet küldi, 100 ms-os UI lekérdezési ütemben. Mindkét callback legyen gyors, csak memóriába írjon, és ne dekódoljon.
- Az `evaluate_annotations()` az annotált beszédkezdet/vég és a megfestett partial/final események alapján számolja a késleltetést. A VAD végpontkésés külön szerepel. Az időbélyegekhez a `PipelineStats.source_started_monotonic_ns` értékét használd.
- Windows alatt a `ProcessTreeSampler` a RoboAssist folyamatot és pillanatnyilag élő leszármazottait méri. Először baseline mintát kell venni, utána azonos időközönként mintázni. A CPU százalék a teljes gép logikai processzorkapacitására normalizált; a working set a folyamatfán összeadott pillanatnyi érték, a riport pedig a minták maximumát tárolja.

## Riport és adatvédelem

`BenchmarkReport` tartalmazza a hardver-, modell-, hash-, verzió-, szál-, nyelv-, teszt- és paraméteradatokat. Az `export_report()` JSONL, CSV és Markdown összesítést ír új, run ID-val jelölt könyvtárba. A meglévő futáskönyvtárat nem írja felül. Nyers referencia és hipotézis alapértelmezés szerint nem kerül exportba; a `transcripts.jsonl` csak az `include_transcript=True` explicit kapcsolóval jön létre.

A metrikák számítását szintetikus, ismert példák fedik le. Ez a metrikakód és az export ellenőrzése, nem beszédpontossági vagy teljesítménybenchmark. A jóváhagyott, annotált magyar korpusz és az M1 hardverkategóriás futások a #21/#23 feladatokban készülnek; addig teljesítménycél eléréséről nem teszünk állítást.
