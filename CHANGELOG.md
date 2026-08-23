# 🧪 Beta-Bereich

Diese Funktionen sind noch **nicht** Teil eines offiziellen Updates und befinden sich in aktiver Entwicklung. Freischaltbar auf eigene Gefahr über Einstellungen → „Beta Bereich freischalten".

## Armory

### Item-Datenbank
- Durchsuchbare Item-Datenbank mit Filtern nach Klasse, Kategorie, Rarity und Level.
- EQ-Prioritätsliste je Ausrüstungs-Slot (Helm, Waffe, Rüstung, …) mit empfohlener Reihenfolge und Rarity-Icons.

### Crafting Calculator
- Zeigt zu jedem herstellbaren Item die komplette Materialkette: benötigte Zutaten lassen sich einzeln aufklappen, sofern sie selbst wieder ein Rezept haben.
- Filter nach Beruf (Schmiedekunst, Rüstungsschmiede, Handwerk, Alchemie, Kochen), Kategorie und Rarity.
- Material-Icons zeigen den passenden Rarity-Hintergrund (Common/Rare/Unique/Epic/Legend).

---

# Version 1.3.0

Release Date: 2026-08-21

## ✨ New Features

### Custom Timer — Sound und Vorwarnung direkt beim Bearbeiten
- Beim Anlegen oder Bearbeiten eines Custom-Timers kann jetzt direkt ein Benachrichtigungston ausgewählt und per Klick getestet werden.
- Zusätzlich einstellbar, wie viele Minuten vorher die Benachrichtigung kommen soll (0/1/3/5/10 Min) — vorher wurde ausschließlich exakt bei Ablauf benachrichtigt.

### Schnellzugriff auf der Timer-Seite
- Neuer „+"-Button öffnet direkt ein Popup zum Verwalten von Custom-Timern (Kategorien anlegen, Timer hinzufügen/bearbeiten) — ohne Umweg über die Einstellungen.
- Neues Zahnrad-Symbol springt direkt zu den Timer-Einstellungen.

## 🎨 UI-Änderungen

### Profil-Verwaltung aufgeräumt
- Statt einer eigenen Profil-Seite gibt es jetzt oben links unter dem Avatar einen kleinen „Profile"-Button für den schnellen Profilwechsel.
- Speichern, Laden, Zurücksetzen, Events leeren, Duplizieren sowie Export/Import eines Profils sind jetzt gebündelt unter Einstellungen → Profile zu finden.

### Tasks und Timers zusammengeführt
- Statt zwei getrennten Seitenleisten-Einträgen gibt es jetzt einen gemeinsamen Bereich „ToDo" mit zwei größer hervorgehobenen Reitern oben („ToDo" / „Timer"), darunter wie gewohnt Tasks/Shopping.

### „Plan" heißt jetzt „Flow Map"
- Der Seitenleisten-Eintrag wurde in allen Sprachen von „Plan" zu „Flow Map" umbenannt.

### Einstellungen — Timer-Bereich neu sortiert
- Der bisherige „Custom"-Reiter unter Timer-Einstellungen ist entfallen (Verwaltung jetzt über das neue Popup auf der Timer-Seite, siehe oben).
- Benachrichtigungs-Einstellungen für Shugo/Riss sind jetzt als zweiter Reiter direkt unter Timer zu finden, statt als eigener Menüpunkt.

---

# Version 1.2.0

Release Date: 2026-08-20

## ✨ New Features

### Vorlagen-Suche in der Werkzeugleiste
- Das Vorlagen-Dropdown beim Hinzufügen von Aufgaben und Einkäufen ist jetzt durchsuchbar: Einfach tippen, um die Liste live zu filtern, statt nur durch eine lange Liste zu scrollen.

### Vorlagen-Dialog — Suche und Sortierung nach Ort
- Der Vorlagen-Dialog (Einkauf und Aufgaben) hat jetzt ein Suchfeld, das die Liste live nach Titel und Ort filtert.
- Zusätzlich kann jetzt auch nach Ort sortiert werden (neben Name, Priorität, Schedule).

### About-Seite — Nützliche Links
- Neue Sektion mit hilfreichen Tools für Aion2 — aktuell Guildnest (Gilden-Management-Tool mit Discord-Integration).

### Flow Map — neues Icon „Money"
- Ein weiteres Symbol steht bei der Node-Erstellung zur Auswahl.

## 🐛 Bug Fixes

- **Falsche Symbole in der Flow Map** — Die Icons „Dungeon" und „Broker Market" wurden nach der Auswahl nicht korrekt angezeigt, stattdessen erschien immer das Standard-Symbol. Behoben.
- **Preisänderungen an Vorlagen wirkten sich nicht auf bereits hinzugefügte Einträge aus** — Wurde z. B. der Preis einer Einkaufs-Vorlage nachträglich geändert, blieben bereits hinzugefügte Listeneinträge auf dem alten Stand. Änderungen an Titel, Ort, Preis, Priorität und Zeitplan einer Vorlage werden jetzt automatisch an alle davon erzeugten Einträge weitergegeben.
- **Charakter-Zuweisung bei Aufgaben ging optisch verloren** — Wurde einer bestehenden Aufgabe nachträglich ein Charakter zugewiesen, erschien das Charakter-Badge nicht auf der Karte. Behoben.
- **Ort fehlte bei Aufgaben** — Aufgaben, die aus einer Vorlage mit hinterlegtem Ort erstellt wurden, zeigten diesen Ort nirgends an. Er wird jetzt auf der Aufgaben-Karte angezeigt.
- **„+"-Symbol beim Verzweigen falsch positioniert** — Beim Heraus- oder Hereinzoomen der Flow Map saß das „+"-Symbol zum Hinzufügen eines neuen Knotens nicht mehr korrekt auf der Verbindungslinie. Behoben.
- **Heller Hintergrund in den Einstellungen bei Windows-Dunkelmodus** — Die Einstellungs-Seite zeigte unter Windows im Dunkelmodus einen hellen statt dunklen Hintergrund. Behoben.
- **Abyss Command Shop — falsche Währung** — Die vier Abyss-Command-Vorlagen waren fälschlicherweise mit Abyss Points hinterlegt, obwohl sie mit Kinah gekauft werden. Korrigiert.

## 🎨 UI-Änderungen

- **About-Seite — klare Überschriften-Hierarchie**: Seitentitel, Abschnitts-Titel (z. B. „Unterstützen", „Nützliche Links") und Einzeleinträge sind jetzt optisch klar voneinander unterschieden (Größe/Gewichtung).

---

# Version 1.1.0

Release Date: 2026-08-15

## ✨ New Features

### Neue Währungen: Nightmare Points & Shugo Coins
- Neben Kinah und Abyss Points gibt es jetzt zwei weitere Währungstypen: **NP** (Nightmare Points) und **SC** (Shugo Coins).
- Einkaufskarten zeigen den Preis korrekt als NP oder SC an.
- Im Vorlagen-Dialog können Einträge mit der passenden Währung angelegt und bearbeitet werden.
- Die Einkaufs-Gesamtsumme in der Fortschrittsleiste wird jetzt pro Währung getrennt angezeigt — z. B. „100k Kinah + 52500 AP + 50 NP".

