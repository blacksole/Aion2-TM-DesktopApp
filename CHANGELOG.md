# 🧪 Beta Area

These features are **not** part of an official update yet and are still under active development. Unlockable at your own risk via Settings → "Unlock Beta Area".

## Armory

### Item Database
- Searchable item database with filters for grade/rarity, category, shop, and PvP/PvE/Neutral gear type.
- Right-hand Categories sidebar groups the catalog into Gear, Wings, Arcana, Materials & Enhancement, Consumables, Tools & Services, Cosmetics, and Chests & Misc — pick one to narrow the list and the Category filter above it.
- Gear further breaks down into Weapons / Armor / Accessories via the Category filter.
- Wings get two dedicated filters (Equip Effect / Owned Effect) in place of Category/Class, matching how Wings stats actually work.
- Grade/Rarity filter is a row of colored pill buttons (one click, no dropdown needed).
- Optional "Show Item ID" checkbox to reveal the internal item ID column (hidden by default).
- Item names are colored by rarity throughout the table.
- Double-clicking an item shows its full details, including every possible substat/skill it can roll — purely informational here (no picking), since selecting real Soulbinding rolls only makes sense for an actually-equipped item in the Build Planner.

### Crafting Calculator
- Shows the full material chain for any craftable item: required ingredients can be expanded individually if they're themselves the result of another recipe.
- Filter by profession (Blacksmithing, Armorsmithing, Handicrafting, Alchemy, Cooking), category and rarity.
- Material icons show the matching rarity background (Common/Rare/Unique/Epic/Legend).
- "Vergleich" tab compares crafting an item directly versus transferring it from an existing item of the same line, including Kinah cost.

