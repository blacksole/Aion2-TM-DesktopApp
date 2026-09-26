#!/usr/bin/env python
"""Dev tool: render the component gallery of MASTER §3 for every theme.

Builds one small widget holding every component the design system specifies
a rule for (primary/secondary/destructive buttons, pills, a field with a
placeholder, the four badge flavors, a card, a table snippet, an active
sidebar item), applies each theme's generated QSS to it, and ``grab()``s it
to a PNG.  Looking at the six PNGs side by side is the cheapest way to catch
a token that reads wrong before it reaches the app.

**Always offscreen.**  ``QT_QPA_PLATFORM=offscreen`` is forced below,
*before* any Qt import, so this script can never pop a window onto a real
screen — not on a dev desktop, not over a game.  ``QWidget.grab()`` renders
through the raster paint engine and needs no display at all.

    .venv/bin/python scripts/theme_preview.py --out /tmp/theme-preview
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Must precede every Qt import: Qt reads the platform plugin name at the
# moment QGuiApplication is constructed, but the env var is what selects it.
os.environ["QT_QPA_PLATFORM"] = "offscreen"

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import (  # noqa: E402  (after the offscreen pin)
    QApplication,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import fonts  # noqa: E402
from core import theme as theme_module  # noqa: E402
from core.theme import THEMES, build_palette, build_qss  # noqa: E402


def _label(text: str, object_name: str = "") -> QLabel:
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    return label


def _button(text: str, object_name: str, *, checkable: bool = False, checked: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(object_name)
    if checkable:
        button.setCheckable(True)
        button.setChecked(checked)
    return button


def _section(title: str) -> QLabel:
    return _label(title.upper(), "statTitle")


def build_gallery() -> QWidget:
    """One widget carrying every component MASTER §3 has a rule for."""
    root = QWidget()
    root.setObjectName("ContentArea")
    # The application sheet is scoped to `QWidget[aion2="true"]` and its
    # descendants, so that it cannot leak into the Armory's own windows
    # (see ui/styles.template.qss §0).  The gallery stands in for one of
    # the app's own windows, so it carries the same flag.
    root.setProperty("aion2", True)
    root.setFixedWidth(820)
    outer = QHBoxLayout(root)
    outer.setContentsMargins(16, 16, 16, 16)
    outer.setSpacing(16)

    # --- sidebar (active + inactive item) --------------------------------
    sidebar = QFrame()
    sidebar.setObjectName("SidebarWidget")
    sidebar.setFixedWidth(180)
    side_layout = QVBoxLayout(sidebar)
    side_layout.setSpacing(4)
    side_layout.addWidget(_button("ToDo", "sidebarButton", checkable=True, checked=True))
    side_layout.addWidget(_button("Armory", "sidebarButton", checkable=True))
    side_layout.addWidget(_button("Flow Map", "sidebarButton", checkable=True))
    side_layout.addWidget(_button("Settings", "sidebarButton", checkable=True))
    side_layout.addStretch(1)
    outer.addWidget(sidebar)

    body = QVBoxLayout()
    body.setSpacing(12)
    outer.addLayout(body, 1)

    title = _label("Aether Cockpit", "PageTitle")
    body.addWidget(title)

    # --- buttons ---------------------------------------------------------
    body.addWidget(_section("buttons"))
    buttons = QHBoxLayout()
    buttons.addWidget(_button("+ Add Task", "primaryButton"))
    buttons.addWidget(_button("Export", "secondaryButton"))
    buttons.addWidget(_button("Reset Profile", "DeleteDialogDangerBtn"))
    buttons.addWidget(_button("?", "helpButton"))
    buttons.addStretch(1)
    body.addLayout(buttons)

    # --- pills -----------------------------------------------------------
    body.addWidget(_section("pills / tabs"))
    pills = QHBoxLayout()
    active = _button("ToDo", "tabButton")
    active.setProperty("active", "true")
    pills.addWidget(active)
    pills.addWidget(_button("Shopping", "tabButton"))
    pills.addWidget(_button("Priority", "sortButton", checkable=True, checked=True))
    pills.addWidget(_button("Name", "sortButton", checkable=True))
    pills.addWidget(_button("On", "toggleButton", checkable=True))
    pills.addStretch(1)
    body.addLayout(pills)

    # --- field + placeholder --------------------------------------------
    body.addWidget(_section("fields"))
    field_row = QHBoxLayout()
    filled = QLineEdit("Amoran Fortress run")
    field_row.addWidget(filled, 1)
    empty = QLineEdit()
    empty.setPlaceholderText("Task title…")
    field_row.addWidget(empty, 1)
    check = QCheckBox("Appears automatically")
    check.setObjectName("settingsCheckbox")
    check.setChecked(True)
    field_row.addWidget(check)
    body.addLayout(field_row)

    # --- badges ----------------------------------------------------------
    body.addWidget(_section("badges"))
    badges = QHBoxLayout()
    badges.addWidget(_label("LOW", "priorityLow"))
    badges.addWidget(_label("MIDDLE", "priorityMiddle"))
    badges.addWidget(_label("MISSED", "missedBadge"))
    badges.addWidget(_label("DAILY", "scheduleDaily"))
    badges.addWidget(_label("EVENT", "eventBadge"))
    badges.addStretch(1)
    body.addLayout(badges)

    # --- card ------------------------------------------------------------
    body.addWidget(_section("card"))
    card = QFrame()
    card.setObjectName("taskCard")
    card_layout = QHBoxLayout(card)
    card_layout.setContentsMargins(12, 12, 12, 12)
    card_layout.addWidget(_button("○", "checkButton"))
    text_col = QVBoxLayout()
    text_col.addWidget(_label("Clear the Abyss dailies", "taskTitle"))
    text_col.addWidget(_label("Resets in 04:12:38 · 3 of 5 done", "taskDescription"))
    card_layout.addLayout(text_col, 1)
    card_layout.addWidget(_label("HIGH", "priorityHigh"))
    card_layout.addWidget(_button("×", "deleteButton"))
    body.addWidget(card)

    # --- table snippet ---------------------------------------------------
    body.addWidget(_section("table"))
    table = QFrame()
    table.setObjectName("statCard")
    grid = QGridLayout(table)
    grid.setContentsMargins(12, 8, 12, 8)
    for column, header in enumerate(("ITEM", "GRADE", "GEARSCORE")):
        grid.addWidget(_label(header, "statTitle"), 0, column)
    rows = (("Fabled Greatsword", "Epic", "1 284"), ("Abyss Plate", "Legend", "1 102"))
    for row, (name, grade, score) in enumerate(rows, start=1):
        grid.addWidget(_label(name, "taskTitle"), row, 0)
        grid.addWidget(_label(grade, "taskDescription"), row, 1)
        grid.addWidget(_label(score, "StatRowCell"), row, 2)
    body.addWidget(table)

    # --- progress numbers (display face) --------------------------------
    body.addWidget(_section("summary"))
    summary = QHBoxLayout()
    for value, sub, obj in (
        ("12", "DONE", "Done"),
        ("4", "OPEN", "Open"),
        ("1", "MISSED", "Missed"),
        ("17", "TOTAL", "Total"),
    ):
        col = QVBoxLayout()
        col.addWidget(_label(value, f"Progress{obj}Val"))
        col.addWidget(_label(sub, f"Progress{obj}Sub"))
        summary.addLayout(col)
    summary.addStretch(1)
    summary.addWidget(_label("71%", "ProgressPct"))
    body.addLayout(summary)

    body.addStretch(1)
    return root


def render(out_dir: Path) -> list[Path]:
    """Grab the gallery once per theme; return the written PNG paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    loaded = fonts.load_fonts()
    # Same reason as main.py: the sheet must name the families Qt really
    # registered, not the ones the tokens hoped for.
    theme_module.set_font_families(loaded)
    print(f"fonts: {loaded}")

    written: list[Path] = []
    for theme in THEMES:
        # MASTER §4-1: the app applies BOTH the sheet and the palette
        # (main.py / MainWindow.apply_theme).  Grabbing with the sheet alone
        # left every pixel the QSS does not explicitly paint on Fusion's
        # default light grey -- the gallery's own ground came out #efefef,
        # so translucent tokens (`accent.soft` pills) composited over grey
        # and read as washed-out light chips instead of the dark-ground
        # wash the app really draws.  A preview that does not apply the
        # palette is not previewing what ships.
        app.setPalette(build_palette(theme))
        gallery = build_gallery()
        gallery.setStyleSheet(build_qss(theme, asset_path=ROOT.as_posix()))
        gallery.adjustSize()
        app.processEvents()
        pixmap = gallery.grab()
        path = out_dir / f"theme_{theme}.png"
        if not pixmap.save(str(path)):
            raise RuntimeError(f"Could not write {path}")
        written.append(path)
        print(f"{theme:10} {pixmap.width()}x{pixmap.height()}  {path}")
        gallery.deleteLater()
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="directory for the PNGs")
    args = parser.parse_args(argv)
    render(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
