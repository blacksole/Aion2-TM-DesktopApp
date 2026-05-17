from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit
)
from PySide6.QtCore import Signal


class ProfilePage(QWidget):
    save_requested = Signal()
    load_requested = Signal()
    reset_requested = Signal()
    profile_name_changed = Signal(str)

    def __init__(self):
        super().__init__()

        self.language = "en"
        self.tr_func = None

        self.profile_name = "Default"
        self.edit_mode = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.title_label = QLabel("Profile")
        self.title_label.setObjectName("mainTitle")

        self.subtitle_label = QLabel("Manage and save profiles")
        self.subtitle_label.setObjectName("subtitle")

        self.profile_label = QLabel('Aktuelles Profil: "Default"')
        self.profile_label.setObjectName("subtitle")

        self.profile_input = QLineEdit()
        self.profile_input.setObjectName("profileInput")
        self.profile_input.setText(self.profile_name)
        self.profile_input.setVisible(False)

        self.profile_edit_btn = QPushButton("✎")
        self.profile_edit_btn.setObjectName("smallIconButton")
        self.profile_edit_btn.setFixedSize(34, 34)
        self.profile_edit_btn.clicked.connect(self.toggle_profile_edit)

        profile_row = QHBoxLayout()
        profile_row.addWidget(self.profile_label)
        profile_row.addWidget(self.profile_input)
        profile_row.addWidget(self.profile_edit_btn)
        profile_row.addStretch()

        button_row = QHBoxLayout()

        self.save_profile_btn = QPushButton("Save Profile")
        self.save_profile_btn.setObjectName("tabButton")

        self.load_profile_btn = QPushButton("Load Profile ▾")
        self.load_profile_btn.setObjectName("tabButton")

        self.reset_profile_btn = QPushButton("Reset Profile")
        self.reset_profile_btn.setObjectName("tabButton")

        self.save_profile_btn.clicked.connect(self.save_requested.emit)
        self.load_profile_btn.clicked.connect(self.load_requested.emit)
        self.reset_profile_btn.clicked.connect(self.reset_requested.emit)

        button_row.addWidget(self.save_profile_btn)
        button_row.addWidget(self.load_profile_btn)
        button_row.addWidget(self.reset_profile_btn)
        button_row.addStretch()

        layout.addWidget(self.title_label)
        layout.addLayout(profile_row)
        layout.addLayout(button_row)
        layout.addStretch()

    def set_profile_name(self, profile_name: str):
        self.profile_name = profile_name

        if self.tr_func:
            self.profile_label.setText(
                self.tr_func(self.language, "current_profile", name=profile_name)
            )
        else:
            self.profile_label.setText(f'Aktuelles Profil: "{profile_name}"')

        self.profile_input.setText(profile_name)

    def get_profile_name(self):
        return self.profile_input.text().strip()

    def toggle_profile_edit(self):
        if not self.edit_mode:
            self.edit_mode = True
            self.profile_input.setText(self.profile_name)
            self.profile_label.setVisible(False)
            self.profile_input.setVisible(True)
            self.profile_edit_btn.setText("💾")
            self.profile_input.setFocus()
            self.profile_input.selectAll()
            return

        new_name = self.profile_input.text().strip()

        if new_name:
            self.profile_name = new_name
            self.profile_name_changed.emit(new_name)

        self.profile_label.setText(f'Aktuelles Profil: "{self.profile_name}"')
        self.edit_mode = False
        self.profile_input.setVisible(False)
        self.profile_label.setVisible(True)
        self.profile_edit_btn.setText("✎")

    def update_language(self, language: str, tr_func):
        self.language = language
        self.tr_func = tr_func

        self.profile_label.setText(
            tr_func(language, "current_profile", name=self.profile_name)
        )

        self.save_profile_btn.setText(
            tr_func(language, "save_profile")
        )

        self.load_profile_btn.setText(
            tr_func(language, "load_profile")
        )

        self.reset_profile_btn.setText(
            tr_func(language, "reset_profile")
        )

        self.title_label.setText(
            tr_func(language, "profile")
        )

        self.subtitle_label.setText(
            tr_func(language, "profile_subtitle")
        )