import sys
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


app = QApplication(sys.argv)
if getattr(sys, "frozen", False):
    _base = Path(sys.executable).parent
else:
    _base = Path(__file__).resolve().parent
app_icon = _base / "assets" / "icons" / "aion2_tm_icon.ico"
app.setWindowIcon(QIcon(str(app_icon)))

window = MainWindow()
window.show()

sys.exit(app.exec())
