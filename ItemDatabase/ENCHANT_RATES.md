# AION 2 — Verzauberungs-Raten (Enchant/Enhance)

Ermittelt am 2026-08-21 durch Auswertung von **117 echten Datenpunkten** (101 Waffen/Accessoires + 16 Rüstungsteile), gesammelt über die shugo.gg-API von tatsächlich ausgerüsteten Items realer Charaktere. Kalibrierung siehe `app.py` (`estimate_enchant_bonus`, `estimate_armor_bonus`, `estimate_exceed_bonus`, `estimate_armor_exceed_bonus`).

**Grundprinzip (für alle Ausrüstung gleich):**
- Nur bestimmte Main-Stats bekommen beim Verzaubern einen Bonus — alle anderen Main Stats bleiben unverändert.
- Der Bonus wird **addiert**, nicht in den Basiswert eingerechnet — Anzeige im Spiel z. B. `396 ~ 545 (+350)`.
- Der Bonus **friert ein**, sobald die reguläre Maximalstufe erreicht ist (Exceed-Bereich beginnt danach).
- Substats (die Zufalls-Rollen mit Bereich, z. B. `81 ~ 100`) ändern sich **nie** durch Verzauberung — nur durch Soulbinding.

---

## Waffen & Guard (Off-Hand)

| Rarität | Skaliert | Bonus bei Cap | Rate/Stufe | Cap-Stufe | Quelle |
|---|---|---|---|---|---|
| Legend | Attack | +150 @ 15 | **+10/Stufe** (exakt linear) | 15 | bestätigt (2 Punkte: +10@1, +50@5) |
| Unique | Attack | +225 @ 15 | Kurve, ~+15–22/Stufe steigend (nicht linear) | 15 | bestätigt (4 Punkte: 65@6, 125@10, 165@12, 225@15) |
| Heroic (Epic) | Attack | +350 @ 20 | **+17.5/Stufe** (exakt linear, kann Dezimalwerte ergeben) | 20 | bestätigt per Screenshot + mehrfach über API |
| Common/Rare | Attack | unbekannt | keine Daten gefunden (kein Spieler trägt sowas mehr) | vermutlich 15 | **ungetestet**, Platzhalter = Legend-Rate |

**Exceed-Bereich** (jenseits der Cap-Stufe, für alle Raritäten identisch):
- Attack (flach): **+30 / Exceed-Stufe**
- Attack increase (%): **+1% / Exceed-Stufe**

---

## Accessoires (Ring, Necklace, Earrings, Bracelet, Brooch, Amulet)

| Rarität | Skaliert | Bonus bei Cap | Rate/Stufe | Cap-Stufe |
|---|---|---|---|---|
| Legend | Attack | +75 @ 15 | **+5/Stufe** | 15 |
| Unique | Attack | +75 @ 15 | **+5/Stufe** | 15 |
| Heroic (Epic) | Attack | +100 @ 20 | **+5/Stufe** | 20 |

→ Rate ist **grade-unabhängig**, immer +5/Stufe — nur die Cap-Stufe (und damit der Endwert) unterscheidet sich je nach Rarität.

**Exceed-Bereich** (alle Raritäten identisch, 3 Stat-Zeilen statt 2):
- Attack (flach): **+20 / Exceed-Stufe**
- Defense (flach, NEU — Accessoires haben sonst kein Defense): **+40 / Exceed-Stufe**
- Attack increase (%): **+1% / Exceed-Stufe**

---

## Rüstung (Helm, Torso, Shoulder, Gloves, Pants, Boots, Cape)

Skaliert **zwei** Stats gleichzeitig (Waffen/Accessoires nur einen):

| Rarität | Defense-Bonus @ Cap | Defense-Rate | HP-Bonus @ Cap | HP-Rate | Cap-Stufe |
|---|---|---|---|---|---|
| Unique | +450 @ 15 | **+30/Stufe** | +300 @ 15 | **+20/Stufe** | 15 |
| Heroic (Epic) | +700 @ 20 | **+35/Stufe** | +400 @ 20 | **+20/Stufe** | 20 |

→ HP-Rate ist grade-unabhängig (+20/Stufe bei beiden), Defense-Rate ist es nicht.

**Exceed-Bereich** (beide Raritäten identisch, 4 neue Zeilen):
- Defense (flach): **+80 / Exceed-Stufe**
- HP (flach): **+80 / Exceed-Stufe**
- Defense increase (%): **+1% / Exceed-Stufe**
- HP increase (%): **+1% / Exceed-Stufe**

---

## Belt (Sonderfall — eigene Regeln)

Belt hat eine **eigene, niedrigere Maximalstufe (10)**, unabhängig von der Rarität — und beide getesteten Raritäten lieferten identische Werte:

| Rarität | Defense-Bonus @ Cap | Defense-Rate | HP-Bonus @ Cap | HP-Rate | Cap-Stufe |
|---|---|---|---|---|---|
| Unique | +300 @ 10 | +30/Stufe | +500 @ 10 | +50/Stufe | 10 |
| Heroic (Epic) | +300 @ 10 | +30/Stufe | +500 @ 10 | +50/Stufe | 10 |

→ Beide Raritäten identisch, da Cap-Stufe (10) für Belt fix ist. Exceed-Rate für Belt wurde **nicht getestet** (kein Sample über Stufe 10 gefunden).

---

## Offene Punkte

- **Common/Rare-Grade**: komplett ungetestet (keine Spieler tragen sowas auf hohem Level mehr) — App nutzt aktuell die Legend-Formel als Platzhalter.
- **Belt-Exceed-Bereich**: keine echten Daten, App nimmt an, dass die allgemeine Rüstungs-Exceed-Rate (+80/Stufe je Defense+HP, +1%/Stufe je) auch hier gilt.
- **Unique-Waffen-Kurve**: nicht exakt linear, Formel ist ein Kurven-Fit (`k=5.733, p=1.355`), trifft die Randpunkte gut, Zwischenwerte können leicht abweichen (~5 Einheiten).
