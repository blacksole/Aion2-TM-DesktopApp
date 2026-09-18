"""core/fonts.py — the bundled OFL faces register, and never crash headless."""

import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from core import fonts

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def app():
    """A real QApplication: QFontDatabase is unusable (and fatal) without one."""
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_font_files_are_present_and_within_budget():
    files = sorted(fonts.FONT_DIR.glob("*.ttf"))
    assert files, f"no bundled fonts in {fonts.FONT_DIR}"
    total = sum(path.stat().st_size for path in files)
    assert total < 2 * 1024 * 1024, f"font payload {total} bytes exceeds the 2 MB budget"


def test_every_declared_file_exists():
    missing = [
        filename
        for _role, (_family, filenames, _fallback) in fonts.FONT_SPECS.items()
        for filename in filenames
        if not (fonts.FONT_DIR / filename).is_file()
    ]
    assert not missing, f"declared but not shipped: {missing}"


def test_licenses_are_shipped():
    """OFL 1.1 requires the license to travel with the fonts."""
    licenses = sorted(path.name for path in fonts.FONT_DIR.glob("OFL*.txt"))
    assert len(licenses) == 3, licenses
    for name in licenses:
        assert "SIL OPEN FONT LICENSE" in (fonts.FONT_DIR / name).read_text(encoding="utf-8").upper()


def test_load_fonts_returns_the_three_roles(app):
    loaded = fonts.load_fonts(force=True)
    assert set(loaded) == {"display", "body", "mono"}
    assert all(isinstance(value, str) and value for value in loaded.values())


def test_load_fonts_registers_the_bundled_families(app):
    loaded = fonts.load_fonts(force=True)
    assert loaded["body"] == "Barlow"
    assert loaded["display"] == "Barlow Condensed"
    assert loaded["mono"] == "JetBrains Mono"


def test_load_fonts_is_cached(app):
    first = fonts.load_fonts(force=True)
    assert fonts.load_fonts() == first


def test_family_helper(app):
    assert fonts.family("mono") == fonts.load_fonts()["mono"]
    with pytest.raises(KeyError):
        fonts.family("handwriting")


def test_fallbacks_are_used_when_a_family_cannot_load(app, monkeypatch, caplog):
    monkeypatch.setattr(fonts.QFontDatabase, "addApplicationFont", staticmethod(lambda _path: -1))
    with caplog.at_level("WARNING"):
        loaded = fonts.load_fonts(force=True)
    assert loaded == {role: spec[2] for role, spec in fonts.FONT_SPECS.items()}
    fonts.load_fonts(force=True)  # restore the real families for later tests


def test_import_and_call_without_a_qapplication_does_not_raise():
    """Verified the hard way: QFontDatabase segfaults with no QGuiApplication.

    Run in a child process because this test session necessarily has an app.
    """
    code = (
        "import core.fonts as f;"
        "d = f.load_fonts();"
        "assert set(d) == {'display', 'body', 'mono'}, d;"
        "assert all(d.values()), d;"
        "print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        env={"PATH": "/usr/bin:/bin", "QT_QPA_PLATFORM": "offscreen", "HOME": str(ROOT)},
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "ok" in result.stdout