### Sprach-spezifische Standard-Profile
- Es gibt jetzt drei Starter-Profile: **Default [EN]**, **Default [DE]** und **Default [RU]** — je mit übersetzten Vorlage-Einträgen.
- Beim ersten Start wählt die App automatisch das zur eingestellten Sprache passende Profil.
- Beim Sprachwechsel innerhalb eines Standard-Profils wechselt die App automatisch zum passenden Sprach-Default.
- Im Profil-Menü erscheinen Benutzerprofile oben, darunter (getrennt durch eine Linie) die Standard-Profile.

### Shop-Vorlagen — Abyss Command Shop
- Neue Vorlagen für den Abyss Command Shop: Abyss Command (15.000 AP), Abyss Command: Proficiency (37.500 AP), Elite (75.000 AP), Special Mission (150.000 AP) — alle wöchentlich.

## 🐛 Bug Fixes

- **Übersetzung im Aufgaben-Tab unvollständig** — Mehrere Texte im Aufgaben-Tab und im Vorlagen-Dialog wurden bei einer anderen Sprache als Deutsch nicht übersetzt. Alle betroffenen Felder sind jetzt vollständig in das Übersetzungssystem eingebunden.
- **Profile wurden beim App-Start verändert** — Beim Laden eines Profils wurde dieses automatisch neu gespeichert, was den Zeitstempel aktualisierte und Daten überschreiben konnte. Der automatische Speicheraufruf beim Profilladen wurde entfernt.

---

# Version 1.0.0

Release Date: 2026-08-14

## ✨ New Features

### Profil-Avatar
- Klick auf den Profilkreis im Header öffnet einen Datei-Dialog (PNG, JPG, WEBP). Das gewählte Bild wird kreisförmig zugeschnitten und als Avatar angezeigt. Der Avatar wird in der lokalen Konfiguration gespeichert und bleibt über Neustarts erhalten.

---

# Version 0.10.0

Release Date: 2026-08-14

## ✨ New Features

### Vorlagen-Dialog — Sortierung mit Richtungsanzeige
- Im Vorlagen-Dialog (Einkauf und Aufgaben) kann jetzt nach Name, Priorität und Schedule sortiert werden. Ein erneuter Klick auf denselben Button dreht die Sortierrichtung um. Der aktive Button hebt sich farblich hervor und zeigt einen Pfeil (↑ / ↓).

### Vorlagen-Dialog — Schedule- und Prioritäts-Badges
- Jede Vorlage in der Liste zeigt jetzt ein farbiges Badge für Schedule (täglich / wöchentlich / Season) und Priorität (LOW / MID / HIGH) — auch bei Einkauf-Vorlagen, die nicht als Allgemein markiert sind.

### Preisfeld — Hinweis auf K-Einheit
- Der Platzhaltertext im Preisfeld lautet jetzt „Preis (in K)", damit klar ist, dass der Preis in Tausend-Schritten (Kinah) angegeben wird.

## 🐛 Bug Fixes

- **Aufgaben aus Charakter-Nodes fehlten in der Aufgabenliste** — Aufgaben (type: task), die einem Charakter-Node zugewiesen wurden, landeten fälschlicherweise in der Einkaufsliste. Sie werden jetzt korrekt als Aufgabenkarten in der Aufgabenliste angezeigt.
- **Charakter-Dropdown zeigte keine Einträge** — Nach dem Laden eines Profils oder nach dem Profilwechsel blieb das Charakter-Dropdown leer. Es wird jetzt nach jedem Sync und nach dem Profilladen korrekt befüllt.
- **Flackern beim Speichern eines Nodes** — Beim Speichern einer Node-Karte wurden alle Karten neu aufgebaut, was zu einem sichtbaren Flackern führte. Es wird jetzt nur noch die betroffene Karte aktualisiert.
- **Flackern beim Öffnen der Flow Map** — Overlay-Positionen wurden verzögert gesetzt, was beim Öffnen des Fensters kurz aufflackerte. Die Positionierung erfolgt jetzt direkt beim Resize-Event.

---

# Version 0.9.9

Release Date: 2026-08-14

## ✨ New Features

### Aufgaben-Tab — Komplett überarbeitet
- "Tägl. Aufgaben" und "Wöch. Aufgaben" wurden zu einem einzigen "Aufgaben"-Tab zusammengeführt. Daily, Weekly und Season lassen sich per Filter umschalten — genau wie im Einkauf.
- Aufgaben sind jetzt vorlagenbasiert: Man wählt eine Vorlage aus dem Dropdown, setzt Schedule, Priorität und optional einen Charakter.
- Der Vorlagen-Dialog hat jetzt zwei Tabs: "Einkauf" und "Aufgaben". Aufgaben-Vorlagen haben keinen Preis — nur Titel, Kategorie und optionale Charakter-Zuweisung.
- Der Vorlagen-Dialog öffnet automatisch den Tab, der dem aktuell aktiven Aufgaben-Tab entspricht.

### Flow Map — Liste bearbeiten
- Der Charakter-Node hat jetzt eine "Liste bearbeiten"-Schaltfläche, die einen Dialog mit zwei Tabs öffnet: "Einkauf" und "Aufgaben". Vorlagen beider Typen können direkt dort zugewiesen werden.
- Items und Aufgaben aus dem Flow-Plan erscheinen automatisch in den entsprechenden Listen. Die Synchronisation erfolgt beim Speichern und beim Laden des Profils.

### Season
- In den Timer-Einstellungen lässt sich das Season-Ende als Datum + Uhrzeit eintragen.
- Der Season-Countdown erscheint in der Timer-Übersicht als eigene Karte und im Aufgaben-/Einkauf-Tab, sobald der Season-Filter aktiv ist.

### Shopping — Reset-Timer je nach Filter
- Der Reset-Countdown im Einkauf-Tab passt sich dem aktiven Filter an: Daily → Tages-Countdown, Weekly → Wochen-Countdown, Season → Countdown bis Season-Ende. Bei "Alle" wird kein Timer angezeigt.

### Vorlagen — Priorität & Schedule beim Anhaken
- Beim Anhaken einer Vorlage öffnet sich ein Popup, in dem Anzahl, Priorität und Schedule direkt angepasst werden können — vorausgefüllt mit den gespeicherten Vorlagenwerten.

### Preisfelder — k-Notation
- Preisfelder akzeptieren jetzt die Kurzschreibweise: `42k`, `1.5k` etc. — sowohl für Kinah als auch für AP.

## 🐛 Bug Fixes

- **Node-Klick unzuverlässig** — Klicks im unteren Bereich einer Node-Karte wurden nicht erkannt. Behoben.
- **Einkaufsliste zeigte keine Einträge** — Vorhandene Einträge wurden nach bestimmten Aktionen nicht mehr angezeigt, obwohl sie noch gespeichert waren. Behoben.
- **Flow Map: Negative Größen beim Start** — Beim Öffnen der Flow Map wurden Qt-Warnungen über negative Widget-Größen ausgelöst, weil das Resize-Event feuerte bevor das Fenster vollständig aufgebaut war. Behoben.

## 🎨 UI-Änderungen

