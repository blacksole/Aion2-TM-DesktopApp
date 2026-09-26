# Reply to Voyd-star — the 7 baseline failures he couldn't reproduce

*Drafted 2026-09-25/26 by @koordinator, for tobia to review before posting
as a PR #8 (or general) comment on GitHub.*

---

**Update: 4 of the 7 are already fixed** (commit `259615b`, pushed to
`Tasse/work`) — turned out to be genuine test bugs, not just environment
noise, exposed only when the cross-platform suite runs from Windows:

- `test_linux_honours_xdg_overrides` — `utils/paths.py::_xdg()` used
  `Path(value).is_absolute()`, which is `False` for a POSIX path like
  `/xdg/data` on a Windows host (no drive letter) -- silently treated a
  genuinely absolute XDG override as relative. Fixed with a plain
  `startswith("/")` check; real Linux-host behavior is unchanged.
- `test_play_wav_falls_back_to_cli_player` /
  `test_play_wav_returns_false_when_no_backend_exists` — `play_wav()` reads
  `sys.platform` directly (it's the one function real playback goes
  through, no injectable `platform=`), so on Windows it always takes the
  `winsound` branch before ever reaching the mocked `_play_qt`/CLI path the
  tests set up. Fixed by monkeypatching `_plat` itself in the tests.
- `test_valid_config_path_wins_over_everything` — the fake `config.json`
  was built with raw `%s` string interpolation instead of `json.dumps()`;
  a Windows path's backslashes produced invalid JSON, and
  `_resolve_profile_dir()`'s bare `except Exception: pass` silently
  swallowed the resulting `JSONDecodeError`. Fixed with `json.dumps()`.

The remaining 3 below are not Windows/Linux issues -- kept as originally
diagnosed:

**1 is a fresh-clone assumption that doesn't hold on our dev machine**
- Docstring says it outright: assumes `ItemDatabase/data/` is empty ("what
  every fresh clone looks like"). Ours has 10k+ cached detail files and a
  real `items_all.json` from actually using the app locally, so the
  Recommendations card shows real data instead of the "needs data" copy
  the test expects. Passes on an actually-fresh clone.

**2 look like genuine Qt-teardown/data-shape flakiness, still investigating**
(`tests/test_build_planner_state.py::test_host_pull_without_an_open_planner_returns_the_pushed_dict`,
`tests/test_build_planner_state.py::test_round_trip_preserves_key[daevanion_active]`)
- The `daevanion_active` round-trip fails on a shape mismatch
  (`{'s:31': ['310113']}` appearing where the dummy state only has
  `{'s:qa-board': [1, 2, 3]}` — looks like state bleeding in from another
  test or a stale on-disk fixture, not yet isolated).
- The other throws `RuntimeError: libshiboken: Internal C++ object
  (QStandardItemModel) already deleted` from `ItemDatabase/app.py:22433`
  during `_load_items_chunk` — a background item-loading callback firing
  after its own model was torn down. Haven't pinned down whether it's a
  pre-existing race or a Windows-specific timing difference; didn't want to
  block your PR review on it.

None of the 7 are blockers for anything you touched in #8 — happy to open
separate issues for the last 2 if useful, since those look like real
(if narrow) bugs rather than environment noise.
