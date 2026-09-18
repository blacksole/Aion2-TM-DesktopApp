"""Reusable empty-state placeholder (UX audit 2026-09-18, finding M2:
"Empty states are blank" — the Shopping tab with no items renders as a
large void, the custom-timer manager shows nothing but a "+").

Deliberately style-free: no colors, no fonts, no QSS of its own. It only
exposes stable objectNames (``emptyState`` / ``emptyStateTitle`` /
``emptyStateHint`` / ``emptyStateAction``) so the later design pass can
style it from ``ui/styles.qss`` without touching this file. Until then it
inherits the palette like any plain widget.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class EmptyStateWidget(QWidget):
    """Centered "nothing here yet" block: title + optional hint + optional
    action button. Hidden on construction — callers show it explicitly."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("emptyState")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addStretch()

        self.title_label = QLabel("")
        self.title_label.setObjectName("emptyStateTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.hint_label = QLabel("")
        self.hint_label.setObjectName("emptyStateHint")
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setWordWrap(True)
        self.hint_label.setVisible(False)
        layout.addWidget(self.hint_label)

        self.action_button = QPushButton("")
        self.action_button.setObjectName("emptyStateAction")
        self.action_button.setCursor(Qt.PointingHandCursor)
        self.action_button.setVisible(False)
        layout.addWidget(self.action_button, 0, Qt.AlignHCenter)

        layout.addStretch()

        self._action_slot = None
        self.setVisible(False)

    # ── content ───────────────────────────────────────────────────────────

    def set_content(self, title: str, hint: str = "", action_label: str = "",
                    on_action=None):
        """Sets every piece at once. An empty ``hint``/``action_label``
        hides that piece; passing ``on_action`` rewires the button (the
        previous callback is always disconnected first, so repeated calls
        never stack up handlers)."""
        self.retranslate(title, hint, action_label)

        if self._action_slot is not None:
            self.action_button.clicked.disconnect(self._action_slot)
            self._action_slot = None

        if on_action is not None:
            self.action_button.clicked.connect(on_action)
            self._action_slot = on_action

        self.action_button.setVisible(bool(action_label) and on_action is not None)

    def retranslate(self, title: str, hint: str = "", action_label: str = ""):
        """Text-only refresh for a language switch — keeps the wired-up
        action callback and the current visibility untouched."""
        self.title_label.setText(title)
        self.hint_label.setText(hint)
        self.hint_label.setVisible(bool(hint))
        self.action_button.setText(action_label)
        if self._action_slot is not None:
            self.action_button.setVisible(bool(action_label))
