from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel)

class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        label = QLabel("Dashboard")
        layout.addWidget(label)