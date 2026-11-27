# #25 projekt- és függőséglicenc-audit

**Frissítve:** 2026-11-27  
**Állapot:** részleges; a licencválasztás rögzítve, a Windows terjesztési átvétel nyitva.

## 🟦 Saját projektlicenc

A tulajdonos a feladat során **MIT** licencet választott a RoboAssist saját
forráskódjához. A [LICENSE](../../LICENSE) és a [harmadik fél közleményei](../../THIRD_PARTY_NOTICES.md)
ezt rögzítik. A választás nem vonatkozik a függőségekre vagy modellekre, és nem
minősíti a teljes Windows csomag terjesztési feltételeit.

## 🔍 Vizsgálati hatókör

Az audit a [Python hash lockra](../../requirements.lock), a
[conda-forge Windows x64 lockra](../../conda-av-win64.lock), a modellek
[verzió- és hash-manifestjére](../../models/manifest.json), a PyInstaller build
specifikációjára és az elkészült licenc-bundle leltárára támaszkodik. A build a
függőségek licenceit és upstream közleményeit a csomag `licenses/` könyvtárába
másolja. Ez reprodukálható leltár, nem jogi vélemény.

## 📦 PyAV és FFmpeg runtime

A Windows x64 / CPython 3.11 runtime a rögzített conda-forge csomagokat használja.

| Csomag | Build | Licencmetaadat | Artifact SHA-256 |
|---|---|---|---|
| `av` 17.1.0 | `py311h06a8702_0` | BSD-3-Clause | `978c663178d010a4d5bc2c76976abb96b132e8533c9e4d258f400e77935d619a` |
| `ffmpeg` 8.1.2 | `lgpl_haba0ffa_812` | LGPL-2.1-or-later | `903a1428dddb6a7568d82e767f0c793b6abcc621bd740bdde325be1889008f08` |

A teljes natív környezet **98 hash-rögzített conda-forge artifactból** áll. A
stage-elt DLL-zár 65 fájl, összesen 123,033,664 bájt; a manifest a fájlok
hash-eit és a 44 csomagtulajdonos licenc- és buildmetaadatait rögzíti. A pontos
zárhoz és buildhez tartozó licencszövegek, FFmpeg-receptek és manifest a
`licenses/av-runtime/` könyvtár része. A PE importzár vizsgálata nem talált
x264/x265 GPL-only DLL-t; ez a DLL-listára vonatkozó ellenőrzés, nem codec- vagy
terjesztési jogi minősítés.

### Rögzített FFmpeg 8.1.2 forrás és buildkonfiguráció

A lockolt `ffmpeg-8.1.2-lgpl_haba0ffa_812` conda-forge recept az upstream
[FFmpeg 8.1.2 forrásarchívumot](https://ffmpeg.org/releases/ffmpeg-8.1.2.tar.gz)
rögzíti (`SHA-256: 32faba5ef67340d54724941eae1425580791195312a4fd13bf6f820a2818bf22`).
A recept a conda-forge `ffmpeg-feedstock` `f639462076b7d4d708c8b0b5a447be6776ecf9cf`
commitjéből származik. A `recipe/build.sh` a `license_family != gpl` ágon
`--disable-gpl` kapcsolót ad át; a közös konfiguráció `--enable-version3`-at
állít be. Az elkészült FFmpeg 8.1.2 bináris `-buildconf` kimenete ugyanezeket a
kapcsolókat tartalmazza. A próbacsomag licencmappájában ellenőriztem a
`recipe/meta.yaml`, `recipe/build.sh`, `COPYING.LGPLv2.1` és `COPYING.LGPLv3`
bejegyzéseket.

A forrásarchívum maga nincs a ZIP-ben: a csomag jelenleg a forrás URL-jét,
hash-ét, a buildreceptet és a licencszövegeket tartalmazza. Ez a forrásazonosítás
és konfigurációs bizonyíték nem igazolja önmagában a corresponding source
kiadással együtt történő átadását, a relinkelési feltételeket vagy a teljes
terjesztési megfelelést. Ezek a #47/#25 kiadási átvételi feltételei nyitva
maradnak.

A korábbi PyPI `av` 18.1.0 kiadás yanked státuszt kapott memóriakorrupciós hiba
miatt. A hiba javítását a [PyAV 18.1.1 kiadási jegyzete](https://github.com/PyAV-Org/PyAV/releases/tag/v18.1.1)
rögzíti. Az aktuális csomag a conda-forge PyAV 17.1.0 LGPL FFmpeg buildjére
állt át; nem használja a korábbi PyAV wheelt.

## 🐍 Python disztribúciók és ismert sérülékenységek

A csomag **51 Python-disztribúció** licenc- és közleményfájlját, valamint a
név/verzió/licencmetaadatot tartalmazó manifestet állítja elő. A 2026-11-27-i
`uv audit` a hash lockból feloldott 51 Python csomagnál nem talált ismert
sérülékenységet vagy kedvezőtlen projektstátuszt. Ez az eredmény a Python
csomagnevekre és verziókra terjed ki; a 98 natív conda artifact külön OSV-auditja
nem történt meg.

A fő közvetlen komponensek licenceit és nyitott terjesztési kérdéseit a
[THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md) sorolja fel. Különösen:

- A PySide6 és a shiboken6 csomagmetaadata LGPL/GPL alternatívákat jelez; a
  választott Qt licencút, relink/source átadás és a végső binary csomag feltételei
  még kiadási átvételt igényelnek.
- PortAudio, ONNX Runtime és egyéb natív összetevők közleményeit a tényleges
  PyInstaller ZIP-ben kell ellenőrizni, nem csak a Python projektmetaadatból
  következtetni.
- A két rögzített Whisper modell külön, manifestben rögzített modellrevision és
  SHA-256 mellett kerül importálásra; a csomag nem terjeszti a modell súlyait.

## ✅ Ellenőrzések és korlátok

- ✅ A `requirements.lock` SHA-256-tal rögzíti a Python wheel artefaktumokat.
- ✅ A `conda-av-win64.lock` 98 explicit artifact URL-t és SHA-256-ot rögzít.
- ✅ A stage manifest az FFmpeg 8.1.2 buildjét LGPL-2.1-or-laterként jelöli, és
  rögzíti a DLL-zárat; x264/x265 DLL nincs benne.
- ✅ A csomagolt FFmpeg 8.1.2 buildrecept, upstream forrás URL/SHA-256,
  `--disable-gpl` buildág és tényleges bináris `-buildconf` egyezése ellenőrizve;
  a forrásarchívum átadása és a licencút teljes átvétele nyitott.
- ✅ A `uv audit` 51 Python csomagra ismert sérülékenységet vagy kedvezőtlen
  projektstátuszt nem jelzett; a natív conda closure nem tartozott a vizsgálatba.
- ⏳ A ZIP-ben található Qt, ONNX Runtime, PortAudio és minden tranzitív notice
  tényleges átvétele a #24 csomagolási jegyben marad nyitva.
- ⏳ A #28 tiszta Windows gépen telepítési és indítási próbája külön jóváhagyott
  későbbi feladat; a tulajdonos ezt elhalasztotta.
- ⏳ A magyar hangbenchmark (#21/#10) jóváhagyott, annotált hangforrásra vár;
  teljesítmény- vagy pontosságállítás nem készült.

A #25 és az M1 kapu (#10) maradjon nyitva, amíg a terjesztési/licencátvétel és a
M1 többi elfogadási feltétele nem teljesül.

