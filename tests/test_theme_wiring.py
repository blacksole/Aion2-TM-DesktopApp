"""The token system as the RUNNING app uses it (MASTER §4-1/§4-2, §3, §1).

tests/test_theme.py pins the token table; this file pins the plumbing that
was rebuilt on 2026-09-18:

  * the stylesheet is rendered from the template onto the **QApplication**,
    and a theme switch re-renders it (it used to be one hand-pushed copy per
    top-level window, plus ~100 ``QWidget[theme="…"]`` blocks that a widget
    could silently miss -- the 2026-09-08 "Templates buttons stay cyan on
    Inferno" bug);
  * the Fusion fallback palette follows the theme too;
  * the overlay's slider fades only the section BACKDROPS, never the text;
  * "Reduce animations" persists in the profile and reaches ui.motion;
  * the PyInstaller spec ships the template and the fonts.

Seams (KEEP STABLE):
  * ``MainWindow._resolve_profile_dir`` / ``_save_app_config`` -- patched so
    no test touches the repo's profiles/ or config.json.
  * ``MainWindow.load_styles()`` / ``apply_theme(name)`` /
    ``set_reduce_motion(enabled, save=True)`` / ``reduce_motion``.
  * ``core.theme.set_current`` / ``current`` / ``build_palette``.
  * ``ui.overlay.overlay_window.set_backdrop_alpha`` / ``backdrop_color``.
"""

import re
import shutil
from pathlib import Path

import pytest

from tests.conftest import destroy_window
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QLabel

from core import theme
from core.translations import tr
from ui import motion

FIXTURE_PROFILE = Path(__file__).resolve().parent / "fixtures" / "reset_profile.json"
SPEC = Path(__file__).resolve().parent.parent / "Aion2 TM.spec"


@pytest.fixture(scope="module")
def win(qapp, tmp_path_factory):
    """One real, offscreen MainWindow on a throwaway profile directory."""
    import ui.main_window as mw

    profile_dir = tmp_path_factory.mktemp("theme_profiles")
    shutil.copy2(FIXTURE_PROFILE, profile_dir / "QaProfile.json")

    patcher = pytest.MonkeyPatch()
    patcher.setattr(mw.MainWindow, "_resolve_profile_dir", lambda self: profile_dir)
    patcher.setattr(mw.MainWindow, "_save_app_config", lambda self: None)

    window = mw.MainWindow()
    window.countdown_timer.stop()
    yield window
    destroy_window(window)
    patcher.undo()


@pytest.fixture(autouse=True)
def _back_to_abyss(win):
    """Each test starts on Abyss: the stylesheet is process-wide.

    Only on the way IN, deliberately.  A theme switch costs one app-wide
    ``setStyleSheet`` + ``setPalette`` + a repolish of every widget of every
    open window -- and by the time this module runs, four other test modules
    are each holding their own MainWindow alive in the same QApplication, so
    a switch is ~5x what it costs in the app. Reverting on the way out as
    well doubled that for nothing: ``apply_theme`` is a no-op when the theme
    has not moved, so the next test's entry does the revert when (and only
    when) a revert is actually needed.
    """
    win.apply_theme("abyss")
    yield
    motion.set_reduced_motion(False)


# ---------------------------------------------------------------------------
# MASTER §4-1: one stylesheet, on the application
# ---------------------------------------------------------------------------


def test_the_stylesheet_lives_on_the_application(win):
    sheet = QApplication.instance().styleSheet()
    assert len(sheet) > 5000, "the app has no rendered stylesheet"
    assert "{{" not in sheet, "an unsubstituted placeholder shipped"
    assert "ASSET_PATH" not in sheet


def test_no_window_carries_its_own_copy_of_the_sheet(win):
    """The three hand-pushed copies (MainWindow, Overlay, Flow Map) are the
    thing QApplication.setStyleSheet replaced; a copy coming back means two
    sources of truth for one window again."""
    assert win.styleSheet() == ""
    assert win.overlay.styleSheet() == ""
    if win.flow_map_window is not None:
        assert win.flow_map_window.styleSheet() == ""


