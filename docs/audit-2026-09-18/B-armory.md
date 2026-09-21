# Audit B — ARMORY module (ItemDatabase/), Aion2 Task Manager v2.0.7

Scope: `ItemDatabase/app.py` (22,877 lines, 48 top-level classes), fetch/compute data scripts, `check_for_updates.py`, plus the host-app seam in `ui/main_window.py`. Read-only audit. All paths relative to `/home/florian/Work/tries/2026-09-18-aion-2/`.

Severity scale: HIGH / MED / LOW. Effort: S (<1 day) / M (1–3 days) / L (1–2 weeks).

---

## 1. Domain model

**Everything is plain dicts.** There is not a single dataclass or typed model in `app.py` — all 48 classes are Qt widgets/windows/caches. Game entities live as raw JSON dicts flowing from `data/*.json` files and two runtime network caches.

| Entity | In-memory shape | Where |
|---|---|---|
| Item (catalog row) | dict `{id:int, name, grade, categoryName, options, price, iconUrl…}` from `data/items_all.json` | loaded in `ItemDatabaseWindow._load_items` (app.py:22625), deduped Bound/Unbound (app.py:22652) |
| Item detail | dict `{level, gradeName, categoryName, mainStats:[{id,name,value}], subStats:[...], maxEnchantLevel, sources, subSkillCountMax…}` | `ItemDetailCache` (app.py:819) — per-id `data/details/{id}.json` disk cache + live POST to shugo.gg batch-details (app.py:856–864) |
| Stat totals | `dict[stat_id:str, float]` + per-slot breakdown `by_slot[stat_id][slot_id]` | `_compute_stat_totals_detailed` (app.py:18971), id normalization via `_GEAR_STAT_ID_ALIASES` (app.py:18988) |
| GearScore | float = Σ `detail["level"]` + enchant push | `_compute_gearscore` (app.py:19040); push rates `_GEARSCORE_NORMAL_RATE=1.0` / `_GEARSCORE_EXCEED_RATE=5.0` (app.py:1258–1259), empirically calibrated against real TW characters (comment block app.py:1240–1257) |
| Enchant model | pure functions with fitted constants: `estimate_enchant_bonus` (app.py:1135), `estimate_exceed_bonus` (app.py:1171), `estimate_armor_bonus` (app.py:1211), accessory/heroic/curve constants (app.py:1063–1084). **`ENCHANT_RATES.json` is read by no Python file at all** (verified by grep) — it and `ENCHANT_RATES.md` are documentation of the 117-sample calibration; the live numbers are hardcoded in app.py. LOW severity duplication risk (two sources of truth). |
| Sets (dungeon/tier) | `dungeon_sets.json` {source_tag: {root_name: …}} precomputed by `compute_dungeon_sets.py` (grouping rules lines 1–70); crafted-tier chains derived at runtime by BFS `_ordered_tier_chain` (app.py:7152) |
| Wings / Pantheon | `wings_items.json`, `pantheon_items.json` from questlog.gg tRPC (fetch_wings_items.py:1–23, fetch_pantheon_items.py:1–26); merged into totals via `_wings_stat_totals` / Lord-point totals (`_refresh_stat_info`, app.py:19090–19100) |
| Daevanion | 15×15 grid dicts `{id, r, c, g, cost, e:[{t:"s"/"k", n, v, skill_id}]}` from `daevanion_boards_s/a.json` (fetch_daevanion_start.py:1–24); stat-name canonicalization `_daevanion_stat_key` (app.py:12358) + label/id maps (app.py:12371–12520) |
| Skills / Arcana | `skills_all.json` (scraped gamers4.life RSC, fetch_skills.py:1–25), `arcana_class_skills.json` (questlog.gg tRPC, fetch_arcana_class_skills.py:1–25), `arcana_info.json` parsed out of item description flavor text (fetch_arcana_info.py:1–15 — **no numeric Arcana stat values exist in any API**) |

**Six-source stat merge.** The canonical build total = Equipment + Genius Insight + attribute-derived + Arcana-Lord + Daevanion + passive-skill (+ wings), merged in `_refresh_stat_info` (app.py:19057–19110) and duplicated for arbitrary builds in `_compute_full_build_totals` (app.py:20687). This is the de-facto "stat model" of the app and the core asset a recommendation engine must reuse.

**Persistence.** `LoadoutWindow.get_persistable_state` (app.py:19863) returns one dict persisted by the host under profile key `"build_planner"` (ui/main_window.py:2314 restore, 2420–2421 + 2485 save). Keys: `character_class`, `character_race`, `current_build_name`, `active_gear_types`, `stat_priority_profiles`, `monolith_level`, `skill_levels`, `skill_arcana_wish`, `skill_active_specs`, `current_skill_build_name`, `skill_builds_data` (per class → per build → priority + arcana_cards), `equip_builds_data` (per class → per build → `equipped`, `substats`, `enchant`, `philosopher_stone`, `priority`, `priority_progress`, `linked_skill_build`, `linked_genius_build`), `daevanion_active`, `daevanion_filter_checked`, `genius_builds_data`, `current_genius_build_name`, `pantheon_slots` (17 keys — the last two were missing from the first draft of this audit; `tests/test_build_planner_state.py` pins the exact registry).
- **MED risk, explicitly documented at app.py:19923–19928:** serialization is explicit-key; a new key added to build state but not to `get_persistable_state` is *silently dropped* on the next save/load round-trip. Recommendation: schema-driven (single key registry) serialization + a round-trip unit test. Effort S.

**Host sync.** No shared object, no Qt signals for state: the Armory is loaded lazily as a *module by file path* — `importlib.util.spec_from_file_location("item_database_app", db_dir/"app.py")` (ui/main_window.py:664–675) — kept as a singleton (`self._item_database_module`). State crosses the boundary by value: `set_pending_loadout_state` push (app.py:22068) and `get_loadout_state` pull at profile-save time (ui/main_window.py:873, 2420). Only one real signal crosses: `add_to_templates_requested` (ui/main_window.py:691–693). Language/theme are forwarded imperatively (`update_language` app.py:22090; module-global `_ARMORY_LANGUAGE`, app.py:35–48). The overlay reads the *persisted* dict, not the live window (ui/main_window.py:801–812).

