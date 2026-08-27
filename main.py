import sys
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.app_logger import get_logger
from ui.main_window import MainWindow

logger = get_logger("main")
logger.info("=== App starting (frozen=%s) ===", getattr(sys, "frozen", False))

app = QApplication(sys.argv)
# Fusion is a pure-software Qt style that fully honors QSS custom
# subcontrols -- the native Windows style only partially does, which is
# why a QComboBox's custom ::down-arrow image can render doubled/wrong and
# its ::drop-down click region can end up misaligned with what's actually
# drawn (real bug reported in the Item Database's Grade/Category/Class
# filters: arrow visible, but clicking opened nothing).
app.setStyle("Fusion")
if getattr(sys, "frozen", False):
    _base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    _base = Path(__file__).resolve().parent
app_icon = _base / "assets" / "icons" / "aion2_tm_icon.ico"
app.setWindowIcon(QIcon(str(app_icon)))

window = MainWindow()
window.show()

sys.exit(app.exec())