- **Overlay**: Jede Zeile zeigt `[Task]` oder `[Shop]` als Typ, ein Schedule-Badge (D / W / S) und — bei Einkaufseinträgen mit Charakterzuweisung — den Charakternamen.
- **Liste bearbeiten — Dialog**: Einträge werden jetzt als einzelne Karten mit Rahmen dargestellt, passend zum restlichen Design. Die Listenbereich ist größer, der Dialog breiter und luftiger.
- **Liste bearbeiten — Schließen**: Der Button ist jetzt neutral gestaltet statt blau, um ihn klar vom Hinzufügen-Button zu unterscheiden.
- **Löschen-Button**: Zeigt jetzt × statt des Papierkorb-Symbols.
- **Charakter-Auswahl**: Das Dropdown zeigt "Char" als Platzhalter. Der erste Eintrag ist nicht wählbar. Nach dem Hinzufügen wird die Auswahl automatisch zurückgesetzt.
- **Root-Node**: Zeigt immer das Home-Symbol, unabhängig von der gespeicherten Einstellung.
- **Charakter-Node-Editor**: Das Charakter-Symbol kann im Startknoten nicht mehr ausgewählt werden.

---

# Version 0.9.8

Release Date: 2026-08-10

## 🐛 Bug Fixes

- **Auto-Update: Update wurde nicht übernommen** — Das v0.9.7-Release-ZIP enthielt durch einen Build-Fehler nur `Aion2.exe` statt `Aion2 TM.exe` + `_internal/`. Robocopy kopierte daher nur eine fremde Datei in den App-Ordner — `_internal/` und `Aion2 TM.exe` blieben unverändert. Korrekter Ablauf jetzt: ZIP herunterladen → `_internal/` Inhalte ersetzen → `Aion2 TM.exe` überschreiben → `Aion2 TM.exe` neu starten.
- **Auto-Update: Neustart auf `Aion2 TM.exe` hardcodiert** — Der Updater leitete den Neustart-EXE-Namen bisher dynamisch aus `sys.executable` ab, was zu falschen Starts führen konnte. Der EXE-Name ist jetzt fest auf `Aion2 TM.exe` gesetzt.

---

# Version 0.9.7

Release Date: 2026-08-10

## 🐛 Bug Fixes

- **Profilordner-Wechsel lädt falsches Profil** — Nach dem Wechsel des Profilordners wurde `last_profile.txt` ausgelesen, die auf einen absoluten Pfad im alten Ordner zeigen konnte. Dadurch wurden Timer, Tasks, Shopping und Plan nicht aktualisiert. Jetzt wird immer direkt das beste Profil aus dem neuen Ordner geladen (erstes Nicht-Default-Profil, Fallback auf Default).
- **PyInstaller: styles.qss nicht gefunden** — `load_styles` nutzt jetzt `sys._MEIPASS` im kompilierten Build, sodass die QSS-Datei im Bundle korrekt gefunden wird.
- **Update-Angebot ohne gültiges Asset** — Der Update-Checker bot Updates an, auch wenn kein kompiliertes Release-Asset (`.zip`/`.exe`) vorhanden war. In dem Fall wurde das GitHub Source-Archiv heruntergeladen, das eine PyInstaller-Exe nicht aktualisieren kann. Jetzt wird das Update nur angeboten, wenn ein gültiges Asset existiert.

## 🔧 Improvements

- **Build- und Release-Scripts** — `scripts/build_exe.bat` baut die Exe via PyInstaller. `scripts/create_release.bat` baut, erstellt das ZIP und lädt es automatisch als GitHub Release Asset hoch (`gh` CLI erforderlich).

---

# Version 0.9.6

Release Date: 2026-08-10

## 🐛 Bug Fixes

- **Custom Timer: Profil wurde zu früh gespeichert** — In `apply_settings_from_page` wurde `save_profile` aufgerufen, bevor `custom_timers` und `timer_categories` in den App-State übernommen wurden. Dadurch gingen beim nächsten App-Start aktivierte Timer und Kategorien verloren (Profil enthielt noch den alten Stand). Das `save_profile`-Call wurde ans Ende der Funktion verschoben, sodass immer der vollständige, aktuelle Stand gespeichert wird.

## 🔧 Improvements

- **Custom Timer Dialog: Feldreihenfolge im Custom-Tab** — Im "Custom"-Modus-Tab erscheint jetzt zuerst das **Start**-Feld (Startuhrzeit), danach das **Intervall**-Feld. Logischere Lesereihenfolge: erst wann, dann wie oft.

---

# Version 0.9.5

Release Date: 2026-08-10

## ✨ New Features

- **Timer-Kategorien** — Custom Timer können jetzt in Kategorien (Überschriften) gruppiert werden. Bis zu 4 Kategorien (1 Standard + 3 weitere) können in den Timer-Einstellungen verwaltet werden (hinzufügen, umbenennen, löschen). Beim Anlegen oder Bearbeiten eines Timers wählt man die gewünschte Kategorie. Auf der Timer-Übersichtsseite erscheinen die Timer-Karten unter der jeweiligen Kategorieüberschrift.
- **Max. 8 Custom Timer** — Die bisherige Beschränkung auf 2 Custom Timer entfällt. Es können jetzt bis zu 8 Timer verwaltet werden, frei auf Kategorien verteilt.
- **Custom Timer Start-Uhrzeit** — Beim Anlegen eines neuen Custom Timers wird die aktuelle Uhrzeit automatisch als Standard-Startzeitpunkt übernommen.

---

# Version 0.9.4

Release Date: 2026-08-06

## ✨ New Features

- **Custom Timer: 4 Modi** — Der Custom Timer Dialog wurde vollständig überarbeitet. Statt eines einzigen Anzeigeformats gibt es jetzt vier klar getrennte Modi:
  - **Daily** — Countdown bis zu einer konfigurierten Tageszeit (täglich wiederholend), wie der Daily-Reset-Timer.
  - **Weekly** — Countdown bis zu einem bestimmten Wochentag + Uhrzeit (wöchentlich wiederholend), wie der Weekly-Reset-Timer inkl. Tages-Buttons (Mo–So).
  - **Hourly** — Intervall-Timer (1–6 h Schnellauswahl oder manuelle HH:mm-Eingabe per Stift-Button).
  - **Custom** — Sekundengenaues Intervall via HH:mm:ss-Eingabe.
- Modus-Buttons ersetzen das bisherige Anzeigeformat-Dropdown. Die Übersichtszeile in den Timer-Einstellungen zeigt je nach Modus eine passende Zusammenfassung (z.B. "Täglich 09:00", "Wöchentlich Di 09:00", "Alle 2h", "01:30:00").

## 🐛 Bug Fixes

- **Weekly-Reset feuert jetzt beim App-Start** — Der wöchentliche Reset wurde bisher nur ausgelöst, wenn die App exakt am konfigurierten Wochentag lief. Startet man die App an einem anderen Tag (z.B. Donnerstag), nachdem der Reset-Zeitpunkt (Mittwoch 09:00) bereits verstrichen war, feuerte der Reset nie. Jetzt wird beim Start geprüft, ob der letzte Reset-Zeitpunkt seit dem gespeicherten Datum verstrichen ist — unabhängig vom heutigen Wochentag.

---

# Version 0.9.3

Release Date: 2026-08-02

## ⚡ Performance & Visual Fixes

