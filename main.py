import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from core import theme
from core.app_logger import get_logger
from core.fonts import load_fonts
from ui.main_window import MainWindow


def main() -> int:
    """Start the application. Returns the Qt exit code.

    Everything below used to run at import time, which made `import main`
    (and therefore `python -m main`, any test, any packaging tool that
    inspects the module) build a QApplication and pop a window open as a
    side effect.
    """
    logger = get_logger("main")
    logger.info("=== App starting (frozen=%s) ===", getattr(sys, "frozen", False))

    # Multi-monitor setups with mixed per-monitor scaling (e.g. 100% + 150%)
    # are a known Qt/Windows trigger for Qt.Popup windows self-closing the
    # instant they're shown (User-reported, 2026-08-29: EQ-Priority item
    # picker -- correct geometry/isActiveWindow=True in the log, then
    # closeEvent fires in the very same tick, on a multi-monitor setup with
    # mixed scaling, confirmed by the user). PassThrough keeps each monitor's
    # own scale factor exact instead of rounding it, which is what Qt's docs
    # call out as the fix for exactly this class of cross-monitor geometry/
    # activation glitch. Must be set before QApplication() is constructed.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    # Fusion is a pure-software Qt style that fully honors QSS custom
    # subcontrols -- the native Windows style only partially does, which is
    # why a QComboBox's custom ::down-arrow image can render doubled/wrong and
    # its ::drop-down click region can end up misaligned with what's actually
    # drawn (real bug reported in the Item Database's Grade/Category/Class
    # filters: arrow visible, but clicking opened nothing).
    # A stable window class / Wayland app-id: without it a window manager sees
    # "python3" under Wayland and "main.py" under XWayland (measured on
    # Hyprland), so no single windowrule can match the app -- which the
    # overlay's documented Hyprland rule needs (see README, "Run on Linux").
    app.setApplicationName("Aion2 TM")
    app.setDesktopFileName("aion2-tm")
    app.setStyle("Fusion")
    # Register the bundled OFL faces BEFORE any stylesheet names them:
    # QSS resolves font-family at parse time, so a face registered later is
    # simply not found and every rule silently falls back (MASTER §1).
    load_fonts()
    # Fallback palette for everything the QSS does not explicitly cover
    # (User-reported, 2026-08-29: black-on-dark text and white list boxes
    # when the OS itself was in dark mode -- Fusion pulls those from the
    # SYSTEM palette otherwise). Built from the tokens now, and rebuilt per
    # theme by MainWindow.apply_theme(); this call is only the baseline that
    # covers the window's own construction, before the profile is read.
    app.setPalette(theme.build_palette(theme.DEFAULT_THEME))
    if getattr(sys, "frozen", False):
        _base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        _base = Path(__file__).resolve().parent
    app_icon = _base / "assets" / "icons" / "aion2_tm_icon.ico"
    app.setWindowIcon(QIcon(str(app_icon)))

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
