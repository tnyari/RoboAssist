# RoboAssist Windows csomag

Helyi, offline magyar beszédfelismerés Windows 10/11 x64 rendszeren. Az alkalmazás
nem küld hangot hálózatra, és a csomag modellsúlyt nem tartalmaz.

## Első használat

1. Bontsd ki a ZIP-et egy írható mappába.
2. Telepíts vagy másolj át egy modellt a külön
   [modellútmutató](_internal/models/README.md)
   szerint. Az útmutató rögzíti a szükséges fájlokat és SHA-256 ellenőrzést.
3. Indítsd a `RoboAssist.exe` fájlt, válassz mikrofont, modellt és nyelvet, majd
   kattints az **Indítás** gombra.

A részletes használatot, adatkezelést, hibaelhárítást és eltávolítást a
[Windows felhasználói útmutató](_internal/docs/user-guide.md) írja le. A helyi WAV replay
benchmark és annak annotációs sémája a
[benchmark útmutatóban](_internal/docs/benchmark-metrics.md)
van; valós méréshez jóváhagyott, annotált hangforrás szükséges.

A RoboAssist FFmpeg könyvtárakat használ LGPLv2.1 licenc alatt. A megfelelő
FFmpeg/PyAV forrásarchívumok és a buildrecept az
`_internal/licenses/upstream-sources/` és
`_internal/licenses/av-runtime/` könyvtárban találhatók; a felületen a
**Súgó → Névjegy** ablak is megadja ezeket az útvonalakat.

## Leállítás és eltávolítás

Állítsd le a felvételt az alkalmazásban, zárd be az ablakot, majd töröld a
kicsomagolt csomagmappát. A felhasználói adatkönyvtárba importált modell külön
marad; ha már nincs rá szükség, külön törölhető.

