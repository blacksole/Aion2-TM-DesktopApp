"""Reusable empty-state placeholder (UX audit 2026-09-18, finding M2:
"Empty states are blank" — the Shopping tab with no items renders as a
large void, the custom-timer manager shows nothing but a "+").

Deliberately style-free: no colors, no fonts, no QSS of its own. It only
exposes stable objectNames (``emptyState`` / ``emptyStateTitle`` /
``emptyStateHint`` / ``emptyStateAction``) so the later design pass can
style it from ``ui/styles.template.qss`` without touching this file — it
now does, see #emptyState / #emptyStateTitle / #emptyStateHint there.

The icon (MASTER §3: « État vide : icône Lucide 24 px ``fg.muted`` »,
review G/m13) arrived with the icons wave. It is **optional** and hidden
by default: ``ui/pages/armory_page.py`` builds an EmptyStateWidget too and
is owned by another change at the time of writing, so a widget that grew a
mandatory icon would have altered a page this file must not touch.
``set_icon(name)`` is the whole opt-in.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ui.widgets.icons import IconLabel


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

        #: MASTER §3 — 24 px, ``fg.muted``, above the title.  Built lazily
        #: by :meth:`set_icon` so an empty state that names no icon keeps
        #: exactly the geometry it had before this widget grew one.
        self.icon_label: IconLabel | None = None
        self._icon_slot = layout.count()

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

    # ── icon ──────────────────────────────────────────────────────────────

    def set_icon(self, name: str, size: int = 24, color: str = "fg.muted"):
        """Show a Lucide icon above the title (MASTER §3: 24 px, ``fg.muted``).

        Calling it again swaps the glyph; the widget is created once. Passing
        an empty ``name`` hides it again.
        """
        if not name:
            if self.icon_label is not None:
                self.icon_label.setVisible(False)
            return

        if self.icon_label is None:
            self.icon_label = IconLabel(name, size, color)
            self.icon_label.setObjectName("emptyStateIcon")
            layout = self.layout()
            layout.insertWidget(self._icon_slot, self.icon_label, 0, Qt.AlignHCenter)
        else:
            self.icon_label.set_icon(name, color)
        self.icon_label.setVisible(True)

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