- **Flow Map: Zoom no longer rebuilds cards** — Zooming now updates node card sizes and positions in-place (`apply_zoom()`) instead of destroying and recreating all cards. No more flickering on zoom.
- **Flow Map: Render before show** — Node cards are now built while the window is still hidden. When the Flow Map opens, all content is already ready — no blank-window flash.
- **Flow Map: Batched redraws** — `setUpdatesEnabled(False/True)` wraps all card creation in the renderer, so the map area repaints exactly once after a full rebuild instead of per-card.
- **Flow Map: Immediate card cleanup** — `clear_node_cards()` now calls `card.hide()` before `deleteLater()`, so old cards disappear instantly rather than lingering until the next event loop tick.
- **Flow Map: Native window pre-creation** — `winId()` is called at app startup to force the OS to create the Flow Map's native window handle early. The first `show()` no longer triggers an empty-window flash.
- **Flow Map: All widgets correctly parented** — `FlowNodeCard`, `FlowMapViewport`, `FlowGuideView`, `NodeEditorPanel`, `tool_bar`, `content`, `side_panel_wrapper`, and `side_panel` now receive their Qt parent at construction time instead of via `setParent()` after the fact. This eliminates the "many small Python windows" flicker that appeared at app startup and on every Flow Map open.
- **Flow Map: Editor panel closes after save** — Saving a node in the editor panel now automatically closes the panel.

---

# Version 0.9.2

Release Date: 2026-08-02

## ✨ New Features

- **Minimize to Tray** — When closing the app for the first time, a dialog asks whether to minimize to the system tray or exit completely. The choice is saved in `config.json`. Tray icon shows a context menu with *Open* and *Exit*; double-click restores the window. The option can be changed any time in Settings → General.
- **Flow Map: Root rename syncs Map name** — Renaming the root node in the editor panel automatically renames the map in the dropdown. No manual rename needed.
- **Flow Map: Overlay checkbox per map** — A purple "Overlay" checkbox in the top-left map selector controls whether that map's nodes appear in the overlay guide. Multiple maps can be checked; all their nodes are shown simultaneously. State is saved per map in the profile.
- **Profile duplication** — Duplicate an existing profile via a button on the Profile page. A small popup asks for the new profile name.

## 🐛 Bug Fixes

- **DPS Meter no longer starts on profile switch** — `_launch_dps_meter_if_configured()` now fires exactly once at app startup instead of on every `load_profile()` call. DPS Meter settings remain global (config.json only).
- **Flow Map editor panel closes after saving** — Saving a node in the editor panel now automatically closes the panel.
- **Flow Map node card window flicker fixed** — `FlowNodeCard` widgets were briefly created as parentless top-level windows before being reparented, causing small Python windows to flash on screen. Fixed by passing the correct parent at construction time.

## 🎨 UI Improvements

- Tray icon context menu labels update when language is changed.
- Flow Map overlay checkbox uses distinct purple highlight to distinguish it from the cyan "Move Children" checkbox.

---

# Version 0.9.1

Release Date: 2026-07-29

## ✨ New Features

- **Custom Timer system** — Create up to 2 fully configurable custom timers via a popup dialog. Each timer supports: a custom name (max. 10 characters), a color from 8 presets, a display format (`hh:mm:ss` or `mm:ss`), and an individual interval. `hh:mm:ss` timers use hour presets (1–6 h) or manual input via a pencil button; `mm:ss` timers use a minutes-only spinner (1–999 min).
- **Custom Timer notifications** — Each custom timer can be assigned its own notification sound in Settings → Notifications. The notification section is hidden until at least one custom timer is configured.
- **Timer page: Custom Timers section** — Active custom timers appear below the existing timers under a "Custom Timers" heading. The section is hidden until at least one timer is active.
- **Help tooltips on section headers** — Small "?" buttons next to *Reset Timer*, *Advanced Timer*, and *Custom Timer* headers show a short description on hover. Fully translated (DE / EN / RU).

## 🎨 UI Improvements

- **Advanced Timer rows cleaned up** — Removed the redundant description text below Shugo Timer and Riss Timer; the names are self-explanatory.
- **Settings page scroll** — The settings content area is now wrapped in a QScrollArea to prevent widget overlap at smaller window sizes.
- **Minimum window size** increased to 1 100 × 820 px to accommodate the additional Custom Timer content.

---

# Version 0.9.0

Release Date: 2026-07-27

## 🎨 UI Restructuring

- **About page moved to main navigation** — "About" is now a top-level sidebar entry alongside Tasks, Timers, Plan, Profile, and Settings. It is no longer buried inside Settings → General.
- **Settings navigation simplified** — reduced from 7 tabs to 5:
  - *Reset Timer* and *Advanced Timer* merged into a single **Timer** tab with two clearly labelled sub-sections.
  - **Notifications** extracted into its own dedicated tab (previously hidden in Advanced Timer).
  - About and Support rows removed from Settings → General.
- **Settings → General cleaned up** — now contains only app-level toggles: Event Tasks, Auto Save, DPS Meter, and Check for Updates.

## ✨ New Features

- **About page redesign** — larger app icon (80 px), bold title with visual separator, word-wrapped description, and a dedicated **Discord öffnen ↗** button that opens the developer's Discord profile directly.
- **Discord profile link** — clicking "Discord öffnen ↗" opens `discord.com/users/294899670017114122` in the browser or Discord desktop app.

---

# Version 0.8.9

Release Date: 2026-07-26

## ✨ New Features

- **DPS Meter integration** — Configure an external EXE (e.g. a DPS meter) in Settings → General. A toggle controls whether it starts automatically when the app opens. A manual **▶ Start** button lets you launch it at any time for testing.
- **Overlay: Guide node check-off** — Flow Guide nodes can now be toggled directly from the Overlay. Active nodes show a ○ button, completed nodes show ✓. Locked nodes are displayed but cannot be toggled. Changes are saved to the profile immediately.
- **First-run setup dialog** — On the very first launch the app asks whether existing profiles should be imported from a custom folder, or whether to start fresh. The dialog is shown once and skipped on all subsequent starts.

## 🐛 Bugfixes

- **Profile overwrite on path change** — Changing the profile folder in Settings no longer overwrites existing profiles with an empty state. The app now loads the existing profile from the new folder immediately after the path is confirmed.

---

# Version 0.8.7

Release Date: 2026-07-25

## ✨ New Features

- **Synchronized / Separate notification mode** — The notification section now has a toggle to switch between *Synchronized* (one shared warn time + On/Off for both timers) and *Separate* mode (independent warn time and On/Off switch per timer). Settings are saved to the profile.
- **0 min warn option** — All warn-time dropdowns now include "0 min" to trigger the notification exactly at spawn. Useful since Shugo has a 3-minute entry delay and Riss a 10-minute entry delay.
- **Per-timer warn ranges** — In Separate mode, Shugo offers 0 / 1 / 3 / 5 min and Riss offers 0 / 1 / 5 / 10 min, each matching typical entry scenarios for that boss.

---

# Version 0.8.6

Release Date: 2026-06-21

## 🌍 Internationalization

