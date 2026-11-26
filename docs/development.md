# Fejlesztői indulás

## 🟦 Aktuális állapot

A repó dokumentációs és feladatkezelési alapjai elkészültek. A könyvtárak vázak; nincs futtatható STT kód, telepíthető Python csomag, dependency lock vagy CI workflow.

A kapott terv Python 3.11 x64-et, PySide6-ot és faster-whisper CPU INT8 baseline-t javasol. A konkrét kompatibilis verziók rögzítése [#16](https://github.com/tnyari/RoboAssist/issues/16), a Windows CI [#17](https://github.com/tnyari/RoboAssist/issues/17) feladata.

## 🧭 Első fejlesztési lépések

1. Olvasd el az [AGENTS.md](../AGENTS.md) és [GitHub munkarend](github-workflow.md) fájlokat.
2. A GitHub bővítménnyel nézd át [#3](https://github.com/tnyari/RoboAssist/issues/3), [#16](https://github.com/tnyari/RoboAssist/issues/16) és [#17](https://github.com/tnyari/RoboAssist/issues/17) feltételeit.
3. Windows x64 / Python 3.11 környezetben készítsd el a csomagmetaadatokat és a verziórögzített lockot; az alapbeállítások mintája a [configs/default.toml](../configs/default.toml).
4. Tiszta környezetben ellenőrzött telepítési parancsokkal egészítsd ki ezt a dokumentumot.
5. Az első implementációs teszteket az audio/engine/pipeline kóddal együtt készítsd; a CI a tényleges ellenőrzéseket futtassa.
6. A [roadmap](https://github.com/tnyari/RoboAssist/issues/2) szerint haladj; M2 előtt az M1 kapu kötelező.

A modelltelepítés külön, explicit hálózatos lépés lehet. Futás közben hiányzó modellnél hiba kell, automatikus hálózati fallback nem.

## ✅ Ellenőrzési terv

Windows CI: lint, typecheck, unit és kis replay integrációs teszt; teljes modellbenchmark manuálisan/dedikált runneren. A tényleges parancsok és rögzített eszközverziók #17 részei.

Hardveres mikrofon-, háromgépes teljesítmény-, offline DNS/HTTP-, 30 perces és 8 órás stabilitási tesztek későbbi M1 aljegyek. VCC teszthívás csak M2-ben, megfelelő tesztkörnyezetben.

A projektlicenc véglegesítése [#25](https://github.com/tnyari/RoboAssist/issues/25); jelenleg nincs LICENSE fájl vagy feltételezett MIT-engedély.
