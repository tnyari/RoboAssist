# Windows CI

**Jegy:** [#17](https://github.com/tnyari/RoboAssist/issues/17) ·
**Szülő:** [#3](https://github.com/tnyari/RoboAssist/issues/3) ·
**Workflow:** [windows-ci.yml](../.github/workflows/windows-ci.yml)

## 🟦 Futtatás és környezet

A workflow minden pull requestnél, a `main` ágra küldött változásnál és kézi
`workflow_dispatch` indításkor fut. Nincs útvonal- vagy draft-szűrő.
A kézi indítás a workflow alapértelmezett ágra kerülése után érhető el.

A job neve **Python 3.11 x64 checks**, a runner `windows-2025`.
A [GitHub-hosted Windows runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
Windows Server környezet: nem a Windows 10/11 kliensgépes próba helyettesítője.
A runner image verziója és a lock SHA-256 értéke a futás naplójába kerül.
Az image tartalma frissülhet; a Python és a csomagok verzióját a projekt rögzíti.

A CI a [fejlesztői setupot](development.md) hívja Windows PowerShell 5.1 alatt:
`scripts/setup-dev.ps1`. Ez ellenőrzött uv 0.13.10 bootstrapot, saját CPython
3.11.18 x64 interpretert, teljes `requirements.lock` hash-ellenőrzést, kizárólag
wheel telepítést és offline editable projekttelepítést használ.
A runner előtelepített Pythonjától független; a setup nem frissíti a lockot.

## 🧪 Kötelező ellenőrzések

| Lépés | Futtatott parancs / tartalom |
|---|---|
| Setup | Telepítés + `uv pip check` + konfigurációvalidálás |
| Lint | `python -m ruff check src tests scripts/check-environment.py` |
| Formátum | `python -m ruff format --check src tests scripts/check-environment.py` |
| Típusok | `python -m mypy`, a pyproject strict beállításával |
| Tesztek | `python -m pytest --basetemp=.tools/ci-pytest -p no:cacheprovider` |
| Telepített CLI | `roboassist-config.exe --config configs/default.toml` |
| Natív smoke | `python scripts/check-environment.py` |

Minden Python-parancs a projekt `.venv/Scripts/` környezetéből fut.
A meglévő készlet 30 konfigurációteszt és 2 subprocess CLI-teszt; a pytest a
`pyproject.toml` összes aktuális tesztjét gyűjti, nincs fix darabszámra szűrés.
Nincs `continue-on-error`, feltételes tesztkihagyás vagy üres tesztet zöldnek
jelölő ág. Az első hibás kötelező lépés sikertelen jobot ad; az utána következő
lépések GitHub alapértelmezett viselkedése szerint nem futnak.

A natív smoke DLL/import kompatibilitást, CPU INT8 támogatásjelzést, ONNX CPU
providert és offscreen Qt renderelést ellenőriz. A HF offline/telemetriatilalmi
beállítások és a smoke Python socket-tiltása nem OS-szintű hálózati bizonyítás.
Modell, mikrofon vagy replay bemenet nem kell hozzá.

## 🔒 Jogosultságok és erőforrások

- Workflow token: kizárólag `contents: read`; nincs írási jogosultság vagy secret.
- Checkout: az [actions/checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1)
  teljes commit SHA-ra rögzítve (`3d3c42e5aac5ba805825da76410c181273ba90b1`),
  `persist-credentials: false` beállítással.
- `pull_request` trigger; nincs emelt jogosultságú `pull_request_target` futás.
- PR-enként/áganként az új futás megszakítja a korábbi, még futó jobot.
- Job-időkorlát: 20 perc. Nincs külső cache-visszatöltés vagy feltöltött artifact.
- A fejlesztői telepítés hálózatot használ; az alkalmazás futásidejű offline
  szabályait ez nem módosítja.

A jogosultság- és shell-szabályok forrása a
[GitHub workflow szintaxis](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).

## 🟨 Hatókör és halasztott munka

- A felhasználó 2026-11-26-i döntése alapján a további fejlesztés a már ellenőrzött
  Windows 10 gépen történik; a tiszta Windows 10/11 és hiányzó VC++ runtime próba
  [#28](https://github.com/tnyari/RoboAssist/issues/28) alatt **halasztott, Open**.
  #16 és #3 nyitott elfogadása megmarad; #17 ezen döntés alapján folytatható.
- A PR #29 tartalmazza a #16 alapját. A CI PR erre az ágra épül; a főágba kerüléshez
  előbb az alap PR rendezése, majd a CI PR főágra irányítása szükséges.
- A kis replay integráció és annak CI-bekötése [#20](https://github.com/tnyari/RoboAssist/issues/20)
  pipeline-függő munka; itt nincs helyette üres vagy szintetikus sikerjelzés.
- Modellsúly, modellinference, teljes benchmark, hardveres mikrofonteszt és
  hosszú stabilitási mérés nincs a normál CI-ben. Ezek külön M1 ellenőrzések.

A tényleges Actions-futás és helyi ellenőrzés bizonyítéka az
[ellenőrzési riportban](reports/issue-17-ci.md), a #17 jegyen és a
[PR #30-ban](https://github.com/tnyari/RoboAssist/pull/30) szerepel.
Egy workflow-fájl létezése önmagában nem CI-siker.
