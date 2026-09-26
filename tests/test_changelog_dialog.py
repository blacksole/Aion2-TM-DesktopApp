"""Update History (ChangelogHistoryDialog): every version has a date, and
every rail button looks the same.

tobia, 2026-09-24 (verbatim): "jeder hat ein Datum und der Hotfix Tag ist
immer gleichgross. Die Groesse wie mit dem Datum ist richtig".

What was wrong, measured on the real dialog before the fix:
* 2.0.6 / 2.0.4 were never published as GitHub Releases, and the date came
  ONLY from GitHub -> no date line at all;
* without a date line the button's spare height went to the top row, so the
  title and HOTFIX badge stretched to 38px (21px on 2.0.5);
* 2.0.6 got a HOTFIX badge at all only because its notes contain the
  sentence "Hotfix releases are marked with a badge".
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

import ui.update_dialog as ud  # noqa: E402
from tests.conftest import destroy_window  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# 1. data: CHANGELOG.md is enough for a date; "Hotfix" means the marker line
# ---------------------------------------------------------------------------

def test_every_current_line_version_has_a_date_offline():
    """No GitHub at all (offline): every 2.x entry still carries a date."""
    major = ud.APP_VERSION.split(".")[0]
    entries = [e for e in ud._parse_local_changelog() if e["tag"].split(".")[0] == major]
    assert entries, "CHANGELOG.md has no entries for the current major line"
    missing = [e["tag"] for e in entries if not e["release_date"]]
    # GitHub's publish time still wins where it exists; "Release Date:" is
    # what makes the dialog right offline and for never-published versions.
    assert not missing, f"CHANGELOG.md entries without 'Release Date:': {missing}"


def test_release_date_line_is_taken_out_of_the_notes():
    entries = {e["tag"]: e for e in ud._parse_local_changelog()}
    assert entries["2.0.6"]["release_date"] == "2026-09-17"
    assert "Release Date" not in entries["2.0.6"]["body"]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("**Hotfix**\n\n## Bug Fixes\n- x", True),
        ("Hotfix\n\n- x", True),
        ("- Hotfix releases are marked with a badge.", False),
        ("- fixed the hotfix badge", False),
        ("", False),
    ],
)
def test_hotfix_is_the_marker_line_not_the_word(body, expected):
    assert ud._is_hotfix(body) is expected


def test_the_real_hotfixes_are_205_and_206():
    """2.0.6 is a hotfix (tobia, 2026-09-24) -- by its "**Hotfix**" line,
    not by its notes mentioning the word."""
    entries = {e["tag"]: e for e in ud._parse_local_changelog()}
    assert ud._is_hotfix(entries["2.0.5"]["body"])
    assert ud._is_hotfix(entries["2.0.6"]["body"])
    assert not ud._is_hotfix(entries["2.0.4"]["body"])


# ---------------------------------------------------------------------------
# 2. the rail: same height, same date line, same badge everywhere
# ---------------------------------------------------------------------------

@pytest.fixture
def dialog(qapp, monkeypatch):
    """The real dialog, offline, with GitHub knowing only SOME versions --
    exactly the situation that broke 2.0.6 / 2.0.4."""
    from core import theme

    theme.apply(qapp, "Abyss")
    published = [
        {"tag_name": "v2.0.8", "published_at": "2026-09-22T16:39:22Z"},
        {"tag_name": "v2.0.5", "published_at": "2026-09-14T16:35:09Z"},
    ]

    class _Resp:
        def read(self):
            return json.dumps(published).encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(ud.urllib.request, "urlopen", lambda *a, **k: _Resp())
    monkeypatch.setattr(ud._ChangelogFetcher, "start", lambda self: self.run())

    host = QWidget()
    host.setProperty("aion2", True)
    dlg = ud.ChangelogHistoryDialog(host, language="en")
    dlg.resize(842, 1100)
    dlg.show()
    for _ in range(10):
        qapp.processEvents()
    yield dlg
    # destroy_window() (not just deleteLater()+one processEvents()) pumps
    # Qt's DeferredDelete queue until the tree is actually gone -- without
    # it this fixture leaked ~416 live widgets across the suite (PR #8
    # review, Voyd-star, 2026-09-25: budget is 150). host is a plain
    # QWidget, not a MainWindow, so give destroy_window() a shape it
    # tolerates: no HOST_WINDOW_ATTRIBUTES, no .close() of its own needed.
    dlg.close()
    destroy_window(host)


def _rail(dlg) -> dict[str, QPushButton]:
    out = {}
    for btn in dlg.findChildren(QPushButton):
        if btn.objectName() != "changelogVersionBtn":
            continue
        title = next(lbl for lbl in btn.findChildren(QLabel)
                     if lbl.objectName() == "changelogVersionBtnTitle")
        out[title.text()] = btn
    return out


def _child(btn: QPushButton, name: str) -> QLabel:
    return next(lbl for lbl in btn.findChildren(QLabel) if lbl.objectName() == name)


def test_the_two_unpublished_versions_now_show_a_date(dialog):
    rail = _rail(dialog)
    assert _child(rail["v2.0.6"], "changelogVersionBtnDate").text() == "September 17, 2026"
    assert _child(rail["v2.0.4"], "changelogVersionBtnDate").text() == "September 14, 2026"


def test_every_rail_button_is_the_same_height(dialog):
    heights = {tag: btn.height() for tag, btn in _rail(dialog).items()}
    assert len(set(heights.values())) == 1, heights


def test_every_date_line_sits_at_the_same_place(dialog):
    geos = {
        tag: (_child(btn, "changelogVersionBtnDate").y(), _child(btn, "changelogVersionBtnDate").height())
        for tag, btn in _rail(dialog).items()
    }
    assert len(set(geos.values())) == 1, geos


def test_the_hotfix_badge_is_one_size_on_every_hotfix(dialog):
    rail = _rail(dialog)
    badges = {tag: _child(btn, "changelogHotfixBadge") for tag, btn in rail.items()}
    visible = sorted(tag for tag, badge in badges.items() if badge.isVisible())
    assert visible == ["v2.0.5", "v2.0.6"]
    # Hidden badges keep their size, so the row is identical in every
    # button -- and nothing is stretched (was 38px / 21px before).
    sizes = {badge.size().toTuple() for badge in badges.values()}
    assert len(sizes) == 1, sizes
    assert badges["v2.0.5"].height() <= badges["v2.0.5"].sizeHint().height()
