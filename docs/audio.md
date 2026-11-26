# Mikrofon és WAV replay

**Feladat:** [#4](https://github.com/tnyari/RoboAssist/issues/4) ·
**Driverhiba-javítás:** [#33](https://github.com/tnyari/RoboAssist/issues/33).

## 🟦 Közös forrásszerződés

Az `offline_stt.audio` modul `MicrophoneSource` és `WavReplaySource` osztályai
ugyanazt az `AudioSource` pull-szerződést követik: `start()`, `read(timeout)`,
`stop()`, `close()`, `state`, `error` és `stats`. Az engine/UI nincs importálva.

- A `read()` egy saját memóriájú, alapból nem írható `AudioFrame`-et vagy timeoutnál
  `None` értéket ad. A kimenet mindig **16 kHz mono float32**, 20 vagy 30 ms-os
  frame-ekben; WAV végén a maradék frame rövidebb lehet, nincs kimeneti nullapótlás.
- A `start_sample`/`end_sample` egész mintaszám a session nullpontjától;
  `start_ms`/`end_ms` ezekből származik. Nincs falióra-alapú összefűzés vagy
  frame-enként felhalmozódó időbélyeg-kerekítés. A mintaszám csatornánként értendő.
- Állapotok: idle/running/ended/stopped/error/closed. Az EOF `ended`; a forráshiba
  látható `AudioSourceError`, nem csendes EOF vagy üres siker.
- Egy forrást **egyetlen worker/vezérlő** olvas; a start/read/stop/close hívásokat
  sorosítani kell. A UI ezekhez később workerparancsot küld (#6/#20).
- Stopkor a forrás saját callback-puffere nullázódik, a pending frame-ek és a
  resampler állapota ürül. Az előzőleg átadott frame-ek a fogyasztó tulajdonai;
  azok referenciáinak törlése a fogyasztó/session feladata. Ez nem biztonságos
  memóriatörlési garancia az összes Python/FFmpeg-másolatra.
- Stop után Start új sessiont és nulláról induló mintaszámot ad; Close végleges.
  Driverlezárási hiba után a bizonytalan állapotú forrás nem indítható újra.

## 🎙️ Eszközlista és explicit capture

A fejlesztői setup után:

```powershell
.\.venv\Scripts\python.exe -m offline_stt.audio devices
# A fenti listából válassz indexet; ez csak példa, nem tartós eszközazonosító:
.\.venv\Scripts\python.exe -m offline_stt.audio microphone --device 1 --rate 48000 --channels 1 --seconds 3
```

Az eszközlistázás nem indít capture-t. A mikrofonpróba külön parancs, egyértelmű
indítás/leállítás jelzéssel; 0,1–30 másodperces célidővel. Csak számlálókat és
összesített peak/RMS jelszintet ír ki, hangot vagy átiratot nem ment. A 30 ms-os
frame-ek teljes frame-határig tarthatnak, ezért a mintaszám legfeljebb egy
frame-mel meghaladhatja a megadott időhöz tartozó mintaszámot.

Az `input_devices()` indexet, host API-t, nevet, max. bemeneti csatornaszámot és
alaprátát ad vissza. Az API-végpontok száma nem fizikai mikrofonok száma.
Az index Windows/PortAudio újraindítás vagy eszközváltozás után eltérhet; az
eszközválasztást az aktuális listából kell elvégezni. A kiválasztott rate/channels
kombinációt a start ténylegesen ellenőrzi és megnyitja; nincs csendes fallback.

### Callback és túlterhelés

A PortAudio callback kizárólag egy **előre lefoglalt SPSC gyűrűpufferbe** másol,
és számlálókat/hibaállapotot frissít. Nincs callbackbeli resampling, STT, UI,
fájlírás, alvás, lockvárakozás vagy felhasználói feldolgozó hívása.

A puffer alapból 25 bemeneti blokk (20 ms-nál 500 ms, 30 ms-nál 750 ms),
konfigurálható 2–500 blokkig; túlterheléskor nem nő. A slot másolás után publikált,
és csak az olvasói másolat elkészülte után szabadul fel. Ez a rögzített
CPython 3.11 GIL-re és az egy producer/egy reader szerződésre épül; nem hard
real-time vagy szabad szálkezelésű Python-garancia. A NumPy másolás átengedheti a
GIL-t; a slot még nem újrafelhasználható ezalatt.

Puffertelítődés, PortAudio status-hiba, váratlan streamvég vagy callback timeout
látható forráshiba. A `stats` tartalmazza az input/output mintaszámot, elveszett
blokkokat/mintákat, overflow-eseményt és legnagyobb pufferfoglaltságot.
Adatvesztés után nem tömörítjük össze a hang időalapját és nem gyártunk csendet:
a forrás hibára áll és lezárja a streamet. A stats pillanatfelvétel, nem a későbbi
benchmark teljes metrikarendszere (#8).

## 🟦 Resampling és PCM16

Az `AudioNormalizer` a már lockolt **PyAV 18.1.1 / libswresample** állapottartó
szűrőjét használja. PyAV most közvetlen függőség is; új csomagverzió nincs.
Stereo esetén a downmix a két csatorna számtani átlaga. Nem frame-enként újrainduló
szűrőt vagy mintavétel-eldobásos decimálást használunk. A feldolgozás a `read()`
oldalán fut, tehát a későbbi workerben kell meghívni.

A bemeneti float32 tömb alakja `(minták, csatornák)`; csak véges értékeket fogad.
A megadott bemeneti mintaszámnak folytonosnak kell lennie. WAV EOF-kor a filter
10 ms nullabemenettel kifut, de a kimenet pontosan
`ceil(bemeneti_minták * 16000 / bemeneti_rate)` mintára vágódik; a nullabemenet
nem ad hozzá lejátszott időt. A legutolsó frame megőrzi a valódi hosszt.

A `pcm16_bytes()` adapter little-endian PCM16-ot ad kerekítéssel és szaturációval;
nem csordul át a +1,0 érték negatív tartományba. Az alap pipeline-típus float32
marad, a PCM16 csak az azt igénylő későbbi adapterekhez használható.

## ⏱️ Helyi WAV replay

```python
from offline_stt.audio import SourceState, WavReplaySource

source = WavReplaySource("sajat-helyi-minta.wav")
try:
    source.start()
    while source.state == SourceState.RUNNING:
        frame = source.read(timeout=0.1)
        if frame is not None:
            # Ugyanezt az AudioFrame-et kapja majd a worker/pipeline.
            pass
finally:
    source.close()
```

Csak explicit helyi, tömörítetlen mono/stereo **PCM8/16/24/32 WAV** támogatott.
Float WAV, tömörített WAV vagy nem támogatott header érthető hibát ad.
A fájlt nem tölti egészében memóriába: 20 ms bemeneti blokkokkal olvas,
azonos normalizálón és frame-szerződésen keresztül.

A frame esedékessége `monotonic_start + end_sample / 16000`, alapból 20 ms-os
kimenettel. A fogyasztó feldolgozási ideje nem adódik minden új határidőhöz;
késéskor az esedékes frame-ek azonnal elérhetők, az audio-időbélyegek nem tolódnak.
Ez legjobb szándékú OS-ütemezés, nem garantált 20 ms falióra-pontosság.
A bounded worker/backlog kezelése és a STT replay integráció #18/#20 feladata.

## 🧪 Ellenőrzés és korlátok

A normál CI szintetikus PCM-et készít a teszt ideiglenes könyvtárában, és a
mikrofon driverhatárát fake backenddel ellenőrzi; valódi mikrofont nem nyit.
Lefedett: chunkfüggetlen resampling, anti-alias, amplitúdó, pontos mintaszám,
PCM szélsőértékek, abszolút replay-óra, valódi faliórás pacing, újraindítás,
overflow/stall/injektált leválasztás és hibás erőforráslezárás.

A [tényleges célgépes riport](reports/issue-4-audio.md) külön jelöli a valódi
mikrofonpróbát és az injektált eszközhibát. Fizikai eszközkihúzás, többgépes
benchmark, STT/VAD/UI és hosszú stabilitási mérés nincs késznek állítva.
A tiszta Windows-próba továbbra is halasztott [#28](https://github.com/tnyari/RoboAssist/issues/28).

Források: [sounddevice callback-szerződés](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html),
[PyAV audio/resampler API](https://pyav.basswood.io/docs/stable/api/audio.html).
A konkrét PyAV 18.1.1 viselkedését a lockból telepített csomagon is ellenőriztük.