def test_apply_theme_re_renders_the_app_stylesheet_and_palette(win):
    """One test over every theme rather than two parametrized ones: each
    switch is an app-wide restyle (see _back_to_abyss), and this way the
    module pays for six of them instead of twenty.

    Abyss is in the loop now, and ``HighlightedText`` is asserted here, so
    that this single pass carries the per-theme PALETTE half of what
    ``test_a_profile_theme_reaches_the_palette_at_startup`` used to check by
    building a fresh MainWindow per theme (three window builds inside a
    module that already holds one).  That test keeps the startup PATH; the
    values every theme installs are these.
    """
    for name in sorted(theme.THEMES):
        win.apply_theme(name)

        sheet = QApplication.instance().styleSheet()
        accent = theme.THEMES[name].accent
        assert accent in sheet, f"{name}'s accent {accent} is not in the rendered sheet"
        if name != "abyss":
            assert theme.ABYSS.accent not in sheet, f"{name}: Abyss's accent survived the switch"

        palette = QApplication.instance().palette()
        assert palette.color(QPalette.Highlight) == theme.qcolor(name, "accent"), name
        assert palette.color(QPalette.Base) == theme.qcolor(name, "bg.input"), name
        assert palette.color(QPalette.HighlightedText) == theme.qcolor(name, "fg.on_accent"), name


def test_apply_theme_publishes_the_current_theme_for_painters(win):
    """MASTER §4-3: a painter reads core.theme.current() instead of being
    handed the theme name through a constructor."""
    win.apply_theme("void")
    assert theme.current() == "void"
    assert theme.current_tokens() is theme.THEMES["void"]


def test_the_theme_property_is_gone(win):
    """Nothing selects on it any more; leaving it set would invite a new
    `QWidget[theme="…"]` rule and the duplication MASTER §4-2 removed."""
    assert win.property("theme") in (None, "")
    assert win.background.property("theme") in (None, "")
    sheet = re.sub(r"/\*.*?\*/", "", QApplication.instance().styleSheet(), flags=re.S)
    assert "[theme=" not in sheet


def test_load_styles_is_idempotent_and_cheap(win):
    """apply_theme runs on every profile load, usually for the same theme."""
    first = win.load_styles()
    second = win.load_styles()
    assert first == second == QApplication.instance().styleSheet()


def test_a_dialog_created_after_the_switch_still_gets_the_new_theme(win):
    """The 2026-09-08 bug: a QDialog(parent=self) did not descend from the
    widget that carried the theme property, so it kept the old accent."""
    from ui.widgets.template_dialog import TemplateDialog

    win.apply_theme("inferno")
    dialog = TemplateDialog([], [], parent=win, language="en", tr_func=tr)
    try:
        # A widget inherits the app sheet; what it must NOT have is a sheet
        # of its own pinning it to another theme.
        assert dialog.styleSheet() == ""
        assert theme.THEMES["inferno"].accent in QApplication.instance().styleSheet()
    finally:
        dialog.deleteLater()


# ---------------------------------------------------------------------------
# MASTER §3: overlay backdrop alpha, text stays opaque
# ---------------------------------------------------------------------------


def test_the_slider_no_longer_fades_the_whole_window(win):
    """setWindowOpacity() faded the text too, which made the HUD unreadable
    at the low end of its own slider."""
    overlay = win.overlay
    overlay._opacity_slider.setValue(20)
    assert overlay.windowOpacity() == pytest.approx(1.0)


def test_the_slider_drives_the_backdrop_alpha(win):
    from ui.overlay import overlay_window

    for percent in (20, 50, 90, 100):
        win.overlay._opacity_slider.setValue(percent)
        assert overlay_window.backdrop_alpha() == pytest.approx(percent / 100.0)
        assert overlay_window.backdrop_color("bg.window").alphaF() == pytest.approx(
            percent / 100.0, abs=0.01
        )


def test_every_overlay_label_stays_fully_opaque_at_the_lowest_setting(win):
    """The whole point of the change: at 20 % the backdrop is a wash and the
    text is still black-on-white crisp."""
    win.overlay._opacity_slider.setValue(20)
    labels = win.overlay.findChildren(QLabel)
    assert labels, "the overlay rendered no labels at all"
    for label in labels:
        assert label.windowOpacity() == pytest.approx(1.0)
        effect = label.graphicsEffect()
        assert effect is None or effect.opacity() == pytest.approx(1.0), label.objectName()


def test_the_row_identity_bar_stays_opaque_too(win):
    """A row's 3 px colour bar is what tells the priority/status apart."""
    from ui.overlay import overlay_window

    overlay_window.set_backdrop_alpha(0.2)
    assert overlay_window.priority_color("high").alphaF() == pytest.approx(1.0)
    assert overlay_window.status_color("completed").alphaF() == pytest.approx(1.0)


def test_the_backdrop_follows_the_theme(win):
    from ui.overlay import overlay_window

    overlay_window.set_backdrop_alpha(1.0)
    win.apply_theme("emerald")
    assert overlay_window.backdrop_color("bg.window").name() == theme.qcolor("emerald", "bg.window").name()


