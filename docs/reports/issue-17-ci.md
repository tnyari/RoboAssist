# #17 – Windows CI ellenőrzési riport

**Dátum:** 2026-11-26 (Europe/Budapest) ·
**Jegy:** [#17](https://github.com/tnyari/RoboAssist/issues/17) ·
**Szülő:** [#3](https://github.com/tnyari/RoboAssist/issues/3) ·
**PR:** [#30](https://github.com/tnyari/RoboAssist/pull/30)

## 🟩 Tényleges GitHub Actions-eredmény

| Tétel | Ellenőrzött eredmény |
|---|---|
| Workflow | Windows CI / Python 3.11 x64 checks |
| Futás | [#1 – 45860846280](https://github.com/tnyari/RoboAssist/actions/runs/45860846280) |
| Job | [140051162213](https://github.com/tnyari/RoboAssist/actions/runs/45860846280/job/140051162213) |
| Trigger / állapot | `pull_request` / **completed, success** |
| Ellenőrzött PR-head | [`c0ad22e73d1c98d72881a4a7ae13f2e9e9425278`](https://github.com/tnyari/RoboAssist/commit/c0ad22e73d1c98d72881a4a7ae13f2e9e9425278) |
| PR-alap | `issue-16/python311-lock-config`, PR #29, `1906d25` |
| Runner címke | `windows-2025` |
| Tényleges OS | Microsoft Windows Server 2025 Datacenter x64, `10.0.26100` |
| Image | `win25-vs2026 / 20261116.315.1` |
| Shell | Windows PowerShell `5.1.26100.33822` |
| Python | A setup által telepített CPython **3.11.18 x64**, nem a runner előtelepített Pythonja |
| Függőségek | `uv pip check`: **45 kompatibilis disztribúció** |
| Forrás lock SHA-256 (az első CI-naplóból hiányzott, #31) | `7472cc372365bcb9478600d0d48ce6692a7e32c44af39e961dc8f7540afb16fd` |

A GitHub Actions a pull request merge-refjét ellenőrzi; a fenti SHA a futás
API-ból visszaolvasott PR-headje. A workflow/ref, joblépések, végállapot és napló
a GitHub bővítményen keresztül kerültek ellenőrzésre.

| Kötelező lépés | Tényleges kimenet |
|---|---|
| Runner és lock azonosítás | OS, image és shell a naplóban; a hash kijelzési hibáját #31 követi |
| Hash-lockos setup | Telepítés sikeres, 45 csomag kompatibilis; konfiguráció rendben |
| Ruff lint | `All checks passed!` |
| Ruff formátum | `7 files already formatted` |
| Strict mypy | `Success: no issues found in 3 source files` |
| Pytest | **32 passed in 0.17s**: 30 konfigurációteszt + 2 subprocess CLI-teszt |
| Telepített entrypoint | hu / CPU INT8 / offline; save_audio=False, save_transcript=False |
| Natív offline smoke | `status: passed`: DLL/import, CPU INT8 támogatásjelzés, ONNX CPU provider, offscreen Qt |

A job összes kötelező lépése sikeres; nincs elnyelt hiba vagy kihagyott
ellenőrzés. A tesztfutás ideje nem beszédfelismerési teljesítménymérés.

## 🟠 Naplózási javítás – #31

Az első futásban a PowerShell az OS-objektum után a FileHashInfo objektumot is
Caption/Version/OSArchitecture oszlopokkal próbálta formázni, így a hash helyén
üres sor jelent meg. Emiatt az első sikeres futás nem bizonyítja a hash naplóba
írását; a fenti hash a tényleges forrásfájlból származik. A hiba külön aljegy:
[#31](https://github.com/tnyari/RoboAssist/issues/31), szülője #17.

A külön javító commit a számított `.Hash` értéket explicit, címkézett szövegként
írja ki. A módosított lépés helyi Windows PowerShell 5.1 kimenetében a teljes
64 karakteres `7472cc…fb16fd` érték megjelenik. Az új Actions-futás konkrét hash-sora
és a javítás elfogadása #31-ben és a PR #30-ban kerül rögzítésre; a kezdeti
kijelzési hiány nem szerepel sikeres ellenőrzésként.

## 🟠 Windows checkout sorvége – #32

A #31 utáni [CI #3](https://github.com/tnyari/RoboAssist/actions/runs/45861542089)
sikeres volt, és már ténylegesen kiírta a hash-t:
`406de88c20be894b7a1e0f7dbcf973fe88e81b67fbde8731f1208753e0ccf6ee`.
Ez a Git LF forrását CRLF-re alakító Windows checkout hash-e. A helyi
LF→CRLF ellenőrző számítás byte-ra ezt az értéket adta, míg az LF változaté a
fenti `7472cc…fb16fd`. A korábbi Windows checkout ezért nem szerepel
byte-azonos forrásfájlként.

Külön bug aljegy: [#32](https://github.com/tnyari/RoboAssist/issues/32), szülő #17.
A javítás kizárólag a `requirements.lock text eol=lf` sort adja a
`.gitattributes` fájlhoz; a lock tartalma, a verziók és a csomaghash-ek változatlanok.
A javított checkout teljes CI-jének és pontos hash-sorának bizonyítéka #32-ben,
#17-ben és a PR #30 végső állapotában követett.

## 🧪 Helyi ellenőrzés

A workflow YAML-ja parse-olható, mind a nyolc `run` blokk Windows PowerShell 5.1
parserrel érvényes. A blokkok pontos parancsai, a GitHub PowerShell
hibaterjesztésével megegyező wrapperrel, a kijelölt Windows 10 célgépen
is sikeresek: **32 passed in 0.95s**, Ruff/formátum/strict mypy és natív smoke zöld.

A helyi tesztharness az első próbán a PowerShell 7-ből örökölt modulútvonal miatt
nem találta a PS5.1 Get-FileHash cmdletjét. A harness saját PS5.1 modulútvonallal
újraindítva sikeres; a workflow és a projekt setupkódja ehhez nem változott.
Ez a helyi harness eltérése, nem elhallgatott CI-siker vagy projekt-hibajavítás.

A helyi kimenetek a Gitből kizárt `.tools/issue-17/` könyvtárban vannak:
`commands.json`, `local-results.json`, `step-0.log`–`step-7.log`.
A végrehajtott parancsok és a hatókör a [CI-leírásban](../ci.md) szerepelnek.
A GitHubra írt workflow tartalma visszaolvasva azonos volt a helyben ellenőrzöttel.

## 🟨 Nem futtatott ellenőrzések és integráció

- **Tiszta Windows 10/11, hiányzó VC++ runtime telepítése:** a felhasználó
  kérésére halasztott [#28](https://github.com/tnyari/RoboAssist/issues/28);
  nyitott marad. A Windows Server CI ezt nem helyettesíti.
- **Replay/pipeline integráció:** [#20](https://github.com/tnyari/RoboAssist/issues/20),
  az implementáció elkészültekor kell bekötni. Itt nincs helyette üres teszt.
- **Modellinference, mikrofon, RTF/latency/WER és stabilitás:** külön M1 munka;
  modell vagy hang nem került a CI-be.
- **Main/push és kézi trigger tényleges futása:** a workflow még a PR-ben van,
  az alapértelmezett ágon még nincs telepítve. A bizonyíték valódi PR-futás;
  main push/dispatch siker nincs állítva.
- **Integráció:** a PR #30 a #29 ágára épül. A főági bevezetéshez előbb a #29,
  majd a mainre irányított #30 rendezése szükséges. Automatikus merge nincs.
  #17 az integrációig Open; #16/#3 és a halasztott #28 szintén Open.
- Ez a riport az első sikeres implementációs futást rögzíti. A dokumentációs
  kiegészítés utáni PR-head végső CI-állapota a PR #30-ban és #17-ben követett.

## 🔗 Ellenőrzött források

- [Workflow](../../.github/workflows/windows-ci.yml)
- [GitHub workflow szintaxis és jogosultságok](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [GitHub-hosted Windows runnerek](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [actions/checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1),
  [rögzített commit](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1)
