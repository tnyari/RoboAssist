# RoboAssist Windows feliratablak

## Első indítás

1. Futtasd a fejlesztői setupot a [fejlesztői útmutató](development.md) szerint.
2. Telepítsd a `base-multilingual` vagy `small-multilingual` modellt a
   [modellútmutató](../models/README.md) szerint. A modelltelepítés külön, explicit
   lépés; az alkalmazás futás közben nem tölt le semmit.
3. Indítsd a `roboassist.exe` parancsot a repó gyökeréből.
4. Válassz mikrofont, helyi modellt és nyelvet, majd kattints az **Indítás** gombra.

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
- **Leállításkor** a session lezárja a mikrofont, kiüríti a belső audiopuffereket,
  majd törli a felirat memóriabeli tartalmát. Ha szükséged van az átiratra, exportáld
  vagy másold ki a leállítás előtt.

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

