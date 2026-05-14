from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton
)


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Login")
        self.setFixedSize(420, 260)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("Aion2 Task Manager")
        title.setObjectName("loginTitle")

        info = QLabel(
            "Bitte melde dich später mit Discord an,\n"
            "um Zugriff auf die App zu erhalten."
        )
        info.setObjectName("loginInfo")

        self.login_btn = QPushButton("Login with Discord")
        self.login_btn.setObjectName("primaryButton")
        self.login_btn.setMinimumHeight(42)
        self.login_btn.clicked.connect(self.accept)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(info)
        layout.addWidget(self.login_btn)
        layout.addStretch()