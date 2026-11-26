# GitHub Issues munkarend

## 🧭 Használt funkciók

| Terület | Megoldás |
|---|---|
| Feladat | GitHub issue |
| Típus/címke | Gyári bug, enhancement, documentation; szükség esetén más meglévő gyári címke |
| Állapot | Natív Open / Closed; lezárási ok completed vagy indokolt not_planned/duplicate |
| Prioritás | 🔴 P0 előfeltétel/blokkoló · 🟠 P1 kötelező szállítás · 🟡 P2 összehasonlítás/optimalizálás |
| Aljegy | Önálló issue, szülőre mutató hivatkozás és szülő oldali checklist |
| Függőség | „Előfeltétel: #N”; ez dokumentált, kézzel követett kapcsolat |
| Haladás | Időrendi issue-kommentek |
| Repo módosítás | GitHub bővítmény fájl/commit/branch/PR műveletei |

GitHub Projectet nem használunk. A bővítmény jelenlegi eszközei nem teszik elérhetővé natív sub-issue kapcsolat, prioritásmező, milestone létrehozás vagy issue-pinning kezelését. Nem készítünk ezeket utánzó egyedi címkéket. M1/M2 tervezési szakaszok a leírásban szerepelnek, nem létrehozott GitHub milestone objektumok.

Az issue- és PR-sablon munkaszabályt és szükséges adatokat ad; a jegynyitást és kommentelést nem kényszeríti ki automatikusan egy bot.

## 📝 Új kérés és aljegy

- Minden új változtatási vagy hibajavítási kérés új jegyet kap a munka előtt.
- Az aktuális, már jeggyel rendelkező kérés folytatása ugyanazon a jegyen történik.
- Menet közben felmerülő vagy megmaradó önálló feladat új aljegy.
- Szülő leírásában: `- [ ] #N – rövid feladatnév`.
- Aljegy leírásában: `Szülőjegy: #P`; a szülő aljegylistája és az aljegy hivatkozása együtt szükséges.
- A checklistet lezáráskor kézzel frissítsd; Markdown hivatkozás nem hoz létre natív hierarchiát.
- A szülő marad Open, amíg az elfogadási feltételei és vállalt aljegyei nem teljesülnek.
- Egy aljegy becslése a szülőét bontja, nem újra hozzáadandó összeg.

## 🎨 Leírás és mérföldkő-komment

A gyári címkék saját színüket kapják. A szövegben színes emoji, táblázat és rövid listák segítik a gyors olvasást; tetszőleges HTML/CSS színezésre nem támaszkodunk.

```markdown
## 🟦 Mérföldkő – <rövid név>

**Eredmény:** <mi készült el vagy milyen döntés született>
**Ellenőrzés:** <teszt/riport/commit/PR linkje és eredménye>
**Következő lépés:** <konkrét feladat vagy aljegy linkje>
```

Jelölések: 🟦 megkezdett munka/mérföldkő, 🟨 akadály, 🟩 ellenőrzött eredmény, 🟥 hibás ellenőrzés. Ezek kommentjelölések, nem új státuszok.

Komment szükséges a munkakezdésnél, lényeges implementációs vagy döntési pontnál, elakadásnál, ellenőrzésnél és lezárásnál. Ugyanazt az eredményt ne ismételd több üres státuszfrissítésben.

## ✅ Lezárás

A lezáró komment rögzítse az eredményt és az elfogadási feltételek bizonyítékait. A nem futtatott ellenőrzéseket és okukat külön nevezze meg. A valóban megmaradó munkát külön aljegybe kell tenni; ha az a szülő vállalt feltétele, a szülő sem zárható le.

Natív Closed/completed csak kész munkára használható. A nem tervezett vagy duplikált kérés lezárása kapjon rövid indoklást és megfelelő natív lezárási okot.
