# RoboAssist Windows feliratablak

## Első indítás

### Fejlesztői futtatás

1. Futtasd a fejlesztői setupot a [fejlesztői útmutató](https://github.com/tnyari/RoboAssist/blob/main/docs/development.md) szerint.
2. Telepítsd vagy importáld a `base-multilingual` vagy `small-multilingual` modellt a
   [modellútmutató](../models/README.md) szerint.
3. Indítsd a `roboassist.exe` parancsot a repó gyökeréből.

### Hordozható Windows csomag

1. Csomagold ki a verziózott ZIP-et egy olyan mappába, ahová a felhasználód írhat.
2. Indítsd a `RoboAssist.exe` fájlt. A modellkönyvtár nincs a ZIP-be építve.
3. Nyiss PowerShellt a kicsomagolt mappában, és importáld a külön, hash-ellenőrzött
   modellkönyvtárat a mellékelt modellkezelővel:

   ```powershell
   .\RoboAssistModels.exe install base-multilingual --from-directory C:\Models\faster-whisper-base
   .\RoboAssistModels.exe verify base-multilingual
   ```

   A `small-multilingual` modellhez cseréld ki a modellazonosítót és a könyvtárat.
   A telepítő a fájlokat ellenőrzi, majd az alkalmazás helyi adatkönyvtárába másolja.
4. Válassz mikrofont, helyi modellt és nyelvet, majd kattints az **Indítás** gombra.

Hálózati letöltés külön, felhasználó által indított műveletként érhető el:

```powershell
.\RoboAssistModels.exe install base-multilingual --allow-network
```

Az alkalmazás és a GUI indítása nem tölt le modellt.

A csomag onedir elrendezésű, nem végez rendszerszintű telepítést. Eltávolításhoz
zárd be az alkalmazást és töröld a kicsomagolt mappát. Az alkalmazás helyi
adatkönyvtárában tárolt modellek külön maradnak; csak akkor töröld őket, ha már
nincs rájuk szükséged. A tiszta Windows 10/11 próba a [#24](https://github.com/tnyari/RoboAssist/issues/24)
része, és még nem igazolt.

## Használat

- A státusz mutatja, hogy a modell betölt, a mikrofon figyel, beszéd feldolgozása
  zajlik, vagy hiba történt. A bemeneti mérő a session worker által számított
  dBFS-szintet jeleníti meg.
- Az ideiglenes felirat halvány, a végleges szöveg normál színű. A feliratablak
  automatikusan követi a legújabb szöveget, ha a görgetősáv alján áll.
- A **Törlés** a jelenleg látható szöveget üríti; a már futó szegmens újabb
  revízióit is elrejti. A **Másolás** a vágólapra másol. A **TXT export…** csak a
  fájl kiválasztása és mentése után ír lemezre.
- A feliratablak legfeljebb 2 000 szegmenst és 100 000 karaktert tart memóriában;
  hosszú sessionnél a legrégebbi megjelenített szöveget törli és ezt jelzi.
- A **Mindig felül** beállítás és az ablak mérete megmarad a következő indításra.
- A **Súgó → Névjegy** az FFmpeg LGPLv2.1 tájékoztatását és a Windows csomagban
  található forrásarchívumok/buildrecept útvonalát mutatja.
- **Leállításkor** a session lezárja a mikrofont, kiüríti a belső audiopuffereket,
  majd törli a felirat memóriabeli tartalmát. Ha szükséged van az átiratra, exportáld
  vagy másold ki a leállítás előtt.

## Benchmark reprodukció

A helyi WAV replay futtatása, az annotációs JSONL séma, a 2/4/8 szálas mátrix és
az adatvédelmi beállítások a [benchmark útmutatóban](benchmark-metrics.md) vannak.
A runner fejlesztői környezetből fut; jóváhagyott hangforrás nélkül nincs valós
beszédbenchmark vagy teljesítményállítás.

## Hibaelhárítás

- **Nincs telepített modell:** kövesd a modellek útmutatóját. A modell telepítése
  lehet explicit hálózati letöltés vagy előre letöltött fájlok offline importja;
  a feliratablak egyiket sem indítja el automatikusan.
- **A mikrofon nem indul:** frissítsd az eszközlistát, ellenőrizd a Windows
  mikrofonhozzáférést és válassz olyan bemenetet, amely mono capture-t támogat.
- **Audio frame eldobva vagy workerhiba:** állítsd le a sessiont, ellenőrizd az
  eszközt és próbáld újra. A folytonossági hibát a program láthatóan jelzi.
- A részletes CPU/RAM/RTF/késleltetés és beszédpontossági riport az M1 benchmark (#8)
  része; a GUI pillanatnyi sor- és dekódolásszámlálói nem benchmarkeredmények.

## Adatkezelés

Rögzítés csak **Indítás** után történik. Audio és átirat alapból memóriában marad;
hangfájlt az ablak nem készít. Nincs cloud STT, telemetry vagy futásidejű
modellletöltés. A másolás és a TXT export a felhasználó által indított művelet.