- **Russian language support** — Русский added as third language option in Settings → Language.
- **All UI strings fully translated** — progress bar labels (Done / Remaining / Total / Progress), card priority labels, Event badge, Flow Map tooltips, save status, zoom hint, and "Delete" dialogs now respond to language changes.
- **Timer intervals translated** — Shugo & Riss interval dropdowns (30 min / 1 hour / 2 hours / 3 hours) and the notification warn-time combo (1 / 5 / 10 min) show localized text. Existing profile values are migrated automatically.
- **Weekday buttons translated** — the weekly reset day selector shows Mo–Su in the active language (Пн–Вс in Russian, Mo–Su in English).
- **Toggle buttons translated** — On/Off toggles across all settings sections now show Вкл/Выкл in Russian and Ein/Aus in German at all times, including after clicking and after loading a profile.
- **Flow Map tool label translated** — the active-tool indicator ("Tool: Select") is now localized ("Инструмент: Выбрать" / "Werkzeug: Auswählen").
- **Event checkbox translated** — the "Event" checkbox in the shopping entry form shows "Событие" in Russian.
- **Notification section translated** — "Windows Notifications" title, "No Sound" entry, and "▶ Test" button are localized.

## 🐛 Bugfixes

- **Profile load fallback** — if the last-used profile path is stale (e.g. after an update), the app now automatically loads the first available profile instead of starting empty.
- **License system removed** — all license/auth code and the separate license server have been removed. The app runs standalone without any authentication.

---

# Version 0.8.5

Release Date: 2026-06-21

## ✨ New Features

- **Task & Shopping card editing** — clicking on any task or shopping card fills the top input form with its data. The "Add" button changes to "Update" for the duration. Click the card again or add a new entry to cancel.
- **Card selection highlight** — the selected card gets a theme-appropriate border color so it's always clear which entry is being edited.
- **Flow Map: Multiple Maps** — a dropdown in the Flow Map topbar lets you switch between maps. The "+" button creates a new map. All maps are saved per profile.
- **Flow Map: Delete Map button** — the "🗑" button next to "+" removes the active map after a confirmation prompt. At least one map is always kept.
- **Flow Map: Reset Map button** — the "↺" button at the bottom of the left toolbar clears all nodes from the active map after confirmation.

## 🐛 Bugfixes

- **"Update" button now edits the card correctly** — pressing Enter in the description field while a card was selected was still triggering the "add new entry" path, causing a duplicate to appear instead of updating the existing card.
- **Description now appears on cards that had none** — the description label was never added to the card layout when first created with an empty description, so adding one via the edit form had no visible effect.
- **Flow Map: Delete Map signal now connects on startup** — the signal was only wired in the lazy-init path of `open_flow_map_window`, but the window is created on app start. Clicking Delete did nothing as a result.

---

# Version 0.8.4

Release Date: 2026-06-20


## 🐛 Bugfixes

- **Update system now replaces the EXE correctly** — the updater was downloading the source code archive instead of the release asset, so reinstalling the same version had no effect. It now downloads the actual release ZIP, extracts it to a temp folder, and uses a robocopy batch script to replace the EXE files after the app closes — then restarts automatically.

---

# Version 0.8.3

Release Date: 2026-06-20

## ✨ New Features

