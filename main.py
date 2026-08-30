import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from core.app_logger import get_logger
from ui.main_window import MainWindow

logger = get_logger("main")
logger.info("=== App starting (frozen=%s) ===", getattr(sys, "frozen", False))


def _dark_palette() -> QPalette:
    """App-wide fallback palette (User-reported, 2026-08-29: on a system
    with Windows set to dark mode, several screens showed black text on a
    dark background, or plain white boxes where a list/panel should be
    dark) -- without this, Qt/Fusion falls back to the OS's OWN palette
    for any widget/sub-control our QSS doesn't explicitly cover, and on
    Windows that palette now auto-syncs to the system dark/light setting.
    Every one of the app's 6 named themes (Abyss/Inferno/Emerald/
    Frostbite/Obsidian/Void) is dark, so a single dark baseline here,
    layered under the per-theme QSS, keeps every unstyled corner legible
    regardless of the OS's own light/dark setting -- the QSS already
    layered on top (see ui/styles.qss, apply_theme()) still fully
    controls the actual per-theme look; this only replaces what Fusion
    would otherwise pull from Windows."""
    palette = QPalette()
    window = QColor("#0f172a")
    base = QColor("#0b1120")
    alt_base = QColor("#1f2937")
    text = QColor("#e5e7eb")
    disabled_text = QColor("#64748b")
    accent = QColor("#22d3ee")

    palette.setColor(QPalette.Window, window)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, base)
    palette.setColor(QPalette.AlternateBase, alt_base)
    palette.setColor(QPalette.ToolTipBase, alt_base)
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, alt_base)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.BrightText, QColor("#f87171"))
    palette.setColor(QPalette.Link, accent)
    palette.setColor(QPalette.Highlight, accent)
    palette.setColor(QPalette.HighlightedText, window)
    palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.Text, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_text)
    return palette


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
app.setStyle("Fusion")
app.setPalette(_dark_palette())
if getattr(sys, "frozen", False):
    _base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    _base = Path(__file__).resolve().parent
app_icon = _base / "assets" / "icons" / "aion2_tm_icon.ico"
app.setWindowIcon(QIcon(str(app_icon)))

window = MainWindow()
window.show()

sys.exit(app.exec())