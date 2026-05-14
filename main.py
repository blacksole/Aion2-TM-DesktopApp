import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from services.auth_service import AuthManager
from core.app_config import AUTH_REQUIRED
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow


app = QApplication(sys.argv)

auth = AuthManager()

if AUTH_REQUIRED:
    login = LoginDialog()

    if login.exec() != LoginDialog.Accepted:
        sys.exit(0)

print("Starte Auth-Check...")

if not auth.validate_access():
    QMessageBox.critical(
        None,
        "Access denied",
        "You are not authorized to use this application."
    )
    sys.exit(1)

print("Auth erfolgreich")

window = MainWindow(auth_manager=auth)
window.show()

sys.exit(app.exec())