### Build Planner
- Assemble a virtual gear loadout slot by slot, with real item stats.
- Save multiple named gear sets per class (e.g. "Default", "PvP") and switch between them instantly; a Build Compare tab shows two sets side by side, including GearScore and every stat category.
- GearScore calculated from real item data, including enchant and exceed bonuses.
- PvP / PvE / Neutral gear filter, linked to a matching toggle on the stat panel — PvP and PvE can now be active at the same time, for building a mixed set.
- EQ Priority list: set an acquisition/upgrade order per equipment slot; items already on it show as a gold-star favorite (with an "Only favorites" filter) when picking gear normally.
- Consolidated stat panel (Main Stats, Sub Stats, Offense, Defense, Utility & Recovery, PvE Stats, PvP Stats).
- "Quick Select" button to auto-equip a full gear set — crafted, dungeon-drop (Expedition) or PvP Abyss Gear, matched to your race — in one click, plus a separate "Property Priority" editor to customize which substats get auto-picked per role and Gear Type.
- Daevanion Board tab: interactive per-class/deity board (real tier art, checkable stat/skill sidebar, auto-router for the cheapest path to what you've checked), with a "Stats Gained" summary of every stat the board currently grants. Feeds its skill-level bonuses into the Skill Planner and its stat bonuses into the stat panel/GearScore/damage estimate, and persists to your profile.
- Skill Planner tab: browse/filter class skills (Active/Passive/Stigma), track Skill Points and Stigma Points separately, build a Priority List (remove/favorite/star support), and an Arcana Calculator that finds the best-case Arcana card setup for a wishlist of extra skill levels. Each active skill shows its real per-level damage range, with an optional "Estimated Damage" toggle that scales it by your own current stats.
- Arcana tab: an Information sub-tab to browse all card types/sets — hover a card for its class skill preview, hover a Set banner for its 2-/4-piece Set bonus — and a Sets sub-tab showing your 5 real equip slots, including each assigned card's Empyrean Lord value; each card's Set, rarity, and individual skill/level assignments can now be set manually as well as via the Arcana Calculator, which also lets you pick which named build to apply a result into (or create a new one). Shares the same named build as the Skill Planner.
- Genius Insight tab: pick a stat for each of the 9 Lines on all 5 pet boards (with min/max ranges shown per pick and a lock toggle to protect a Line), save multiple named profiles, and see every board's picks totaled — feeding the stat panel and damage estimate the same way gear does.
- Your core attributes (Might, Dexterity, etc.) and equipped Arcana cards' Empyrean Lord values now feed their real derived bonuses (Attack increase, Evasion increase, Combat Speed, and more) into the stat panel and damage estimate — previously shown but not actually calculated.
- Each Equip Build can now be linked to a specific Arcana/Skill Planner build and Genius Insight profile, so only that combination counts toward its stat panel/GearScore/damage estimate — useful once you're keeping more than one of each around.
- Stat panel values now show a hover tooltip breaking down exactly where the number comes from (equipment, grouped into Weapon/Armor/Jewelry, plus Genius Insight, attributes, Arcana Lords, and the Daevanion Board); hovering a core-attribute/Lord value also shows what it feeds into, even at 0.

---

# Version 1.8.0

Release Date: 2026-08-31

## ✨ New Features

- **Build Planner (Beta): new Genius Insight tab** — pick a stat for each of the 9 Lines across all 5 pet boards (with the real min/max range shown per pick and a lock toggle to protect a Line), save multiple named profiles, and see every board's picks totaled. Feeds the stat panel and damage estimate the same way equipped gear does.
- **Build Planner (Beta): core attributes and Arcana Lord values are now actually calculated** — Might, Dexterity, and the rest of your attributes, plus each equipped Arcana card's Empyrean Lord value, now feed their real derived bonuses (Attack increase, Evasion increase, Combat Speed, Cooldown Reduction, and more) into the stat panel and damage estimate. These were shown before but never actually counted.
- **Build Planner (Beta): the Daevanion Board now feeds the stat panel, GearScore, and damage estimate**, not just the Skill Planner as before. A new "Stats Gained" summary on the board itself lists every stat currently granted (skills and passives excluded, since those already show in the Skill Planner).
- **Build Planner (Beta): Bracelets that roll a raw Empyrean Lord stat now count too**, on top of Arcana cards — both sources combine into the same total and the same derived bonuses.
- **Build Planner (Beta): a large batch of previously-missing equipment stats now feed the stat panel** — PvE/PvP Accuracy, Evasion, Attack, and Defense breakdowns; the full Boss Attack/Defense/Damage Boost/Damage Tolerance set; Block Penetration; Natural Flight Power and Stamina Regen; and per-damage-type resist/chance (Ailment-, Mental-, and Impact-type).
- **Build Planner (Beta): each Equip Build can now be linked to a specific Arcana/Skill Planner build and Genius Insight profile**, so only that exact combination counts toward its stat panel/GearScore/damage estimate — useful once you're keeping more than one of each around.
- **Build Planner (Beta): stat panel values show a hover tooltip breaking down exactly where the number comes from** — equipment (grouped into Weapon/Armor/Jewelry), Genius Insight, attributes, Arcana Lords, and the Daevanion Board. Hovering a core-attribute or Lord value also shows what it feeds into, even while it's still at 0.
- **Build Planner (Beta): Arcana Sets cards now show their Empyrean Lord value directly on the card.**

## 🐛 Bug Fixes

- **Build Planner (Beta): several real equipment stats weren't being counted at all** if your gear happened to roll them — Back/Front Attack, Accuracy Bonus, Evasion Bonus, Defense Bonus, Attack Bonus, Max Attack, Critical Attack, Endurance/Regeneration Penetration, PvE Attack/Defense, and Boss Attack were silently dropped due to a naming mismatch. Now counted correctly.
- **Build Planner (Beta): the Daevanion Board's node tooltip showed percentage-based bonuses (e.g. Combat Speed) as a much larger raw number** instead of the correct percentage (e.g. "250" instead of "2.5%").
- **Build Planner (Beta): quickly hovering between two Daevanion Board nodes could briefly show the previous node's bonus list rendered behind the new one.**
- **Build Planner (Beta): three Boss-related Daevanion stat names were corrected** to match their names everywhere else in the app (Boss Attack, Boss Damage Boost, Boss Damage Tolerance).
- **Build Planner (Beta): Smite and Smite Resist were shown as a plain number instead of a percentage.**

---

# Version 1.7.1

Release Date: 2026-08-30

## 🐛 Bug Fixes

- **Item Database (Beta): clicking "Wings" then immediately the "Equip Effect" filter could do nothing** — clicking it again a moment later worked. The filter dropdown wasn't done updating its own layout yet right after appearing.

---

# Version 1.7.0

Release Date: 2026-08-30

## ✨ New Features

- **Build Planner (Beta): manual Arcana card assignment** — each Sets-tab card now lets you pick its Set/rarity and the skill+level in each of its 4 slots directly, without needing the Calculator.
- **Build Planner (Beta): Arcana Calculator's Apply now asks which build to write into** — the currently active one, any other existing build, or a brand-new one — instead of always silently targeting whatever build happened to be active.
- **Build Planner (Beta): EQ Priority items now show as a favorite** (gold star) when picking gear normally, with a new "Only favorites" filter in the item picker.
- **Build Planner (Beta): PvP and PvE gear filters can be active together**, for building a mixed PvP/PvE set at once.
- **Skill Planner (Beta): shows each active skill's real per-level damage range**, plus an "Estimated Damage" toggle that scales it by your own current stats (an approximation — the game's own base stats aren't publicly known).
- **Skill Planner (Beta): the Priority List picker's hover tooltip now also shows a skill's specialization level bonuses** (e.g. "Lv 10: Removes all debuffs").
- **About page: new "Sources" section** crediting the external data/research sources the app's item, skill, recipe, and board data (and the new damage-formula estimate) come from.

## 🎨 UI Changes

- **Skill Planner (Beta): removed the separate manual "checked" bookmark** on skill cards — the existing Priority List favorite star already covers the same purpose.
- **Build Planner (Beta): Arcana Set Bonus hover tooltip no longer shows a source attribution line.**

## 🐛 Bug Fixes

- **Item Database: duplicate catalog rows (e.g. Wings) no longer show twice** — some items existed as exact duplicates under two different IDs; the same dedup already used for item pickers now also applies to the main table.
- **Build Planner (Beta): the equip item picker could flicker and immediately close instead of opening**, specifically on multi-monitor setups with mixed display scaling.
- **Build Planner (Beta): opening the item picker's own Grade/Rarity dropdown could close the whole picker.**
- **Item Database/Build Planner: Grade/Rarity dropdown items showed in plain white instead of their rarity color.**
- **Skill Planner (Beta): a skill's shown damage numbers didn't update when its level changed** while its detail panel was already open.
- **Build Planner (Beta): the Skill Planner and Arcana tabs' build-selection tabs could fall out of sync** after switching builds from one of the two.

---

# Version 1.6.0

Release Date: 2026-08-29

## ✨ New Features

- **Templates: "Import from Database" now opens the real Item Database** — search, icons, and a shop-type sidebar pre-filtered to purchasable items — instead of a plain name list.
- **Templates item picker: added a Block/Row view toggle**, matching the main Item Database's table view.
- **Item Database: Class filter replaced with a Shop filter** (Merchant NPC / Trade Shop / Black Cloud Merchants / Shugo Festival), matching how items are actually obtained.

## 🎨 UI Changes

- **Build Planner (Beta): Arcana Information/Sets tabs redesigned** — wider cards with each card's 4 assigned skills shown directly on it (right-aligned levels), and a hover tooltip with the full class skill breakdown on the Information tab.
- **Build Planner (Beta): Arcana Set selection now shows real in-game Set banner art** in place of plain buttons, and hovering a Set shows its 2-/4-piece bonus as a tooltip instead of a separate panel.

## 🐛 Bug Fixes

- **Templates: the "All Categories" filter listed the entire ~10,000-item catalog** instead of only items actually purchasable from a shop.
- **Templates item picker: Grade/Rarity filter counts didn't match the shop-filtered list** shown below it.
- **Templates item picker now opens without a noticeable delay**, fixing a slowdown while item icons were loading.
- **Fixed a crash that could occur while item icons were still loading in the background.**
- **Fixed several screens showing unreadable text or plain white/blank boxes when Windows itself is set to Dark Mode** — affected the ToDo list, Templates, the Build Planner's Substats panel, Quick Select dialogs, the Crafting Calculator, the Flow Map, and the in-game Overlay.

---

# Version 1.5.0

Release Date: 2026-08-29

## ✨ New Features

- **Build Planner (Beta): "Daevanion Board" tab** — an interactive board per class/deity: connect adjacent nodes to spend points on real stat/skill bonuses (plain connector cells don't count), click again to refund. Hovering a node shows a detail card (name, grade, cost, effects); a collapsible sidebar lists every stat/skill on the board, check any to highlight its node(s), then "Find best route" auto-connects them via the cheapest path. Your activated nodes persist to your profile and feed bonuses into the Skill Planner. Ships with Global's current board layout only.
- **Build Planner (Beta): "Build Compare" tab** — pick any two of the current class's saved gear sets and see GearScore plus every stat category (including PvE/PvP Stats) side by side, with the better value highlighted.
- **Skill Planner (Beta): Skill Points and Stigma Points tracking** — a "Skill Points Available" counter (base + your Monolith/Wisdom Stone progress) and a separate Stigma Points counter, plus a per-skill -/+ level counter on every skill card. The white number is always what you've manually invested (capped at 10, Stigma 20); any bonus from Gear or the Daevanion Board shows separately in blue.
- **Skill Planner (Beta): Priority List improvements** — slots can now be removed (shifting later ones up), any skill on the list gets a gold star on its card plus an "Only favorites" filter, and hovering a skill in the picker shows its full info. The list now also feeds equipment skill slots directly (a ring/weapon/etc. with a skill-bonus slot auto-picks from it).
- **Skill Planner (Beta): "Arcana Calculator"** — set a purple "wish" counter per skill for how much more level you want beyond Skill Points/Gear/Daevanion (capped live at whatever this season's cards could ever deliver), pick which Vigor/Magic card each of your 5 Lord card slots uses, and get up to 3 best-case combinations to judge your own randomly-farmed cards against (not a literal shopping list, since real card leveling is random). Any combination can be applied straight into a new **Arcana Sets** tab (alongside the existing card/set browser), which shares one named build with the Skill Planner.
- **Build Planner (Beta): Quick Select's crafted item set now reaches Epic tier**, continuing past the previous Unique-grade stopping point.
- **Build Planner (Beta): new "Duplicate Set" button** — copies a Set's full state (items, substats, enchant, Philosopher's Stone) into a new one instead of only starting empty.
- **Skill Planner: gear-picked Skills/Traits now add +1 Level automatically** to the matching skill, stacking if picked on more than one equipped piece.

## 🎨 UI Changes

- **Build Planner (Beta): "Property Priority" editor reorganized** into 3 groups (Weapon/Guard, Armor, Jewelry) with a dedicated tab per real gear piece, and the Armor tab's default priority list expanded from 7 to 14 ranks for better per-slot accuracy.
- **Build Planner (Beta): picked Substats and Skills now show in one combined list** instead of two separate tabs.
- **About page: "Cooperation" row now shows a named, icon-labeled button per community** (Discord/Twitch icon + name) instead of a single dropdown-menu button — includes a new Twitch link (soulflaresifu) alongside the existing Discord communities.

## 🐛 Bug Fixes

- **Skill Planner (Beta): the Priority List (and its saved builds) wasn't saved to your profile at all** — reset every time you reopened the app. Fixed, along with an empty slot always showing German text regardless of your language setting.
- **Build Planner (Beta): "Property Priority" editor's Bracelet list offered 6 values that can never actually be picked** — real customizable Bracelets only roll the 10 Deity stats. Its default priority list is now empty instead of pointing at unreachable values.
- **Build Planner (Beta): equipping a full gear set (Quick Select) or switching Sets is noticeably faster and no longer flickers.**
- **Armory (Beta): rarity item-slot backgrounds looked washed out** compared to the real game art — restored the actual per-rarity texture images.
- **Build Planner (Beta): "Use Philosopher's Stone" had three separate bugs** — wrongly hidden on some Common/Rare items that do have real substats, silently forgotten when reopening a slot or running Quick Select, and checking the wrong internal field for its grade requirement (so it applied to the wrong items). All fixed.
- **Build Planner (Beta): the item picker listed the same item twice** (Bound and Unbound versions) — now shown once.
- **Build Planner (Beta): the back-arrow/"X" buttons on the "Property Priority" editor looked like plain unstyled boxes** instead of matching the app's dark card look. Fixed.
- **About page: the "Cooperation" row and a "Useful Links" description showed raw placeholder text** instead of real text in all languages. Fixed.

---

# Version 1.4.0

Release Date: 2026-08-27

## ✨ New Features

- **Item Database (Beta): Categories sidebar** — a new right-hand panel groups the catalog into Gear, Wings, Arcana, Materials & Enhancement, Consumables, Tools & Services, Cosmetics and Chests & Misc, instead of one long flat category list. Picking a group narrows both the table and the Category filter above it to that group's own subcategories (Gear further splits into Weapons / Armor / Accessories).
- **Item Database (Beta): dedicated Wings filters** — Wings now has its own "Equip Effect" and "Owned Effect" filters (e.g. Attack Bonus, Flight Power, Back Attack) in place of Category/Class, since Wings stats work differently from regular gear.
- **Item Database (Beta): Grade filter as pill buttons** — the rarity filter is now a row of colored, one-click pill buttons (Common/Rare/Legend/Unique/Epic) instead of a dropdown.
- **Item Database (Beta): "Show Item ID" checkbox** — optionally reveals the internal item ID column (hidden by default).
- **EQ-Priority (Beta): "Only show equipped items" checkbox** — when picking an item for a priority slot, optionally filter the list down to just the items currently equipped in the Build Planner.
- **Build Planner (Beta): equipment saved with your profile** — the currently equipped gear and your class/race selection are now saved and restored together with your profile, so switching or reloading a profile keeps your loadout instead of resetting it.
- **Build Planner (Beta): Quick Select now includes dungeon-drop gear** — alongside the crafted Dragon Lord chain, the "Item-Set" dropdown now also lists dungeon sets (Expedition), sorted by GearScore with the strongest at the top and colored by rarity. A new "Gear Type-Filter" switches between them.
- **Build Planner (Beta): Gear Type-Filter linked to the PvP/PvE/Neutral toggle** — picking PvE shows Crafting sets, PvP shows Abyss Gear, and Neutral shows dungeon-drop sets. Defaults to PvE + Neutral and remembers your last choice in your profile.
- **Build Planner (Beta): PvP Abyss Gear in Quick Select** — the 5 Abyss rank sets (Decanus through High Commander) are now available in the Item-Set dropdown when PvP is active, automatically matched to your character's race (Guardian for Elyos, Archon for Asmodae).
- **Build Planner (Beta): real enchant range per item** — the enchant slider's maximum now reflects the actually equipped item's own max enchant + exceed level instead of a flat 0–30 range.
- **Build Planner (Beta): "Property Priority" editor** — a new gear-icon button next to "Properties" lets you customize which substats get auto-picked, per role (Attacker/Defender/Support) and per Gear Type (PvE/PvP), across 4 equipment categories (Weapon/Guard, Armor, Jewelry, Bracelets). Your choices are saved to your profile. Still Beta — Equipment-Priority list and character skills aren't factored in yet.
- **Settings: "View Log" button** — opens a read-only viewer for the app's diagnostic log (which window opened when, which assets/colors loaded or failed to, etc.), useful for troubleshooting without having to find the log file manually.

## 🎨 UI Changes

- **Item Database (Beta): item names colored by rarity** in the main table, matching the color already used for the Grade column.
- **Item Database (Beta): "Item Details" popup is now read-only** — double-clicking a row shows every possible substat/skill the item can roll as plain info, without the pick/select interaction (that only applies to an actually-equipped item in the Build Planner).
- **Item Database (Beta): Class filter now hidden where it never applies** — only shown for "All Categories" and "Gear" (classNames only ever matters for weapons), instead of appearing everywhere with no real effect.
- **App window title renamed to "Aion 2 Companion"** (was "Aion Companion").
- **Build Planner (Beta): enchant level shown under each equipped slot** — the redundant "change item" button under each equipment slot (clicking the icon itself already lets you change the item and its enchant) was replaced with a small "+N" label showing that slot's enchant level, so you can check at a glance whether every item has actually been enhanced. Its color now follows your chosen Layout theme (Settings → Layout) instead of one fixed color.
- **Armory (Beta) windows now follow your Layout theme** — the Item Database and Build Planner windows' background now match your chosen Layout theme (Settings → Layout: Abyss/Inferno/Emerald/Frostbite/Obsidian/Void) instead of always showing Abyss.
- **Build Planner (Beta): role buttons color-coded** — Attacker/Defender/Support now each get their own accent color (orange/blue/green) when selected, in both "Properties" and the new priority editor.

## 🐛 Bug Fixes

- **Armory (Beta): no styling at all in the installed release build** — Item Database, Crafting Calculator and Build Planner rendered with Qt's bare default look (flat grey, plain default buttons) instead of the app's actual dark theme, because the stylesheet file was being looked for at the wrong internal path and silently never loaded. Only ever affected the installed download, never running from source.
- **Armory (Beta): item slots showed a grey background instead of the rarity color** in the installed release build (worked fine when running from source) — the rarity backdrop is now drawn directly instead of loaded from an image file, so it can no longer depend on how a given build happens to bundle image assets.
- **Armory (Beta): now follows your language setting** — Item Database, Crafting Calculator and Build Planner previously always showed German text regardless of your chosen language (Settings → Language); all UI text (buttons, labels, tooltips, messages) now follows English/Deutsch/Русский correctly. Item, recipe, skill and material names stay in their original form (no official in-game translation exists yet for those).
- **Armory (Beta): Elementalist renamed to Spiritmaster** — matches the class's actual current name; affects the Class filter, Build Planner and Skill Planner.
- **Build Planner (Beta): "Quick Select" no longer resets enchant levels on earlier slots** — auto-equipping a full gear set previously only kept the enchant level of the last item it processed; every item now correctly keeps its own assigned enchant level.

---

# Version 1.3.2

Release Date: 2026-08-23

## 🐛 Bug Fixes

- **Armory (Beta): icons and item/recipe/skill data missing after installing from the download** — this only affected the installed release build, not running from source. The Item Database, Crafting Calculator and Build Planner now correctly show their icons and item/recipe/skill data after unlocking the Beta Area.

---

# Version 1.3.1

Release Date: 2026-08-23

## ✨ New Features

### Unlock Beta Area
- New toggle in Settings: "Unlock Beta Area" — opt into in-development features at your own risk. Shows a warning before enabling, since these areas aren't finished and may still change or misbehave.
- See the 🧪 Beta Area section above for what's currently available once unlocked.

---

# Version 1.3.0

Release Date: 2026-08-21

## ✨ New Features

### Custom Timer — sound and warning time right in the editor
- When creating or editing a custom timer, you can now pick a notification sound directly and preview it with one click.
- Also configurable: how many minutes in advance the notification fires (0/1/3/5/10 min) — previously it only notified exactly at expiry.

### Quick access on the Timer page
- New "+" button opens a popup for managing custom timers directly (add categories, add/edit timers) — no detour through Settings.
- New gear icon jumps straight to the timer settings.

## 🎨 UI Changes

### Profile management cleaned up
- Instead of a dedicated profile page, there's now a small "Profile" button under the avatar (top-left) for quick profile switching.
- Save, load, reset, clear events, duplicate, and export/import a profile are now bundled under Settings → Profiles.

### Tasks and Timers merged
- Instead of two separate sidebar entries, there's now a shared "ToDo" area with two prominent tabs at the top ("ToDo" / "Timer"), with Tasks/Shopping underneath as before.

### "Plan" renamed to "Flow Map"
- The sidebar entry was renamed from "Plan" to "Flow Map" in all languages.

### Settings — Timer section reorganized
- The former "Custom" tab under Timer settings is gone (management now happens via the new popup on the Timer page, see above).
- Shugo/Rift notification settings now live as a second tab directly under Timer, instead of their own menu entry.

---

# Version 1.2.0

Release Date: 2026-08-20

## ✨ New Features

### Template search in the toolbar
- The template dropdown when adding tasks and shopping entries is now searchable: just type to filter the list live instead of scrolling through a long list.

### Template dialog — search and sort by location
- The template dialog (Shopping and Tasks) now has a search field that filters the list live by title and location.
- Sorting by location is now also possible (alongside name, priority, schedule).

### About page — Useful Links
- New section with helpful tools for Aion 2 — currently Guildnest (guild management tool with Discord integration).

### Flow Map — new "Money" icon
- An additional symbol is available when creating a node.

## 🐛 Bug Fixes

- **Wrong icons in the Flow Map** — the "Dungeon" and "Broker Market" icons weren't displayed correctly after selection, showing the default symbol instead. Fixed.
- **Price changes to templates didn't apply to already-added entries** — e.g. changing a shopping template's price afterwards left already-added list entries at the old value. Changes to a template's title, location, price, priority and schedule are now automatically propagated to all entries created from it.
- **Character assignment on tasks visually disappeared** — assigning a character to an existing task afterwards didn't show the character badge on the card. Fixed.
- **Location missing on tasks** — tasks created from a template with a location set didn't show that location anywhere. It's now shown on the task card.
- **"+" branch icon misplaced** — zooming the Flow Map in or out left the "+" icon for adding a new node no longer sitting correctly on the connection line. Fixed.
- **Light background in Settings under Windows dark mode** — the Settings page showed a light instead of dark background under Windows dark mode. Fixed.
- **Abyss Command Shop — wrong currency** — the four Abyss Command templates were incorrectly set up with Abyss Points, even though they're bought with Kinah. Corrected.

## 🎨 UI Changes

- **About page — clear heading hierarchy**: page title, section titles (e.g. "Support", "Useful Links") and individual entries are now visually clearly distinguished (size/weight).

---

# Version 1.1.0

Release Date: 2026-08-15

## ✨ New Features

### New currencies: Nightmare Points & Shugo Coins
- Alongside Kinah and Abyss Points, there are now two more currency types: **NP** (Nightmare Points) and **SC** (Shugo Coins).
- Shopping cards display the price correctly as NP or SC.
- The template dialog lets you create and edit entries with the matching currency.
- The shopping total in the progress bar is now shown separately per currency — e.g. "100k Kinah + 52500 AP + 50 NP".

### Language-specific default profiles
- There are now three starter profiles: **Default [EN]**, **Default [DE]** and **Default [RU]** — each with translated template entries.
- On first launch, the app automatically picks the profile matching the configured language.
- Switching languages within a default profile automatically switches to the matching language default.
- User profiles appear at the top of the profile menu, with the default profiles below a separator line.

### Shop templates — Abyss Command Shop
- New templates for the Abyss Command Shop: Abyss Command (15,000 AP), Abyss Command: Proficiency (37,500 AP), Elite (75,000 AP), Special Mission (150,000 AP) — all weekly.

## 🐛 Bug Fixes

- **Incomplete translation in the Tasks tab** — several texts in the Tasks tab and the template dialog weren't translated in languages other than German. All affected fields are now fully wired into the translation system.
- **Profiles were modified on app start** — loading a profile automatically re-saved it, updating its timestamp and potentially overwriting data. The automatic save call on profile load was removed.

---

# Version 1.0.0

Release Date: 2026-08-14

## ✨ New Features

### Profile Avatar
- Clicking the profile circle in the header opens a file dialog (PNG, JPG, WEBP). The chosen image is cropped to a circle and shown as the avatar. The avatar is saved in the local configuration and persists across restarts.

---

# Version 0.10.0

Release Date: 2026-08-14

## ✨ New Features

### Template dialog — sorting with direction indicator
- The template dialog (Shopping and Tasks) can now be sorted by name, priority and schedule. Clicking the same button again reverses the sort direction. The active button is highlighted and shows an arrow (↑ / ↓).

### Template dialog — schedule and priority badges
- Every template in the list now shows a colored badge for schedule (daily / weekly / season) and priority (LOW / MID / HIGH) — including shopping templates not marked as general.

### Price field — hint about the K unit
- The price field's placeholder text now reads "Price (in K)", making it clear the price is entered in thousands (Kinah).

## 🐛 Bug Fixes

- **Tasks from character nodes were missing from the task list** — tasks (type: task) assigned to a character node incorrectly ended up in the shopping list. They're now correctly shown as task cards in the task list.
- **Character dropdown showed no entries** — after loading a profile or switching profiles, the character dropdown stayed empty. It's now populated correctly after every sync and after profile load.
- **Flicker when saving a node** — saving a node card rebuilt all cards, causing a visible flicker. Only the affected card is now updated.
- **Flicker when opening the Flow Map** — overlay positions were set with a delay, causing a brief flicker when opening the window. Positioning now happens directly on the resize event.

---

# Version 0.9.9

Release Date: 2026-08-14

## ✨ New Features

### Tasks tab — completely reworked
- "Daily Tasks" and "Weekly Tasks" were merged into a single "Tasks" tab. Daily, Weekly and Season can be switched via filter — exactly like in Shopping.
- Tasks are now template-based: pick a template from the dropdown, set schedule, priority and optionally a character.
- The template dialog now has two tabs: "Shopping" and "Tasks". Task templates have no price — only title, category and an optional character assignment.
- The template dialog automatically opens the tab matching the currently active tasks tab.

### Flow Map — edit list
- The character node now has an "Edit list" button that opens a dialog with two tabs: "Shopping" and "Tasks". Templates of both types can be assigned directly there.
- Items and tasks from the Flow plan automatically appear in the matching lists. Synchronization happens on save and on profile load.

### Season
- The Season end can now be entered as a date + time in the timer settings.
- The Season countdown appears as its own card in the timer overview and in the Tasks/Shopping tab once the Season filter is active.

### Shopping — reset timer per filter
- The reset countdown in the Shopping tab now adapts to the active filter: Daily → daily countdown, Weekly → weekly countdown, Season → countdown to Season end. No timer is shown for "All".

### Templates — priority & schedule when checking off
- Checking off a template now opens a popup where amount, priority and schedule can be adjusted directly — pre-filled with the saved template values.

### Price fields — k notation
- Price fields now accept shorthand notation: `42k`, `1.5k` etc. — for both Kinah and AP.

## 🐛 Bug Fixes

- **Unreliable node clicks** — clicks in the lower area of a node card weren't recognized. Fixed.
- **Shopping list showed no entries** — existing entries stopped displaying after certain actions, even though they were still saved. Fixed.
- **Flow Map: negative sizes on startup** — opening the Flow Map triggered Qt warnings about negative widget sizes, because the resize event fired before the window was fully built. Fixed.

## 🎨 UI Changes

- **Overlay**: every row shows `[Task]` or `[Shop]` as the type, a schedule badge (D / W / S) and — for shopping entries with a character assigned — the character name.
- **Edit list — dialog**: entries are now shown as individual bordered cards, matching the rest of the design. The list area is larger, the dialog wider and more spacious.
- **Edit list — close**: the button is now styled neutrally instead of blue, to clearly distinguish it from the add button.
- **Delete button**: now shows × instead of the trash can icon.
- **Character selection**: the dropdown shows "Char" as a placeholder. The first entry isn't selectable. The selection resets automatically after adding.
- **Root node**: always shows the home icon, regardless of the saved setting.
- **Character node editor**: the character icon can no longer be selected on the start node.

---

# Version 0.9.8

Release Date: 2026-08-10

## 🐛 Bug Fixes

- **Auto-Update: update wasn't applied** — the v0.9.7 release ZIP, due to a build error, only contained `Aion2.exe` instead of `Aion2 TM.exe` + `_internal/`. Robocopy therefore only copied an unrelated file into the app folder — `_internal/` and `Aion2 TM.exe` stayed unchanged. Correct flow now: download ZIP → replace `_internal/` contents → overwrite `Aion2 TM.exe` → restart `Aion2 TM.exe`.
- **Auto-Update: restart hardcoded to `Aion2 TM.exe`** — the updater previously derived the restart EXE name dynamically from `sys.executable`, which could lead to the wrong file being started. The EXE name is now fixed to `Aion2 TM.exe`.

---

# Version 0.9.7

Release Date: 2026-08-10

## 🐛 Bug Fixes

- **Switching the profile folder loaded the wrong profile** — after changing the profile folder, `last_profile.txt` was read even though it could point to an absolute path in the old folder. As a result, Timer, Tasks, Shopping and Plan weren't updated. Now the best profile from the new folder is always loaded directly (first non-default profile, falling back to Default).
- **PyInstaller: styles.qss not found** — `load_styles` now uses `sys._MEIPASS` in the compiled build, so the QSS file is found correctly inside the bundle.
- **Update offered without a valid asset** — the update checker offered updates even when no compiled release asset (`.zip`/`.exe`) existed. In that case, the GitHub source archive was downloaded, which can't update a PyInstaller exe. The update is now only offered when a valid asset exists.

## 🔧 Improvements

- **Build and release scripts** — `scripts/build_exe.bat` builds the exe via PyInstaller. `scripts/create_release.bat` builds it, creates the ZIP and automatically uploads it as a GitHub release asset (`gh` CLI required).

---

# Version 0.9.6

Release Date: 2026-08-10

## 🐛 Bug Fixes

- **Custom Timer: profile was saved too early** — `save_profile` was called before `custom_timers` and `timer_categories` were applied to the app state. This lost activated timers and categories on the next app start (the profile still held the old state). The `save_profile` call was moved to the end of the function so the complete, current state is always saved.

## 🔧 Improvements

- **Custom Timer dialog: field order in the Custom tab** — the **Start** field (start time) now appears first in the "Custom" mode tab, followed by the **Interval** field. More logical reading order: when first, then how often.

---

# Version 0.9.5

Release Date: 2026-08-10

## ✨ New Features

- **Timer categories** — custom timers can now be grouped into categories (headings). Up to 4 categories (1 default + 3 more) can be managed in the timer settings (add, rename, delete). The desired category is chosen when creating or editing a timer. On the timer overview page, timer cards appear under their category heading.
- **Max. 8 custom timers** — the previous limit of 2 custom timers is gone. Up to 8 timers can now be managed, freely distributed across categories.
- **Custom Timer start time** — creating a new custom timer now automatically pre-fills the current time as the default start time.

---

# Version 0.9.4

Release Date: 2026-08-06

## ✨ New Features

- **Custom Timer: 4 modes** — the Custom Timer dialog was completely reworked. Instead of a single display format, there are now four clearly separated modes:
  - **Daily** — countdown to a configured time of day (repeating daily), like the Daily Reset timer.
  - **Weekly** — countdown to a specific weekday + time (repeating weekly), like the Weekly Reset timer, including weekday buttons (Mo–Su).
  - **Hourly** — interval timer (1–6 h quick-select or manual HH:mm entry via a pencil button).
  - **Custom** — second-accurate interval via HH:mm:ss entry.
- Mode buttons replace the previous display-format dropdown. The summary line in the timer settings shows a matching summary depending on the mode (e.g. "Daily 09:00", "Weekly Tue 09:00", "Every 2h", "01:30:00").

## 🐛 Bug Fixes

- **Weekly Reset now fires on app start** — the weekly reset previously only triggered if the app was running exactly on the configured weekday. Starting the app on a different day (e.g. Thursday) after the reset time (Wednesday 09:00) had already passed meant the reset never fired. The app now checks on startup whether the last reset time has elapsed since the saved date — regardless of today's weekday.

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

* Integrated a new zoom system for the Flow Map.
* Added the current zoom value to the topbar (`Ctrl + Wheel | Zoom XX%`).
* The zoom display now updates dynamically on change.
* Improved node card rendering at different zoom levels.
* Groundwork for automatically centering the flow structure in the viewport.

## Flow Editor

* Reworked the Node Editor panel.
* Optimized collapsing/expanding the editor panel.
* Improved icon selection with icon preview.
* Title, description and icon can now be saved directly from the editor.

## Navigation & Tools

* Extended the tool system for Select, Add Node, Branch and Delete.
* Added individual cursors for all Flow tools.
* Improved hover feedback for node actions.

## Debug & Development

* Extended mouse and container debug display in the footer.
* Added display of content, map and container coordinates.
* Added support for analyzing viewport, map and node positions.
* Fixed several rendering issues with the viewport and node rendering.

## UI

* Improved rendering of the right sidebar.
* Optimizations to sizing and overlay positioning.
* Expanded and cleaned up footer information.

## Fixes

* Fixed an issue where nodes were temporarily invisible.
* Fixed various layout and rendering issues in the Flow Map.
* Stability improvements when re-rendering the flow.


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