---

## 2. Existing recommendation / optimization logic

### 2.1 Quick Select gear (auto-equip a set) — `QuickGearSelectDialog` (app.py:11092)
- **Algorithm: pure lookup, zero ranking.** Race + tier/dungeon-set → exactly one item per slot by *name* (docstring app.py:11093–11104 states stat-based ranking was explicitly deferred). Tier chains come from BFS over upgrade recipes (`_ordered_tier_chain`, app.py:7152); dungeon sets from precomputed `dungeon_sets.json` (`_build_dungeon_sets`, app.py:10625). Filters: rarity pills, PvE/PvP/Neutral tag gating (app.py:11119–11131).
- Complexity O(slots). **Limits:** name-exact resolution; level-45 cap hardcoded in `compute_dungeon_sets.py:26–33`; no "which set is best for me", no partial-upgrade suggestions.

### 2.2 Property Priority (substat auto-pick) — `_pick_priority_substats` (app.py:10924) + `StatPriorityEditorDialog` (app.py:11727) + `QuickStatSelectDialog` (app.py:11646)
- **Algorithm: greedy first-match walk.** For each slot, walk the ordered priority-name list (≤7 entries, `_STAT_PRIORITY_MAX_ENTRIES` app.py:10807) top-to-bottom, take the first unused case-insensitive name match among the item's real `subStats` until `count` slots filled. Applied at app.py:21239.
- **Inputs:** 6 profiles (2 gear types × 3 roles, app.py:10787–10788) × per-category ranked lists; defaults hand-transcribed from a community guide (`_DEFAULT_STAT_PRIORITY_BY_CATEGORY`, app.py:10824–10863 — **5 of 6 profiles are just copies of the PvE/Angreifer guide**, admitted at app.py:10809–10814). Dropdown options are catalog-verified via `data/stat_priority_options.json` (`compute_stat_priority_options.py`, frequency-ordered).
- **Limits (MED):** ordinal ranks only — no weights, no marginal value, no interaction with what's already stacked (e.g. picks Crit on every piece even past a soft cap); name-string matching with a one-entry alias table (`_STAT_NAME_ALIASES`, app.py:10917) is brittle against catalog renames (a shugo.gg relabel already bit them once, app.py:560). This is the natural seed of a real scoring function — the *profile data structure* is right, the *consumption* is simplistic.

### 2.3 Arcana Calculator (best-case card setup for a wishlist) — app.py:3128–3330
- **Algorithm: greedy sequential fill with an exchange-argument correctness sketch.** Per card type (5 usable Lord types, themes fixed up front via `ArcanaThemeChoiceDialog`):
  - `_arcana_best_card_contribution` (app.py:3128): pick 4 slot skills by (remaining need desc, priority rank), fill leftovers from the full pool; then spend the 5-point extra budget one point at a time, capped at 4/skill.
  - `_arcana_best_combination` (app.py:3208): sequential over types — a later type sees earlier coverage.
  - `_arcana_compute_combinations` (app.py:3237): up to 3 alternative combos by iteratively excluding the previous result's *need-based* (type, skill) pairs (the filler-vs-need distinction fixed a real 2026-09-13 bug, docstring app.py:3260–3280); results filtered at ≥50% coverage (`_arcana_result_coverage_percent`, app.py:3305).
- Complexity: trivial (≤5 types × ≤~40 skills × budget 5).
- **Limits (LOW-MED):** result depends on `usable_types` iteration order (no global optimum guarantee once wishes compete across types); the "alternatives" mechanism is an exclusion heuristic, not enumeration; no notion of stat-cards (Key/Hourglass/Dice/Lantern grant stats, not skills — outside the model, fetch_arcana_class_skills.py:19–21).

### 2.4 Daevanion auto-router (cheapest path) — `_daevanion_compute_auto_route` (app.py:12328)
- **Algorithm: greedy Steiner-tree heuristic** (self-declared in docstring): repeatedly connect the wanted node cheapest to reach from the current tree, via **multi-source Dijkstra** with lexicographic distance `(points, MaxMP-nodes-crossed)` (`_daevanion_shortest_from_tree`, app.py:12286), until the board point cap (`_daevanion_total_cost`, app.py:12271) runs out.
- Complexity: Dijkstra uses an O(V²) linear scan (no heap) per wanted node → O(W·V²), V=225 → fine (~½M ops worst case).
- **Limits (LOW):** greedy Steiner is not optimal (known ~2-approximation class); when the cap is hit it **skips all remaining wanted nodes at once** (app.py:12345–12347) instead of trying cheaper subsets; tie-breaking beyond MP count is arbitrary.

### 2.5 Build Compare — `_open_build_compare` (app.py:20591), `_compute_full_build_totals` (app.py:20687), `_compute_skill_compare_rows` (app.py:20882)
- **Descriptive, not prescriptive**: A-vs-B GearScore delta + full 6-source per-stat deltas + per-skill damage-estimate rows. A real 2026-09-03 bug (gear-only totals) was fixed by sharing the exact live pipeline (comment app.py:20670–20680). Inline HTML color spans for deltas (app.py:20656–20659).
- **Limit:** no "what explains the delta" attribution and no suggestion output — but it is the best existing seam for engine-computed explanations.

### 2.6 Crafting Compare (direct vs transfer) — CraftingCalculatorWindow "Vergleich" tab (app.py:10147–10260)
- **Algorithm:** upgrade-hop graph `_build_transfer_source_index` (app.py:7113 — deliberately includes non-Transfer pure-Kinah hops, documented real-data fix), **BFS shortest hop path** `_find_transfer_path` (app.py:7129, depth cap 12), reachability BFS for the target picker (`_reachable_targets`, app.py:10235), recursive Kinah/material rollup `_compute_tree_kinah` (app.py:7317) + `_flatten_material_tree` (app.py:7306).
- **Limits (MED):** BFS returns the *first* (fewest-hops) path, not the cheapest by Kinah/materials — with multiple recipes per output (`_transfer_by_output` keeps both variants, app.py:9548–9555) a cheaper longer chain is never surfaced; no craft-success probability, no market/AH pricing, "owned materials" only in the simulator tab.