def test_the_overlay_empty_row_is_translated(win):
    """`empty_overlay_tasks` was a hardcoded "No active tasks ✓"."""
    for language in ("en", "de", "ru"):
        win.language = language
        win.overlay.refresh()
        texts = [label.text() for label in win.overlay.findChildren(QLabel)]
        expected = tr(language, "empty_overlay_tasks")
        if any(text == expected for text in texts):
            break
    else:
        pytest.skip("fixture profile has open tasks in every language, so no empty row")
    win.language = "en"


def test_the_overlay_empty_row_uses_the_shared_hint_style(win):
    row = win.overlay._empty_row("nothing here")
    assert row.objectName() == "OverlayEmpty"
    assert row.property("class") == "emptyStateHint"


# ---------------------------------------------------------------------------
# MASTER §1: motion.reduced
# ---------------------------------------------------------------------------


def test_reduce_motion_reaches_ui_motion(win):
    win.set_reduce_motion(True, save=False)
    assert motion.reduced_motion() is True
    assert [motion.duration(kind) for kind in ("fast", "base", "slow")] == [0, 0, 0]

    win.set_reduce_motion(False, save=False)
    assert motion.duration("base") == theme.ABYSS.motion_base


def test_reduce_motion_round_trips_through_the_profile(win):
    win.set_reduce_motion(True, save=False)
    win.save_profile(explicit=True, silent=True)

    win.set_reduce_motion(False, save=False)
    assert motion.reduced_motion() is False

    win.load_profile(win.profile_dir / f"{win.profile_name}.json")
    assert win.reduce_motion is True
    assert motion.reduced_motion() is True

    # Leave the fixture profile as it was found.
    win.set_reduce_motion(False, save=False)
    win.save_profile(explicit=True, silent=True)


def test_reduce_motion_is_in_the_saved_settings_block(win, monkeypatch):
    import core.persistence as persistence

    captured = []
    monkeypatch.setattr(persistence, "atomic_write_json", lambda path, data, **kw: captured.append(data))

    win.set_reduce_motion(True, save=False)
    win.save_profile(explicit=True, silent=True)

    assert captured, "save_profile wrote nothing"
    assert captured[-1]["settings"]["reduce_motion"] is True
    win.set_reduce_motion(False, save=False)


def test_the_settings_checkbox_is_wired_both_ways(win):
    check = win.settings_page.reduce_motion_check
    # Start from a known UNCHECKED state: setChecked() to the value the box
    # already holds emits nothing, so a leftover state from an earlier test
    # would make this pass for the wrong reason.
    check.setChecked(False)
    assert win.reduce_motion is False

    check.setChecked(True)
    assert win.reduce_motion is True
    assert motion.reduced_motion() is True

    check.setChecked(False)
    assert win.reduce_motion is False


def test_the_settings_checkbox_is_translated(win):
    for language in ("en", "de", "ru"):
        win.settings_page.update_language(language, tr)
        assert win.settings_page.reduce_motion_check.text() == tr(language, "reduce_motion")
        assert win.settings_page.reduce_motion_hint.text() == tr(language, "reduce_motion_hint")
    win.settings_page.update_language("en", tr)


def test_sync_settings_page_shows_the_stored_value_without_emitting(win):
    """set_values() is a read-back; emitting from it would save the profile
    in the middle of loading it."""
    win.reduce_motion = True
    win.sync_settings_page()
    assert win.settings_page.reduce_motion_check.isChecked() is True

    win.reduce_motion = False
    win.sync_settings_page()
    assert win.settings_page.reduce_motion_check.isChecked() is False


