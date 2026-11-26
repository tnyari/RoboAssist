# Modellek

A [manifest](manifest.json) két többnyelvű Systran faster-whisper modellt rögzít.
Mindegyik forrásfájlnak konkrét revisionje, mérete és SHA-256 értéke van.
A modellkártyák deklarált nyelvei között szerepel a magyar (`hu`). Ez nyelvtámogatási
metaadat, nem helyi pontosságmérés. A tárolt súly FP16; betöltéskor a CPU INT8
számítást a CTranslate2 végzi, ezen a gépen a tényleges típus `int8_float32`.

| Logikai azonosító | Forrás / revision | Forrásfájlok összesen |
|---|---|---|
| base-multilingual | [Systran/faster-whisper-base](https://huggingface.co/Systran/faster-whisper-base/tree/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66), `ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66` | 147 884 932 byte |
| small-multilingual | [Systran/faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small/tree/536b0662742c02347bc0e980a01041f333bce120), `536b0662742c02347bc0e980a01041f333bce120` | 486 214 370 byte |

## Explicit telepítés

A repó gyökeréből, csak a felhasználó explicit letöltési kérése után:

```powershell
.\.venv\Scripts\python.exe -m offline_stt.engines install base-multilingual --allow-network
.\.venv\Scripts\python.exe -m offline_stt.engines install small-multilingual --allow-network
```

A két forrás együtt 634 099 302 byte. Az installer a `models/cache/` alatt ideiglenes
könyvtárba ír, streamelés közben méretet/hash-t ellenőriz, mellékeli a licencet,
majd csak teljes ellenőrzés után aktivál. A `install-receipt.json` rögzíti a forrást,
revisiont, fájlokat és telepítési módot. Meglévő sérült telepítést nem ír felül.
Hálózat nélkül egy előzőleg beszerzett, ugyanilyen forrásfájlokat tartalmazó könyvtár
is importálható; annak tartalmát ugyanahhoz a manifesthez ellenőrzi:

```powershell
.\.venv\Scripts\python.exe -m offline_stt.engines install base-multilingual --from-directory C:\Models\faster-whisper-base
```

Más munkakönyvtárból az alparancs elé tedd a teljes `--catalog` és `--root` útvonalat.
A hálózati kapcsolók csak a külön installerre vonatkoznak. A futásidejű engine
csak helyi könyvtárat kap, teljes ellenőrzéssel; hiány/sérülés látható hiba.

## Helyi ellenőrzés

```powershell
.\.venv\Scripts\python.exe -m offline_stt.engines verify base-multilingual
.\.venv\Scripts\python.exe -m offline_stt.engines smoke base-multilingual
.\.venv\Scripts\python.exe -m offline_stt.engines verify small-multilingual
.\.venv\Scripts\python.exe -m offline_stt.engines smoke small-multilingual
```

A verify nem tölt be neurális modellt. A smoke valódi helyi modellt tölt be egyszer,
külön warm-up után két reset/flush ciklust futtat szintetikus csenden. Nem ment
hangot/átiratot, és nem pontosságmérés vagy benchmark. A CLI maga nem telepít
hálózati tűzfalat; a [#5 riport](../docs/reports/issue-5-engine.md) külön DNS/TCP-tiltással
futtatott próbát is dokumentál.

## Licenc és Git

A két rögzített modellkártya MIT licencet jelöl. A [Whisper licencszöveg](WHISPER_LICENSE.txt)
az [OpenAI Whisper rögzített upstream forrásából](https://github.com/openai/whisper/blob/86098128c0b4f24f0e2aa2994de830614b474227/LICENSE)
származik; hash-e és forrása a manifestben van. Az installer ezt `LICENSE.txt` néven
mellékeli. A RoboAssist saját forráskódjának licence MIT ([LICENSE](../LICENSE)); a
független modell- és függőségfeltételeket, illetve a még nyitott csomagolási kérdéseket
a [#25 licencaudit](../docs/reports/issue-25-license-audit.md) követi.

Súly, cache és letöltés nem kerül Gitbe. Futás közben nincs automatikus letöltés.