### 2.7 Gear Level column — `CraftingItemPickerDialog._make_level_item` (app.py:9337)
- Lazy per-row detail fetch with placeholder "…" swapped by `_on_detail_ready` (app.py:9359); a synchronous disk-cache re-check avoids a stuck placeholder (documented race, app.py:9345–9352). Item level only exists in detail data, never in the catalog row (app.py:9338) — the recurring N-details-per-view cost is a direct consequence of the upstream API split.

**Summary judgment:** every "smart" feature is a well-documented, user-story-driven *greedy heuristic over dict data*, each locked inside a Qt class or module function of app.py. Nothing is exhaustive/ILP; nothing shares a common scoring vocabulary. That is exactly the gap a recommendation engine fills.

---

## 3. Where a recommendation engine plugs in

### 3.1 Existing seams (good news)
A large share of the logic is *already pure-Python and Qt-free in behavior*, just trapped in a Qt-importing module:
- Enchant/GearScore math: app.py:1063–1261 (pure functions + constants).
- Substat pick: `_pick_priority_substats` (app.py:10924) — pure.
- Arcana solver: app.py:3028–3330 — pure.
- Daevanion router: app.py:12271–12383 — pure.
- Transfer graph/BFS/cost rollup: app.py:7113–7360 — pure.
- Stat merge: `_compute_stat_totals_detailed` (app.py:18971) is *almost* pure — its only impurity is `self.detail_cache.get(...)` (app.py:18995).

### 3.2 Coupling that blocks it (in order of pain)
1. **`from PySide6...` at module import** (app.py:87–137): none of the pure functions can be imported without Qt installed and the whole 22.9k-line module executing (incl. a global `QComboBox.showPopup` monkey-patch, app.py:139–152). HIGH for testability.
2. **`ItemDetailCache` is a QObject with QNetworkAccessManager** (app.py:819): every totals/score computation needs it. Fix: define a tiny `DetailProvider` protocol (`get(item_id) -> dict | None`); the engine takes it as a parameter; the Qt cache already satisfies it structurally.
3. **LoadoutWindow methods on `self`** (`_compute_full_build_totals` reaches into genius/arcana/daevanion sub-state, app.py:20687–20730). Fix: pass the persisted build-state dict (already JSON-shaped — see §1) instead of `self`.
4. Module-level mutable singletons: `_ARMORY_LANGUAGE` (app.py:42), `_stat_priority_options_cache` (app.py:10888). Minor.

