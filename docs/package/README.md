# RoboAssist Windows csomag

Helyi, offline magyar beszédfelismerés Windows 10/11 x64 rendszeren. Az alkalmazás
nem küld hangot hálózatra, és a csomag modellsúlyt nem tartalmaz.

## Első használat

1. Bontsd ki a ZIP-et egy írható mappába.
2. Indítsd a `Start-RoboAssist.cmd` fájlt. Ez ellenőrzi a Microsoft Visual C++
   x64 futtatókörnyezetet; ha a legalább 14.52.37029.0 verzió hiányzik, a
   mellékelt, hash-rögzített Microsoft telepítő UAC-jóváhagyást kérhet. Az app
   saját futása nem igényel rendszergazdai jogot.
3. Telepíts vagy másolj át egy modellt a külön
   [modellútmutató](_internal/models/README.md)
   szerint. Az útmutató rögzíti a szükséges fájlokat és SHA-256 ellenőrzést.
4. Válassz mikrofont, modellt és nyelvet, majd
   kattints az **Indítás** gombra.

A `RoboAssistModels.exe` parancssori eszköz használata előtt futtasd egyszer a
`Prepare-RoboAssist.ps1` fájlt; hálózati modelltöltés továbbra is csak külön,
`--allow-network` kapcsolóval indítható.

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

A Microsoft VC Redistributable telepítőjének verzióját és hashét a csomag
`_internal/runtime/vc-runtime.json` fájlja rögzíti. A terjesztésre a Microsoft
Visual Studio licencfeltételei vonatkoznak; az audit a #54 jegyben követi ezt.

## Leállítás és eltávolítás

Állítsd le a felvételt az alkalmazásban, zárd be az ablakot, majd töröld a
kicsomagolt csomagmappát. A felhasználói adatkönyvtárba importált modell külön
marad; ha már nincs rá szükség, külön törölhető.