def test_exactly_three_places_animate():
    """MASTER §4-6: "Aucune autre animation ailleurs." A fourth call site is
    a design decision, not a detail -- it has to go through MASTER first."""
    ui_dir = Path(__file__).resolve().parent.parent / "ui"
    call_sites = []
    for path in sorted(ui_dir.rglob("*.py")):
        if "__pycache__" in path.parts or path.name == "motion.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "motion.fade_in(" in stripped or "motion.fade_out(" in stripped or "motion.slide_hint(" in stripped:
                call_sites.append(f"{path.relative_to(ui_dir)}:{number}")

    # toast show, toast hide, card delete, card undo-restore, page switch.
    assert len(call_sites) == 5, f"unexpected animation call sites: {call_sites}"


# ---------------------------------------------------------------------------
# Packaging
# ---------------------------------------------------------------------------


def test_the_spec_ships_the_template_not_the_deleted_sheet():
    spec = SPEC.read_text(encoding="utf-8")
    assert "('ui/styles.template.qss', 'ui')" in spec
    assert "('ui/styles.qss', 'ui')" not in spec, "the spec still bundles the deleted stylesheet"


def test_the_spec_ships_the_bundled_fonts():
    """MASTER §1 makes the three OFL faces part of the design system: a
    build without them silently falls back on every machine."""
    spec = SPEC.read_text(encoding="utf-8")
    assert "('assets/fonts', 'assets/fonts')" in spec


def test_the_legacy_stylesheet_is_not_in_the_tree():
    assert not (Path(__file__).resolve().parent.parent / "ui" / "styles.qss").exists()


# ---------------------------------------------------------------------------
# F-1: the palette must follow the theme on the path that actually runs
# ---------------------------------------------------------------------------


def test_a_profile_theme_reaches_the_palette_at_startup(qapp, tmp_path_factory):
    """The regression the review found, tested through the real caller.

    ``__init__`` and ``load_profile`` both assign ``current_theme`` *before*
    calling ``apply_theme(self.current_theme)``, so a "did the theme move?"
    guard comparing against ``current_theme`` was always True — the sheet
    followed the profile, the palette stayed on whatever ``main.py`` set.
    Building a window from a profile is the only way to see that; the
    theme-picker path (``apply_theme(other)``) hides it.

    One theme, not three.  This was parametrized over inferno/emerald/void,
    i.e. three MainWindows built from scratch inside one module that already
    holds one — and what it proves (that the startup path applies the
    palette at all, instead of leaving it on main.py's) is a property of
    ``_APPLIED_PALETTE_THEME``, not of a colour: the *values* for the other
    five themes are asserted on the shared window by
    ``test_apply_theme_re_renders_the_app_stylesheet_and_palette`` above and
    by ``test_every_theme_reaches_the_palette_through_apply_theme`` below,
    and the guard itself by
    ``test_apply_theme_tracks_what_it_applied_not_what_was_asked``.
    """
    import json

    import ui.main_window as mw
    from PySide6.QtGui import QPalette

    name = "inferno"
    profile_dir = tmp_path_factory.mktemp(f"palette_{name}")
    data = json.loads(FIXTURE_PROFILE.read_text(encoding="utf-8"))
    data["theme"] = name
    (profile_dir / "QaProfile.json").write_text(json.dumps(data), encoding="utf-8")

    patcher = pytest.MonkeyPatch()
    patcher.setattr(mw.MainWindow, "_resolve_profile_dir", lambda self: profile_dir)
    patcher.setattr(mw.MainWindow, "_save_app_config", lambda self: None)
    # A fresh process-wide "nothing applied yet", so this really is the
    # first application and not a no-op behind an earlier test's state.
    patcher.setattr(mw, "_APPLIED_PALETTE_THEME", None)
    patcher.setattr(mw, "_APPLIED_STYLE_KEY", None)

    window = mw.MainWindow()
    window.countdown_timer.stop()
    try:
        assert window.current_theme == name
        palette = QApplication.instance().palette()
        assert palette.color(QPalette.Highlight) == theme.qcolor(name, "accent"), (
            f"{name}: palette Highlight is {palette.color(QPalette.Highlight).name()}"
        )
        assert palette.color(QPalette.Base) == theme.qcolor(name, "bg.input")
        assert palette.color(QPalette.HighlightedText) == theme.qcolor(name, "fg.on_accent")
        # ... and the sheet agrees with it.
        assert theme.THEMES[name].accent in QApplication.instance().styleSheet()
    finally:
        destroy_window(window)
        patcher.undo()
        # ``patcher.undo()`` puts the two module globals back to what they
        # were BEFORE this test -- but the QApplication's palette and sheet
        # are now this test's theme, so the restored guard describes a state
        # that no longer exists and the next ``apply_theme`` for that theme
        # would be a no-op over a palette that never moved.  That is the F-1
        # bug itself, reproduced inside the harness.  Clearing them says the
        # honest thing: nothing is known to be applied.
        mw._APPLIED_PALETTE_THEME = None
        mw._APPLIED_STYLE_KEY = None


def test_apply_theme_tracks_what_it_applied_not_what_was_asked(win):
    """The guard's subject, pinned directly."""
    import ui.main_window as mw

    win.apply_theme("void")
    assert mw._APPLIED_PALETTE_THEME == "void"
    # Pre-assigning current_theme (what __init__/load_profile do) must not
    # make the next apply_theme a no-op.
    win.current_theme = "frostbite"
    win.apply_theme("frostbite")
    assert mw._APPLIED_PALETTE_THEME == "frostbite"
    assert QApplication.instance().palette().color(QPalette.Highlight) == theme.qcolor(
        "frostbite", "accent"
    )