### 3.3 Proposed package (pure Python, Qt-free)
```
ItemDatabase/armory_engine/          # importable both by app.py and by pytest without Qt
    model.py        # TypedDicts / dataclasses for Item, Detail, BuildState, stat-id aliases
    stats.py        # totals merge (port of _compute_stat_totals_detailed + 6-source merge)
    enchant.py      # estimate_* + _gearscore_push + calibration constants (retire ENCHANT_RATES.json drift)
    score.py        # role scoring: priority profiles -> weight vector -> scalar score(build|item, role, gear_type)
    solvers/
        arcana.py       # move _arcana_* verbatim
        daevanion.py    # move _daevanion_compute_auto_route + Dijkstra (add heapq)
        transfer.py     # move transfer index/BFS + kinah rollup; add cost-weighted path (Dijkstra over Kinah)
        gear.py         # new: slot-upgrade search / set completion
    explain.py      # every recommendation returns (choice, list[Reason(stat_id, delta, weight, text_key)])
```
Explainability contract: solvers never return bare picks — always `(pick, score_delta, contributions)` so the UI can render "why this item" from data the engine already computed (Build Compare's per-stat delta rows, app.py:20591+, are the ready-made display surface).

### 3.4 Five concrete feasible features
| # | Feature | Data needs (all present) | Algorithm sketch | Effort |
|---|---|---|---|---|
| 1 | **Stat gap vs role target** ("you're 240 Accuracy under the PvE-Angreifer profile") | stat_priority_profiles + live totals (app.py:19057) | derive per-role target weights from profile ranks (e.g. rank→weight decay), normalize current totals, report top-k weighted gaps with per-source attribution from `by_slot` | **S** |
| 2 | **Missing set piece** | `dungeon_sets.json` + `equipped` | per set root, count equipped∩set vs set slots; surface nearest-complete sets and the missing slots' sources | **S** |
| 3 | **Best upgrade for slot X given budget** | catalog + details + recipes + enchant curves | candidates = items of slot's category ≥ current level; Δscore via `score.py` (main stats + best-case substats via `_pick_priority_substats`); cost via transfer path + `_compute_tree_kinah`; rank by Δscore/Kinah | **M** |
| 4 | **Cheapest GearScore +N** | details (`level`, `maxEnchantLevel`) + `_gearscore_push` + recipes | marginal-cost greedy across all slots: next enchant level (+1 or +5 GS per push rates, app.py:1258) vs item swap (Δlevel), pop cheapest until +N; exact because contributions are independent per slot | **M** |
| 5 | **What to craft next** | equip-build `priority` chains (persisted, app.py:19925) + recipes + `dungeons_all.json` reward cross-ref (fetch_dungeons.py:5–9 states this linkage is the point) | walk the player's Gear Priority chain, compute per-target remaining material tree minus owned, group by acquiring dungeon; order by (chain rank, completable-now) | **M/L** |

A true substat *optimizer* (marginal stat values, caps, DR curves) is **L** and gated on a combat model the data doesn't ship — defer; the rank-weight approximation in #1/#3 is honest and explainable.

---

## 4. Refactor plan for the monolith

### 4.1 The two hard constraints
1. **PyInstaller ships `app.py` as a DATA file**, not code: `('ItemDatabase/app.py', 'ItemDatabase')` in `Aion2 TM.spec` (datas list, ~line 10), matching the loader in ui/main_window.py:664–675 (`spec_from_file_location` under `sys._MEIPASS`). Consequence: app.py is *not* in the PYZ, is exec'd from source at runtime, and **any new module it imports must also be shipped as data and be importable from that directory**. A package split silently breaks the frozen build unless each new file/folder gets a datas entry — the spec's own comment documents this exact failure class already happening 5 times for data JSONs (v1.9.2 bug note in the spec).
2. **app.py's dir is not on sys.path** when exec'd by file location — but `BASE_DIR = Path(__file__).parent` already exists (app.py:223 vicinity); a one-line `sys.path.insert(0, str(BASE_DIR))` (or making the loader import a package) unlocks normal sibling imports in both dev and frozen mode.

### 4.2 Staged split (each stage shippable)
- **Stage 0 — characterization tests first (S).** No code moves. Add `tests/armory/` with golden-file tests over recorded detail JSONs: totals merge, `_gearscore_push`, enchant estimators vs ENCHANT_RATES.md tables, arcana solver on a fixture wishlist, daevanion route on a fixture board, transfer BFS on fixture recipes, and a `get_persistable_state` round-trip test (guards the silent-key-drop trap, app.py:19923). Requires PySide6 importable (module-level Qt import) — acceptable interim; Stage 1 removes it.
- **Stage 1 — extract the pure engine (M). This is the safe first slice.** Move the §3.1 pure blocks verbatim into `armory_engine/` (no Qt import anywhere in it); app.py re-imports them under the same names so all 700+ internal call sites keep working. Add ONE datas entry (`ItemDatabase/armory_engine` recursive) to *both* specs. Tests from Stage 0 now run Qt-free. Low risk: pure code moves, no behavior change, import errors fail loudly at startup.
- **Stage 2 — split leaf windows by feature (M each).** Order by lowest coupling: `crafting.py` (CraftingCalculatorWindow + pickers, ~9,000–11,000), `daevanion_ui.py` (canvas + tooltips), `arcana_ui.py` (5133–5452, 8687–8874, 13150–13920), `pickers.py` (ItemPickerPopup/TemplateItemPickerDialog), `caches.py` (IconCache/ItemDetailCache), `table.py` (ItemTableView/proxy/ItemDatabaseWindow). Keep `app.py` as a facade that re-exports `create_window`, `TemplateItemPickerDialog`, `_load_qss_text` — the only names the host touches (ui/main_window.py:685, 777–782).
- **Stage 3 — LoadoutWindow last (L).** ~7,456 lines (13922–21378) and the god object; only attack it after the engine extraction has already pulled its computation core out, leaving mostly layout code. Split by tab (equip / skills / genius / daevanion / arcana / compare) with the persisted state dict as the interface between tabs.
- **Do not rename the module** loaded as `"item_database_app"` or change `create_window`'s signature until Stage 3 — that string and the singleton pattern are the host contract (ui/main_window.py:668).

### 4.3 Findings
- **HIGH / structural:** 22,877-line single module with UI+logic+data access interleaved; any UI change risks the calculators. The Stage-1 engine slice removes ~80% of that risk for the features Florian cares about. Effort M.
- **MED:** global `QComboBox.showPopup` monkey-patch (app.py:139–152) executes at Armory *import* and mutates combo behavior of the entire host app (module is loaded in-process). Intentional, but should live behind an explicit `install_combo_hover_fix()` call. Effort S.
- **LOW:** duplicate `_ARCANA_SKILL_SLOTS_PER_CARD = 4` definition (app.py:3028 and 3054).

---

## 5. Data pipeline risks

**Four third-party sources, none contractual:**
| Source | Used for | Mechanism | Risk |
|---|---|---|---|
| shugo.gg | items catalog, per-item details, icons — **also live at app runtime** | REST + spoofed `Referer/Origin` headers both in fetchers (fetch_items.py:15–18) and in the shipped app (app.py:858–859, 922) | **HIGH**: ToS unknown; header spoofing signals it isn't a public API; a block/relabel breaks live detail/icon fetch for all users. Mitigation: fetch_item_details.py's full pre-warm (its docstring, lines 5–15, states runtime independence as the goal) — finish the job by also pre-bundling icons (see offline below) |
| gamers4.life | skills, recipes, dungeons | scraping Next.js RSC payloads out of rendered HTML via sitemap crawl (fetch_skills.py:3–8, fetch_recipes.py:4–11) | **HIGH fragility**: RSC string-escaping parser (`_unescape`, fetch_recipes.py:57+) breaks on any site redeploy; polite 0.35s delay is good, legality still unasked |
| questlog.gg | arcana class skills, wings, pantheon | undocumented tRPC endpoints found by grepping their JS chunks (fetch_arcana_class_skills.py:3–8); pantheon pull downloads a ~30MB payload to keep 236 items (fetch_pantheon_items.py:12–16) | MED: private API, can vanish silently |
| talentbuilds.com | daevanion boards (both variants) | UTF-16 embedded `boardsData` JS decoded as JSON (fetch_daevanion_start.py:4–8) | MED |

- **`data/` is gitignored and absent in this clone** (confirmed: `ls ItemDatabase/data` → absent). App degrades soft (`arm_no_cached_data`, app.py:22626–22628) but nearly every Armory feature is dead without it. **MED**: no manifest states which files at which version constitute a working set — the spec's hand-maintained 13-file datas list *is* the implicit manifest, and it already went stale once (5 missing files, v1.9.2 bug documented in `Aion2 TM.spec` comment). 
- **~278MB caches inside the data dir** (`data/icons/`, `data/details/` — sized in the spec comment). Cache dirs are `BASE_DIR/data/...` (app.py:223–224): in the frozen onedir build that resolves under `_MEIPASS`/`_internal`, i.e. **runtime cache writes land inside the install directory** — breaks on read-only installs, bloats updates, and is wiped by reinstall. MED. Recommendation: platform user-cache dir (e.g. `%LOCALAPPDATA%/Aion2TM/cache`) with migration. Effort S.
- **Offline mode** is only a README idea (README.md:137: opt-in "Use app offline" download). Details are already pre-warmable; icons are not pre-fetched by any script (only on demand) — an offline pack needs a `fetch_icons.py` sweep + bundling strategy.
- **Update cadence**: `check_for_updates.py` re-runs all 8 fetchers + 2 computes, then prints a **semantic JSON diff** (id-paired, leaf-level — its docstring lines 15–28) for human review before commit; scheduled Wednesdays via `setup_weekly_check.bat` (Windows Task Scheduler) with a `--if-due` catch-up path. Good design; gaps: no schema validation of fetched payloads (a half-rendered page can still write garbage that only the diff reader might catch), fetch scripts have no retry/backoff beyond politeness sleeps, and `fetch_daevanion_*`/`fetch_wings`/`fetch_pantheon` are **not in the weekly list** (FETCH_SCRIPTS, check_for_updates.py:57–66) — silent staleness channel. MED, effort S to add.
- **Data-pack versioning proposal (M):** ship `data/pack_manifest.json` = `{pack_version, game_patch_label, generated_at, files: {name: {sha256, count, schema_version}}}` written by check_for_updates.py; app validates presence+schema_version at startup and shows one "data pack vX from DATE" line; release data packs as a separate downloadable artifact (zip) so data refreshes decouple from app releases and the offline-mode idea becomes "download latest pack". This also collapses the spec's per-file datas list to one pack folder + manifest check.

---

## 6. UI-relevant observations inside Armory

- **Inline styles vs styles.qss:** 98 `setStyleSheet` call sites in app.py against a 30KB `styles.qss`. Many are principled (grade colors as data-driven foreground, app.py:11238; role accent colors routed properly through objectNames + QSS, app.py:10794–10800), but ad-hoc HTML `<span style=...>` color literals recur (e.g. compare delta app.py:20656–20659) and hex constants (`#4ade80`/`#f87171`, `#e5e7eb` icon default app.py:7333) are sprinkled rather than centralized. LOW-MED; a `colors.py` token module (feeds both QSS template and code) is effort S and prerequisite for any theming work.
- **Duplication across dialogs:** the pill-button-group pattern (gear-type row, role row) is hand-rolled ~4× nearly verbatim (QuickGearSelectDialog grade pills app.py:11215–11245, QuickStatSelectDialog app.py:11674–11706, StatPriorityEditorDialog app.py:11820–11850); slot-group checkboxes are properly shared (`_build_quick_slot_group_rows`, app.py:10963) — extend that precedent with a `make_pill_row()` helper. LOW, S.
- **Table/list performance:** main table = QStandardItemModel + `ItemFilterProxyModel` (app.py:21485) with chunked timer-driven population (`_load_items_chunk`, app.py:22677; ~5s for ~10k rows, filter combos correctly disabled during load per app.py:22630–22635). No QThreads anywhere — all network I/O is async QNetworkAccessManager on the GUI thread (fine). Watch: `_on_detail_ready`/`icon_ready` fan-out walks row registries per signal; and `CraftingItemPickerDialog` fires one detail request per visible row (app.py:9337–9352) — cheap only because the disk cache is pre-warmed; with an empty cache this is thousands of sequential HTTP roundtrips (the 17s cold-start figure in compute_dungeon_sets.py:3–5 confirms the class of cost). MED for fresh installs → another argument for the offline pack.
- **i18n coverage:** genuinely good — 466 `_t()` call sites, ~1,164 `arm_*` key references in `core/translations.py`, 3 shipped language default profiles (spec datas). Deliberate and documented: game-data names stay English (app.py:51–59). Internal identifiers are German ("Angreifer"/"Verteidiger"/"Support" as persisted keys, app.py:10788 — stable IDs, correctly translated only at display, app.py:10801–10806); cosmetic but confusing for contributors. LOW.
- **A note on quality:** the file's comment discipline is exceptional — nearly every heuristic carries provenance ("User-Wunsch/-reported" + date + evidence). Any refactor must preserve these docstrings verbatim; they are the only spec of the game's empirical mechanics (enchant curves, GearScore rates, stat-id maps).

---

## Priority matrix (top actions)

| Finding | Severity | Effort | Action |
|---|---|---|---|
| Runtime dependency on shugo.gg with spoofed headers (app.py:858) | HIGH | M | offline data/icon pack; degrade gracefully |
| Monolith blocks safe feature work | HIGH | M | Stage-1 `armory_engine/` extraction (§4.2) |
| Explicit-key state serialization silently drops new keys (app.py:19923) | MED | S | key registry + round-trip test |
| Weekly check misses daevanion/wings/pantheon fetchers (check_for_updates.py:57) | MED | S | add to FETCH_SCRIPTS + manifest |
| Cache writes inside install dir (app.py:223) | MED | S | user-cache dir migration |
| Recommendation features are name-rank greedy only (§2) | MED | S–M each | ship features 1–4 from §3.4 on the engine |
| Global QComboBox monkey-patch on module import (app.py:139) | MED | S | explicit installer function |
| ENCHANT_RATES.json dead vs hardcoded constants (app.py:1063) | LOW | S | make constants the generated artifact, or delete the JSON |

---

## Stage 1 done — 2026-09-19

§4.2's "safe first slice" is landed. The pure blocks of §3.1 now live in
`ItemDatabase/armory_engine/` (Qt-free, 9 modules, 1 921 lines), app.py
re-imports them under exactly the names it had, and app.py went from **23 123
to 22 046 lines** (−1 195 moved out, +118 of import block and wrapper/`self`-read
documentation back in). Behaviour-preserving by construction: the code was moved
verbatim, and every number is pinned by goldens recorded from the
*pre-extraction* app.py.

### Function map (old app.py line → new module)

| Old app.py | Moved to | What |
|---|---|---|
| 1175–1440 | `enchant.py` | `_GEAR_STAT_ID_ALIASES`, `_SCALING_STAT_ID`, accessory/weapon-curve/Heroic constants, `_rune_enchant_bonus` + its 4 constants, `estimate_enchant_bonus`, `estimate_exceed_bonus`, armor/belt constants, `estimate_armor_bonus`, `estimate_armor_exceed_bonus`, `_GEARSCORE_NORMAL_RATE`/`_EXCEED_RATE`, `_gearscore_push` |
| 3131–3544 | `arcana.py` | the Arcana Planner block: `_ARCANA_LORD_TYPES`/`_LORD_CATEGORY`/`_GRADE_MAX_LEVEL`/`_ACTIVE_THEMES`, `_arcana_usable_lord_types`, the card model (`_arcana_card_slot_list`/`_card_grade`/`_card_level`), `_arcana_eligible_skills_for_type`, `_arcana_full_pool_for_type`, `_arcana_best_card_contribution`, `_arcana_best_combination`, `_arcana_compute_combinations`, `_arcana_result_coverage_percent`, `_arcana_eligible_types`, `_arcana_max_ceiling`, `_arcana_uncovered_reason` |
| 7216–7348, 7395–7488 | `transfer.py` | `_item_type_word`, `_item_grade`, `_transfer_source_name`, `_build_transfer_source_index`, `_find_transfer_path`, `_ordered_tier_chain`, `_parse_gold_cost`, `_build_recipe_output_index`, `_resolve_material_name`, `_build_material_node`, `_build_material_tree`, `_flatten_material_tree`, `_compute_tree_kinah` |
| 8757 | `stats.py` | `_parse_stat_value` |
| 10781–10830 | `sets.py` | `_build_dungeon_sets` (+ its cache and path), **signature changed**: `detail_cache: "ItemDetailCache"` → `detail_provider: DetailProvider \| None`, plus an optional `path` for tests |
| 10955–10960, 10981–11061, 11087–11124 | `substats.py` | `_STAT_PRIORITY_GEAR_TYPES`/`_ROLES`/`_MAX_ENTRIES`, `_DEFAULT_STAT_PRIORITY_BY_CATEGORY`, `_default_stat_priority_profiles`, `_merge_stat_priority_profiles`, `_STAT_NAME_ALIASES`, `_normalize_stat_name`, `_pick_priority_substats` |
| 12426–12530 | `daevanion.py` | `_daevanion_neighbors`, `_daevanion_is_reachable`, `_daevanion_total_cost`, `_daevanion_spent_cost`, `_DAEVANION_MP_NAMES`, `_daevanion_node_mp_count`, `_daevanion_shortest_from_tree`, `_daevanion_path_nodes_to_add`, `_daevanion_compute_auto_route` |
| 19104 (`LoadoutWindow._compute_stat_totals_detailed`) | `stats.compute_stat_totals_detailed` | body moved; the one impurity, `self.detail_cache.get`, became the `provider` parameter. The method stays as a **thin wrapper** — it is the seam the live panel and Build Compare both call |
| 19173 (`LoadoutWindow._compute_gearscore`) | `stats.compute_gearscore` | same shape, same wrapper treatment |
| — (new) | `model.py` | `Item`/`Detail`/`StatEntry`/`EquipBuild`/`BuildState` TypedDicts (descriptions of the existing dicts, `total=False`), `StatTotals`/`StatsBySlot` aliases, and the **`DetailProvider` Protocol** §3.2 item 2 asked for |
| — (new) | `explain.py` | §3.3's contract as frozen dataclasses: `Reason(stat_id, delta, weight, text_key, text_kwargs)` with a `score_contribution` property, and `Recommendation(pick, score_delta, reasons)`. Data only, no logic |

### What stayed in app.py, and why

- **Everything that draws or loads.** Label/colour tables
  (`ARCANA_LORD_EFFECTS`, `_DAEVANION_STAT_LABELS`, `_ROLE_LABEL_KEYS`,
  `_ROLE_BUTTON_OBJECT_NAMES`), the `_load_*` readers that resolve
  `data/*.json` against app-relative paths (`_load_recipes`,
  `_load_arcana_class_skills`, `_load_stat_priority_options`,
  `_daevanion_variant`), and `_recipe_method` (only `_load_recipes` uses it).
- **`_compute_full_build_totals` (now app.py:19681) — the notable one.** Its
  sibling became a wrapper because it read exactly one thing off `self`. This
  one calls **nine** further `LoadoutWindow` methods, each over a different
  persisted sub-tree: `_linked_genius_build_name_for`,
  `_genius_stat_totals_for`, `_attribute_derived_stat_totals`,
  `_arcana_lord_stat_totals`, `_wings_stat_totals_for`,
  `_compute_equipped_skill_bonus_for`, `_linked_skill_build_name_for`,
  `_compute_arcana_card_skill_bonus_for`, `_passive_skill_stat_totals_for`.
  Extracting it means extracting the whole six-source merge of §1 — each
  source with its own loader and label tables — and the honest interface for
  that is the persisted build-state dict (§3.2 item 3), not nine more
  parameters. Half-extracting it would leave two merges that must agree,
  which is verbatim the 2026-09-03 gear-only-totals bug this method was
  written to fix. It moves whole, in the wave that moves
  Genius/Arcana/Daevanion/wings, or not at all. The full `self`-read list is
  now in its docstring.
- **The `QComboBox.showPopup` monkey-patch** (§4.3 MED) — untouched; it is a
  Qt concern and a separate decision.

### Two findings from doing the work

- **`heapq` in the Daevanion Dijkstra (§2.4) is NOT a free win.** Measured
  before moving: 400 randomized 6×6 boards, a `heapq` port compared against
  the O(V²) linear scan. `dist` matched on every board; **`prev` differed on
  169 of 400**. The linear scan's `d < best_d` keeps the first minimum it
  meets — `grid.values()` insertion order — while a heap breaks ties on
  `(distance, node_id)`. Costs are small integers on a dense grid, so ties
  are the common case, and `prev` is what decides which equal-cost path is
  materialized and therefore which nodes enter the tree. (A first pass showed
  *zero* mismatches, with synthetic `r{r}c{c}` node ids whose lexicographic
  order happens to equal the grid's row-major order; real questlog ids are
  arbitrary strings.) The linear scan stays, with the evidence in
  `armory_engine/daevanion.py`'s docstring. A heap would need an explicit
  tie-break on the grid's insertion index.
- **§2.4's "when the cap is hit it skips all remaining wanted nodes" can
  never fire on the point cap.** `cap` is `sum(cost)` over *every* node on the
  board and the tree is a subset of the board, so `spent <= cap` always
  holds. The branch is reached only by an **unreachable** target — a node
  walled off by `"empty"` cells. The limitation is real, its trigger is not
  the budget; the golden fixture now walls off a node to exercise it.

### Tests + gates

- `tests/test_armory_engine_golden.py` — 704 tests. Goldens in
  `tests/fixtures/armory_engine/golden.json`, **recorded from the
  pre-extraction app.py** against `tests/fixtures/armory_engine/inputs.py`
  (6 items with details, a 6-recipe chain with one Kinah-only hop and one
  decoy, a 5×5 board with 4 punched cells, 3 Arcana wishlists, 12 seeded
  random boards). A red test here means the move changed behaviour, not that
  the golden is stale.
- `tests/test_armory_engine_qt_free.py` — 12 tests. Each engine module
  imported in a **subprocess** with a `meta_path` finder that makes any
  PySide6/shiboken import raise, plus an `ast` pass for a Qt import hidden in
  a function body. Modules are discovered by glob, so a new one is covered
  automatically.
- `tests/test_armory_engine_packaging.py` — 193 tests, 162 run and 31
  skipped (a moved name app.py no longer references needs no re-import; the
  skip is the assertion that the two halves agree). No moved name is
  redefined at app.py's top level; every moved name app.py still references
  is imported back; the two wrapper methods are still one-`return`
  delegations; `sys.path.insert` runs before the first engine import; and
  both `.spec` files carry the recursive `datas` entry.
- `tests/test_enchant_model.py` — its `armory` fixture is now parametrized
  over **both paths** (`armory_engine.enchant` directly, and app.py's
  namespace), so 123 tests became 246 and the shipping re-export surface is
  tested too.

### Spec changes (§4.1's constraint 1)

One line each, both destinations under `ItemDatabase/`:

- `Aion2 TM.spec`: `('ItemDatabase/armory_engine', 'ItemDatabase/armory_engine')`
- `ItemDatabase/AION2_ItemDatabase.spec`: `('armory_engine', 'ItemDatabase/armory_engine')`

A directory source (copied recursively) rather than a line per module —
unlike `ItemDatabase/data/`, which needs per-file discipline because it also
holds ~278 MB of runtime caches. §4.1's constraint 2 is satisfied by
`sys.path.insert(0, str(Path(__file__).resolve().parent))` near the top of
app.py, before the first engine import, with a `_MEIPASS/ItemDatabase` insert
alongside it for the frozen case.

### Also in this pass

Review G **m7** (Armory `apply_theme` had no `unchanged` early return) is
fixed — per window, comparing the **rendered sheet** rather than the theme
name. A name comparison against `_theme.current()`, as m7 suggests, cannot
work: the host records the new theme in `MainWindow.load_styles` *before*
forwarding the switch, so `_theme.current()` is already the target by the
time `apply_theme` runs and a name guard would skip the real switch too. The
expensive part — `findChildren(QWidget)` + unpolish/polish over thousands of
widgets, paid on every profile load — is now skipped for any window whose
sheet already matches. The return value is "windows now wearing this theme"
(restyled + already current), which keeps `apply_theme(name) >= 3` meaning
what `tests/test_armory_theme.py` asserts it means.

---

## Stage 2 done — 2026-09-19 : recos #1/#2

Les deux features **S** du §3.4, livrées derrière le contrat du §3.3. Rien
d'autre du §3.4 n'est touché : #3/#4/#5 restent ouvertes, pour la raison
donnée plus bas.

### Ce qui a été ajouté

| Module | Contenu |
|---|---|
| `armory_engine/providers.py` | `DiskDetailProvider` (le `DetailProvider` du §3.2 item 2, version disque : lit `data/details/{id}.json`, mémoïse hits **et** miss), `load_json_or_none`, `DataBundle` + `load_data_bundle` (les 3 fichiers catalogue, avec `available`/`reason_key`) |
| `armory_engine/score.py` | `role_weights` (rang → poids, décroissance géométrique), `merge_role_weights`, `display_names`, `normalize_stat_id`, `stat_name_index`, `stat_gap` / `stat_gap_ranked`, `substat_alignment` |
| `armory_engine/recommend.py` | `set_root`, `build_set_index`, `missing_set_pieces`, `next_best_actions` |
| `armory_engine/explain.py` | `Recommendation` gagne `text_key` / `text_kwargs` (additif, avec défauts) |
| `ui/pages/armory_page.py` | carte « Recommendations » (`#armoryRecoCard`, lignes `#armoryRecoItem`, « Why? » dépliable par ligne) |
| `ui/main_window.py` | `_armory_data_dir` / `_armory_engine` / `_armory_recommendations`, poussés par l'unique writer `_set_build_planner_state` |

### Feature #1, telle qu'elle est réellement livrable

Le tableau du §3.4 titre #1 « stat gap vs role target » et donne en exemple
*« tu es 240 Accuracy sous le profil PvE-Angreifer »*. **Cette phrase n'est pas
livrable** : la cible absolue demande un modèle de combat (valeur marginale
d'un point, soft caps, rendements décroissants) que le catalogue ne contient
pas — ce que la dernière ligne du §3.4 dit déjà de l'optimiseur de sous-stats.
La fabriquer reviendrait à fabriquer le modèle.

Ce qui est livré à la place, et qui tient sans modèle :

1. **Couverture par slot.** Pour chaque stat que le profil classe haut :
   combien des slots équipés en fournissent, via l'attribution `by_slot` de
   `compute_stat_totals_detailed` (le §3.1 la nommait « l'actif central » —
   elle l'est). Tri par `poids × (1 − couverture)`. Sur le build de test :
   Critical Hit (0.75 × 3/4 = 0.5625) passe devant Attack (1.0 × 1/4 = 0.25),
   parce qu'Attack est déjà sur 3 pièces sur 4 et que recommander le stat que
   tout le build porte déjà est du bruit.
2. **Alignement des sous-stats.** Part des choix qui tombent dans le top-N du
   profil, plus les slots dont **aucun** choix n'est au profil. Ça compare le
   joueur à son propre classement — donc aucune cible inventée — et c'est
   directement actionnable (le picker de sous-stats est à un clic).

Un `reference` (totals d'un build de comparaison) est accepté et bascule le
calcul sur le seul écart de magnitude légitime : même stat, mêmes unités.
Personne ne le passe encore ; Build Compare est le consommateur naturel.

### Feature #2

`dungeon_sets.json` donne `{tag: {root: {grade, gearscore}}}` mais **pas** les
pièces : elles se retrouvent en re-appliquant à `items_all.json` la règle de
suffixe de `compute_dungeon_sets.py` (`"Abyssal Helm"` → root `"Abyssal"`).
`SET_SLOT_WORDS` est donc un **miroir** de `DUNGEON_SET_SLOT_WORDS`, et la
dérive n'est pas laissée à un commentaire : le test parse le script et compare
les deux listes. La passe 2 du script (préfixe de deux mots pour les armes
« flavor-named » du Crafting) n'est pas reproduite — ces roots sont exclus du
fichier écrit de toute façon, et un root que plus aucun item ne résout ne
produit simplement aucune pièce, ce qui est la bonne dégradation.

Deux détails qui viennent des vraies données : les copies liées/non liées
partagent un nom (l'id le plus bas gagne, sinon la pièce recommandée change
d'un rafraîchissement à l'autre), et un root peut être listé sous plusieurs
tags (le premier alphabétiquement gagne, même raison).

### Un bug attrapé en écrivant les tests

`stat_name_index` construisait `{id brut: nom}` alors que
`compute_stat_totals_detailed` réécrit les ids via `_GEAR_STAT_ID_ALIASES`
(`"Defense"` sur la pièce → `"DefenseBonus"` dans les totals). La jointure
échouait donc **exactement sur les stats pour lesquelles la table d'alias
existe**, et silencieusement : le stat ressortait comme « aucune pièce n'en
fournit ». Corrigé (l'index applique l'alias) et gaté par
`test_the_name_index_uses_the_totals_spelling_not_the_pieces`.

### Dégradation (le chemin nominal ici)

`ItemDatabase/data/` de ce clone ne contient ni `items_all.json` ni un seul
fichier de détail — c'est l'état de tout clone frais. Les quatre chemins :

| Situation | Résultat |
|---|---|
| pas de `items_all.json` | **une** recommandation `armory_reco_needs_data` → la carte affiche « Recommendations need the Armory data pack… » |
| pas de `dungeon_sets.json` | pas de recos de set, le reste tourne |
| pas de provider / aucun détail lisible | **aucune** feature de stat (des totals vides et un build qui ne porte réellement rien donnent les mêmes chiffres et veulent dire l'inverse) ; les recos de set tournent, elles n'ont besoin que des noms |
| données présentes, rien à dire | liste vide → la carte affiche « rien à améliorer » |

### Ce qui n'a pas été fait, et pourquoi

- **Rôle choisi par le joueur.** L'état persisté porte `active_gear_types`
  (donc PvE/PvP est lu) mais **pas** de rôle : c'est une sélection par dialogue
  (`StatPriorityEditorDialog.selected_role`), jamais sauvegardée. Le moteur
  prend `Angreifer` — le seul profil avec un vrai appui guide, les cinq autres
  étant des copies (§2.2) — et le dit dans la phrase. Un sélecteur de rôle sur
  le tableau de bord demanderait d'abord une clé de persistance dans
  `BuildState`, donc une décision de spec, pas une ligne de code.
- **Rôle traduit.** `{role}` voyage dans les `text_kwargs` mais les trois
  phrases l'écrivent en dur (« attacker » / « Angreifer » / « атакующий »),
  puisque la valeur est aujourd'hui constante. Une table de libellés de rôle
  dans `core/translations.py` viendra avec le sélecteur ci-dessus.
- **Animation de la révélation « Why? »** : §4-6 de MASTER interdit un sixième
  site d'animation sans passer par MASTER. Non fait, exprès.
- **Features #3/#4/#5** : inchangées. #3 et #4 demandent un `score_delta` en
  espace de stats, donc le modèle de combat ; #5 demande le croisement
  recettes × `dungeons_all.json`, qui est un travail de données à part entière.

### Tests + gates

- `tests/test_armory_engine_recommend.py` (nouveau, 75 tests) : poids, rangs,
  couverture, alignement, complétude de set, orchestration, les 4 chemins de
  dégradation, et le provider/bundle contre un pack de données temporaire.
  **Aucune valeur enregistrée** — contrairement aux goldens du Stage 1 : ici
  tout est calculé à la main depuis `tests/fixtures/armory_engine/reco_inputs.py`,
  parce qu'une valeur enregistrée ne prouverait que « le code refait ce qu'il
  a fait la première fois ».
- `tests/test_armory_dashboard.py` : + 30 tests (clés dans les 3 langues, clés
  émises par le moteur ⊆ clés traduites, rendu avec/sans données, « Why? »,
  re-rendu après changement de langue, garde de formatage, objectNames, seam
  hôte, grab).
- `tests/test_armory_engine_qt_free.py` : les 3 nouveaux modules sont couverts
  d'office (découverte par glob) ; la liste-garde les nomme.
- Grab : `docs/audit-2026-09-18/shots/aether/armory_dashboard_reco.png` (Abyss,
  carte pleine, une ligne dépliée).