- **Windows Notifications** — opt-in toast notification before Shugo & Rift spawn. Warning time is configurable (1 / 5 / 10 minutes). Enabled per profile in Settings → Advanced Timer.
- **Notification Sound** — choose any Windows system sound (from `C:\Windows\Media\`) to play alongside the notification. Includes a live preview button.
- **AppData Profile storage** — profiles are now stored in `%APPDATA%\Aion2 TM\Profiles\` for new installations. Existing installations keep their current folder. The path can be changed in Settings → Profiles at any time.
- **Flow Map: Home button in toolbar** — the Home button now sits at the top of the left toolbar (above the pointer tool), keeping the topbar clean.
- **Flow Map: Zoom to cursor** — mouse wheel zoom now zooms toward the cursor position instead of the top-left corner.

---

# Version 0.8.2

Release Date: 2026-06-19

## 🐛 Bugfixes

- **Flow Map: Changes now save correctly** — the "Saving..." indicator was purely visual and did not trigger an actual save. Every node change (add, move, edit, delete) now immediately saves to the profile.
- **Flow Map: Profile switch now updates the map** — switching profiles while the Flow Map was open kept showing the old nodes. The map now reloads and re-renders immediately when a new profile is loaded.
- **Flow Map: Map no longer jumps to root on every action** — any action that triggered a re-render (add node, add branch, tool switch, save) caused the viewport to scroll back to the root node. The map now stays in place and only centers on the root node when first opened.
- **Profile rename now creates a new file** — renaming a profile updated the name in memory but did not create a new JSON file or remove the old one. The new file is now created and the old one deleted immediately on rename.
- **Default profile preserved on rename** — renaming the Default profile now keeps "Default" as a separate blank profile instead of deleting it.

---

# Version 0.8.1

Release Date: 2026-06-16

## 🐛 Bugfixes

- **Profile saved on close** — tasks and progress were lost when the app was closed via the X-button without triggering a save action first. The app now automatically saves on close.
- **Flow Map: New nodes distributed evenly** — when adding new child nodes, they were always placed to the left when the sibling count was equal, causing a strong left drift. Placement now alternates evenly between left and right.

---

# Version 0.8.0

Release Date: 2026-06-16

## ✨ In-Game Overlay (HUD)

### Added
- New floating HUD overlay window — frameless, always-on-top, semi-transparent dark design
- **Tasks Mode** (default): shows all open tasks across all tabs with colored gradient rows per priority (High = red, Middle = amber, Low = blue)
- **Guide Mode**: shows active and locked Flow nodes with colored gradient rows per status
- Tasks can be checked off directly in the overlay — main app and profile sync instantly
- Gear icon opens mode switcher (Active Tasks / Guide Overview)
- Opacity slider in title bar (20–100%) — adjustable live without closing the overlay
- Draggable by title bar, resizable in height via bottom grip handle (min 80px, max 700px)
- Toggle button "⬛ Overlay" in left sidebar — highlights when active
- Profile name shown in overlay title bar
- DPS-meter-inspired colored gradient fill per row (left accent bar + color tint)
- Tab badges (D / W / DS / WS) per task row showing the source tab at a glance

## ✨ Flow Map — Drag & Drop

### Added
- Nodes can now be freely dragged to any position on the canvas
- Positions are stored in the profile JSON at zoom=1.0 and persist across sessions
- 5px threshold prevents accidental drag when clicking a node
- Auto-layout computes initial positions relative to the root node's actual saved position — prevents layout breaks when mixing saved and newly added nodes

### Changed
- Complete architectural refactor: from `QVBoxLayout`-based recursive rendering to absolute widget positioning
- New `FlowMapArea` canvas widget (8000×8000px) draws all bezier connections via `paintEvent`
- Canvas minimum size increased to 8000×8000 to eliminate node clipping at edges
- Root node starts at canvas center (4000, 4000) — equal 4000px headroom in all directions

### Fixed
- Nodes getting clipped/hidden when dragged toward canvas edges
- Children of a branch only activating the first child when parent was completed — now all children activate
- Auto-layout origin now anchors to root's saved position, preventing new nodes from appearing far from their parents

## ✨ Task Progress Bar

### Changed
- Replaced three separate stat cards (Total / Done / Remaining) and footer progress text with a single unified `TaskProgressBar` widget
- Gradient fill bar (Cyan → Purple) shows completion ratio at a glance
- Stats displayed with large bold numbers (24px) for readability without glasses
- Color-coded icons: ✓ green (Erledigt) · ○ amber (Offen) · Σ cyan (Gesamt)
- Text labels clearly visible below each stat (11px, colored)
- Percentage shown prominently on the right (22px)
- Shopping tabs show Kinah total in the extra info area

### Fixed
- Progress bar and stat counts now update immediately when a task is checked — previously required a tab switch to refresh

---

# Version 0.7.1

Release Date: 2026-06-15

## ✨ Profile Export / Import

### Added
- Export Profile button — saves current profile as a `.json` file via system file dialog
- Import Profile button — loads any `.json` profile file and switches to it immediately
- Toast notifications for successful export/import and import error

## ✨ Confirmation Dialogs

### Added
- Reset Profile now shows a confirmation dialog before wiping all tasks
- Clear Event Entries now shows a confirmation dialog before removing event data

## ✨ Donate Button

### Added
- Donate button in Settings → General with PayPal link
- QR Code dialog for direct PayPal scan (opens from secondary button)
- Green gradient styling for the donate button

## ✨ Flow Map — Branch Fix

### Fixed
- When a parent node was completed, only the first child was activated — now all children activate correctly

---

# Version 0.7.0

Release Date: 2026-06-15

## ✨ Update System

### Added
- Automatic update check on app start (GitHub Releases API, non-blocking background thread)
- In-app update dialog with release notes rendered from GitHub release body (Markdown)
- One-click in-place installation — downloads ZIP, extracts, copies files, clears Python cache
- "App neu starten" button after successful installation restarts the app automatically
- Manual update check button in Settings → General
- Profile header now shows active profile name and current version (top-left)
- Update button appears in header only when a newer version is available

### Internal
- `core/update_checker.py` — `QThread`-based GitHub API checker, emits `update_available(version, body)`
- `ui/update_dialog.py` — `_InstallerThread` + `UpdateDialog` with full install lifecycle
- `ui/widgets/header_widget.py` — repurposed from Discord placeholder to active profile display

## ✨ Flow Map

### Added
- Flow Map data is now persisted in the profile JSON (`flow_map` key)
- Flow Map loads automatically from profile on startup
- `render_flow()` called when Flow Map window opens — fixes empty canvas after profile load

### Changed
- Zoom limits: minimum 60%, maximum 100% (was 40%–140%)
- Zoom hint label updated to "Scroll | Zoom X%" consistently

## 🛠 Fixed
- `cursor: pointing-hand` removed from QSS (invalid Qt property — caused console warnings)
- Flow Map appearing empty on first open after profile load
- Silent KeyError in update toast when `tr()` was called without required format arguments
- Installer `app_root` and archive structure mismatch fixed

---

# Version 0.6.9

Release Date: 2026-06-15

## ✨ Guide Mode

### Added
- Implemented full Guide Mode with U-Bahn / metro map style canvas (QPainter-based)
- Nodes rendered as glowing colored dots based on status (green = completed, blue = active, amber = optional, gray = locked)
- Persistent node selection with colored ring indicator
- Labels below each node dot, automatically truncated at 14 characters
- Info bar at the bottom showing title, description and status icon of the selected node
- "Als erledigt markieren" / "Als offen markieren" toggle button — only shown for selectable nodes
- "Edit" button in Guide Mode info bar — opens the Node Editor for the selected node
- Mode switching between Edit and Guide via topbar buttons
- Dirty check when clicking a different node in Guide Mode while editor has unsaved changes
- Dirty check when switching between Edit Mode and Guide Mode with unsaved editor changes
- Mode button state reverts automatically if the dirty dialog is cancelled
- Node spacing increased to 160px horizontal with proportional branch offset for better label readability
- Hand cursor on all interactive Guide Mode buttons

## ✨ Node Editor

### Added
- "Optionaler Knoten" checkbox — marks a node as optional (shown as amber in Guide Mode)
- Editor panel now starts hidden and only opens when a node is explicitly selected
- Cancel and X button now fully close the editor panel instead of only collapsing it
- Dirty state tracking via `is_dirty` flag and `mark_clean()` method
- `blockSignals` during programmatic node loading — prevents false dirty state on node switch
- Unsaved changes dialog (Save / Discard / Cancel) when switching node selection with unsaved changes
- Title max length set to 25 characters

### Changed
- Cancel and X now share the same closing logic including the unsaved changes dialog
- Arrow toggle button (>> / <<) continues to collapse/expand the panel content only
- Editor panel is correctly reopened via `expand_editor_panel` even after a full close

## ✨ Delete Tool

### Added
- Delete confirmation dialog with context-aware options:
  - Node without children: "Löschen" + "Abbrechen"
  - Node with children: "Zwischenknoten löschen" (reparent children) + "Node + alle Children löschen" + "Abbrechen"
- Root node is protected from deletion
- Editor clears automatically when the selected node is deleted

## ✨ Flow Map

### Added
- Zoom now controlled by scroll wheel alone — Ctrl modifier no longer required
- New nodes and branches use localized titles based on the current application language
- Hand cursor applied globally to all QPushButton elements via QSS
- Back button removed from topbar (redundant with OS window controls)
- Zoom hint label updated to reflect the new scroll wheel behavior

### Changed
- `confirm_dirty_before_action()` centralized in `FlowController` — shared across node selection, cancel, mode switching and Guide Mode

### Internal
- `UnsavedChangesDialog` and `DeleteConfirmDialog` extracted into `delete_confirm_dialog.py`
- `FlowGuideCanvas` and `FlowGuideView` added as new modular widget files
- `close_editor_panel()` added alongside existing `collapse_editor_panel()` / `expand_editor_panel()`
- Translation keys added: `flow_optional_node`, `flow_new_node_title`, `flow_new_branch_title`, `flow_new_node_desc`

---

# Version 0.6.8

## ✨ Flow Editor Refactoring

### Added
- Introduced `FlowRenderer` for dedicated rendering logic
- Introduced `FlowController` for interaction and node manipulation
- Prepared modular architecture for future Flow features
- Added centralized debug structure (`flow_debug.py`) for future extensions

### Changed
- Split rendering logic from `FlowMapWindow`
- Split node interaction logic from `FlowMapWindow`
- Refactored recursive tree rendering
- Refactored connector creation
- Refactored children row creation
- Refactored card wrapper creation
- Improved overall separation of responsibilities
- Simplified `FlowMapWindow` into a coordinator instead of a monolithic class

### Improved
- Cleaner project structure
- Better maintainability
- Easier future implementation of:
  - Drag & Drop
  - Connection editing
  - Animated rendering
  - Auto layout
  - Search & Focus
  - Undo / Redo

### Internal
- Removed obsolete code
- Reduced duplicated rendering logic
- Reduced coupling between UI and business logic
- Prepared for further modularization into independent Flow components

# Version 0.6.6

## Flow Map
- Cleaned up Flow Map code after dynamic connector implementation.
- Removed unused imports and legacy connector code.
- Prevented empty connectors from rendering on leaf nodes.
- Simplified card wrapper width handling.
- Improved readability of the current Flow Map structure.
- Prepared `render_node_branch()` for modular refactoring.

# Version 0.6.5

## Flow Map
- Added dynamic point-to-point connection lines between parent and child nodes.
- Parent connection anchors now distribute automatically based on child count.
- Child connections now attach to the top center of each child node.
- Added curved connector rendering for branched layouts.
- Added straight connector rendering for vertically aligned nodes.
- Improved connector arrow positioning.
- Improved nested branch layout alignment.
- Removed visible debug anchors after successful connector validation.

# Version 0.6.4

## Flow Map
- Refactored Flow rendering preparation for dynamic connection system.
- Introduced subtree width calculation for nested branches.
- Parent containers are now prepared to align based on child subtree width.
- Added dynamic anchor point calculation for parent connection points.
- Added debug anchor visualization for parent and child connection positions.
- Improved branch layout calculation for future bezier connections.
- Child subtree widths are now calculated recursively.
- Branch spacing is now dynamically prepared for variable layouts.
- Connection height can now scale dynamically depending on number of child nodes.
- Refactored FlowNode sizing constants:
  - NODE_WIDTH
  - NODE_HEIGHT
  - ICON_BOX_SIZE
  - ICON_ASSET_SCALE
  - ICON_SIZE
  - TITLE_SIZE
  - DESCRIPTION_SIZE
- Improved icon rendering using asset scaling to compensate transparent padding.
- Internal preparation for point-to-point connector system.
- General code cleanup and layout restructuring.

# Version 0.6.3

## Flow Map

* Neues Zoom-System für die Flow Map integriert.
* Aktuellen Zoomwert in der Topbar ergänzt (`Ctrl + Wheel | Zoom XX%`).
* Zoom-Anzeige wird nun dynamisch bei Änderungen aktualisiert.
* Verbesserte Darstellung der Node-Karten bei verschiedenen Zoomstufen.
* Vorbereitung für automatische Zentrierung der Flow-Struktur im Viewport.

## Flow Editor

* Node Editor Panel überarbeitet.
* Ein- und Ausklappen des Editor-Panels optimiert.
* Verbesserte Symbolauswahl mit Icon-Vorschau.
* Speicherung von Titel, Beschreibung und Symbol direkt aus dem Editor möglich.

## Navigation & Tools

* Tool-System für Select, Add Node, Branch und Delete erweitert.
* Individuelle Cursor für alle Flow-Werkzeuge hinzugefügt.
* Hover-Feedback für Node-Aktionen verbessert.

## Debug & Development

* Erweiterte Maus- und Container-Debuganzeige im Footer.
* Anzeige von Content-, Map- und Container-Koordinaten ergänzt.
* Unterstützung zur Analyse von Viewport-, Map- und Node-Positionen hinzugefügt.
* Mehrere Darstellungsprobleme bei Viewport und Node-Rendering behoben.

## UI

* Verbesserte Darstellung der rechten Seitenleiste.
* Optimierungen bei Größenanpassung und Overlay-Positionierung.
* Footer-Informationen erweitert und übersichtlicher gestaltet.

## Fixes

* Problem behoben, bei dem Nodes zeitweise nicht sichtbar waren.
* Diverse Layout- und Rendering-Probleme in der Flow Map korrigiert.
* Stabilitätsverbesserungen beim Neurendern des Flows.


# Version 0.6.2

Release Date: 2026-06-04

## ✨ Added

### Flow Add Node Tool
- Added functional Add Node workflow
- Clicking a node while Add Node Tool is active now inserts a new node below it
- Added visual add indicator on node hover
- Added larger Add Node icon indicator
- Added custom Add Node hover behavior

### Flow Tool UX
- Improved tool cursor handling
- Added custom hold cursor while dragging the map
- Removed in-map tooltips for a cleaner editing experience
- Tool guidance is now handled through the toolbar

## 🎨 Improved

### Flow Node Layout
- Reworked Flow Node layout into dedicated areas:
  - Left icon area
  - Top title area
  - Center description area
  - Right completion area
  - Bottom add indicator area
- Restored proper node icon rendering
- Restored completion checkmark button
- Improved Add Node icon positioning
- Improved Add Node hover visibility
- Improved node readability and layout consistency

### Flow Map Interaction
- Improved map dragging behavior
- Improved cursor restoration after dragging
- Improved hover handling for nodes and connectors
- Reduced tooltip flickering and inconsistent tooltip sizing

## 🛠 Fixed

- Fixed Add Node indicator causing layout shifts
- Fixed missing node icon rendering after layout refactor
- Fixed completion button showing as text instead of checkmark
- Fixed Add Node button showing text instead of icon
- Fixed inconsistent tooltip behavior by removing map tooltips
- Fixed connector hover behavior
- Fixed node click behavior in Add Node mode

## 🚧 Prepared

- Prepared connector-based node insertion
- Prepared future branch rendering logic
- Prepared support for selecting exact connections when inserting nodes between branches
- Prepared foundation for:
  - Insert node between parent and child
  - Add Branch workflow
  - Branch-specific connector interactions

# Version 0.6.1

Release Date: 2026-06-03

## ✨ Added

### Flow Tool System

* Added dedicated Flow ToolBar
* Added Select Tool
* Added Add Node Tool
* Added Branch Tool
* Added Delete Tool
* Added active tool indicator in footer
* Added tool state management system

### Custom Icons & Cursors

* Added custom toolbar icons
* Added custom cursor icons

  * Select
  * Add Node
  * Branch
  * Delete
  * Hold / Drag
* Added dedicated Flow tool icon directory structure

### Flow Navigation

* Added map drag support
* Added custom drag cursor handling
* Added cursor restoration after dragging
* Added foundation for future connector interaction

### Node Editor

* Added collapsible editor panel
* Added bottom toggle control
* Added close button support
* Added automatic editor reopening when selecting a node
* Added icon support inside symbol dropdown
* Improved icon scaling and alignment

### Progress System

* Added node completion toggle
* Added node completion reversion
* Added automatic activation of the next node
* Added save state indicator

  * Saving...
  * ✓ Saved
* Replaced manual save workflow with autosave preparation

### Zoom System

* Added zoom levels:

  * 100%
  * 80%
  * 60%
* Added dynamic node scaling
* Added dynamic text scaling
* Added adaptive description visibility based on zoom level

## 🎨 Improved

### User Interface

* Improved Flow editor layout
* Improved top toolbar organization
* Improved footer information area
* Improved node card readability
* Improved symbol selection workflow
* Improved overall Flow Map usability

### Flow Icons

* Reworked Flow icon integration
* Increased dropdown icon size
* Improved icon positioning and visibility
* Standardized Flow icon handling

## 🛠 Fixed

* Fixed node description rendering during zoom changes
* Fixed editor panel visibility behavior
* Fixed save state update handling
* Fixed Flow layout alignment issues
* Fixed cursor restoration after drag operations
* Fixed connector hover behavior
* Fixed multiple Flow UI inconsistencies

## 🚧 Foundation for Upcoming Features

* Connector interaction system
* Add Node workflow
* Branch creation workflow
* Delete node workflow
* Connector descriptions
* Flow persistence and save/load system
* Guide Mode progression logic


# Changelog – Version 0.6.0

### Added
- New Flow Map module
- Flow Plan entry in sidebar
- External Flow Map window
- Flow Node data model
- Flow Node editor panel
- Flow Node icon selection
- Flow Node status system preparation
- Flow Map grid background
- Flow Map localization support

### Changed
- Improved Flow Map layout
- Improved Flow Map responsiveness
- Improved node editing workflow
- Improved project structure for future Flow Map features

### Planned
- Branching nodes
- Node completion system
- Progress / Guide Mode
- Save & Load Flow Plans
- Dashboard integration
- Drag & Drop positioning

# Changelog – Version 0.5.2

## Event System

* Added integrated Event system for Tasks and Shopping entries
* Removed separate Event tabs
* Added Event badges for entries
* Added Event filtering system
* Added Event visibility toggle through Settings
* Added automatic migration for old Event tabs
* Added "Clear Event Entries" profile action

## Tasks & Shopping

* Redesigned ShoppingCard layout
* Unified TaskCard and ShoppingCard design
* Added improved Kinah formatting:

  * 100k
  * 1m
  * 1.5m
* Added numeric validation for Amount and Price fields
* Added automatic profile saving for new entries
* Added Daily and Weekly total Kinah calculations

## Sorting & Filtering

* Added active Sort button highlighting
* Added active Filter highlighting
* Added ascending / descending sort toggles
* Added dynamic sort direction arrows
* Improved filtering system for Event entries

## Profiles

* Fixed profile name saving
* Fixed profile loading issues
* Fixed saved task loading from profiles
* Added styled tooltips
* Added Event cleanup option

## UI & UX

* Improved tooltip styling
* Improved Settings layouts
* Improved Reset Timer styling
* Improved Advanced Timer styling
* Improved button consistency
* Improved Shopping amount display
* Improved card spacing and readability

## General

* Multiple translation improvements
* Multiple QSS improvements
* Improved autosave behavior
* Improved refresh handling
* Improved completed state handling


# Aion2 Task Manager – Changelog v0.5.0

## Version 0.5.0

## Tasks & Shopping

* Added Event system for Tasks and Shopping entries
* Added Event badge for marked entries
* Removed separate Event tabs
* Added Event filtering system
* Added dynamic Event visibility through Settings
* Added persistent Event save/load support
* Added migration support for old Event tabs

## UI & UX

* Redesigned Sort/Filter bar
* Added active Sort button highlighting
* Added active Filter highlighting
* Unified ShoppingCard and TaskCard layouts
* Improved ShoppingCard structure and readability
* Added Shopping amount label styling
* Improved Kinah price formatting
* Added total Kinah calculation for Shopping tabs

## Shopping Improvements

* Added numeric-only validation for Amount and Price
* Added automatic Kinah formatting:
  * 100k
  * 1m
  * 1.5m
* Added Daily/Weekly Shopping total display

## Settings

* Added Event visibility controls
* Improved Settings translations
* Improved Advanced Timer layouts
* Improved Reset Timer layouts
* Improved combo button styling

## Profiles

* Fixed profile name saving
* Fixed profile loading issues
* Improved profile synchronization

## General

* Multiple translation fixes
* Multiple QSS improvements
* Improved button state handling
* Improved refresh/filter logic


## Version 0.4.0

Release Focus:

* Settings Redesign
* Shopping System Overhaul
* Priority System
* Improved Profile Handling
* Translation Expansion
* UI Consistency Improvements

---

# ✨ New Features

## 🛒 Shopping System Overhaul

The shopping tabs were fully redesigned and extended.

### Added Shopping Fields

Shopping entries now support:

* Priority
* Amount
* Title
* Location
* Price

### Priority System

Added a full priority system for:

* Tasks
* Shopping entries

Available priorities:

* Low
* Medium
* High

### Improved Shopping Layout

The shopping layout was rebuilt for better readability and consistency.

New order:

1. Priority
2. Title
3. Location
4. Amount
5. Price

### Shopping UI Improvements

* Compact amount input
* Compact price input
* Styled dropdown selection
* Better spacing and alignment
* Improved responsive layout

---

# 🔄 Sorting System

Added a new sorting header for task and shopping lists.

## Sorting Options

### Tasks

* Priority
* Title
* Location / Description

### Shopping

* Priority
* Title
* Location
* Price

## UI Improvements

* New sorting buttons
* Translation support
* Dynamic visibility depending on current tab

---

# ⚙️ Settings Redesign

The complete settings interface was restructured.

## New Settings Categories

### General

General application settings.

### Reset Timer

Contains:

* Daily reset settings
* Weekly reset settings

### Advanced Timer

Contains:

* Shugo Timer
* Rift Timer

### Layout

Theme selection and appearance.

### Language

Application language settings.

---

# 🎨 Settings UI Improvements

## Unified Dropdown Design

The following settings now use the new styled dropdown design:

* Language selection
* Shugo start
* Shugo interval
* Rift anchor
* Rift interval

## Improved Time Inputs

Daily and weekly reset time fields were redesigned:

* Wider input fields
* Improved readability
* Styled arrow buttons
* Better spacing

## Toggle Button Improvements

All toggle buttons now:

* Use translated On/Off states
* Share a unified visual design
* Update dynamically with language changes

---

# 🌍 Translation Improvements

Expanded translation coverage across the application.

## Added Translation Support For

* Settings categories
* Advanced timer labels
* Sorting labels
* Shopping fields
* Toggle buttons
* Descriptions
* Language settings

## Improved Language Synchronization

Settings pages now update dynamically when changing the application language.

---

# 👤 Profile System Improvements

## Improved Profile Saving

Fixed an issue where profiles were always saved as:

* Default.json

The application now correctly saves profiles using the currently selected profile name.

## Profile Edit Improvements

* Improved profile rename flow
* Better signal handling
* Improved profile synchronization

---

# 🧠 Internal Improvements

## SettingsPage Refactor

Large parts of the settings page were restructured:

* Improved translation handling
* Reduced hardcoded text
* Better reusable widgets
* Cleaner signal structure

## Theme Selection Improvements

Theme buttons now:

* Use proper grouping
* Support improved visual selection
* Display integrated theme logos

## Timer Improvements

* Improved timer configuration handling
* Better interval management
* Cleaner settings synchronization

---

# 🎯 UI/UX Improvements

* Improved spacing across settings pages
* Cleaner visual hierarchy
* More compact settings layout
* Better responsive behavior
* Unified dropdown styling
* Improved inline labels
* Better alignment of settings rows
* Cleaner shopping/task creation workflow

---

# 🐛 Bug Fixes

* Fixed profile saving always using Default
* Fixed missing event description labels
* Fixed untranslated settings labels
* Fixed missing settings attributes
* Fixed incorrect settings references
* Fixed mixed German/English UI elements
* Fixed sorting translation keys
* Fixed settings page initialization issues
* Fixed toggle synchronization issues
* Fixed advanced timer layout inconsistencies

---

# 📦 Technical Notes

## Updated Systems

* SettingsPage
* TasksPage
* ShoppingCard
* TaskCard
* ProfilePage
* MainWindow
* Translation System
* Theme System

## Styling Updates

Updated QSS components:

* settingsCombo
* settingsTimeInput
* sortButton
* settingsInlineLabel
* toggleButton
* priorityInput

---

# 🚀 Result

This update significantly improves:

* Visual consistency
* Settings usability
* Translation support
* Shopping management
* Timer configuration
* Profile handling
* Overall UI quality

The application now feels more modern, structured, and scalable for future features.


## 0.1.0

- Initiale PySide6 Version
- Profile
- Settings
- Timer
- Theme-System
- Render License Check