from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

_SCHEDULE_OBJECT_NAMES = {
    "daily":   "scheduleDaily",
    "weekly":  "scheduleWeekly",
    "season":  "scheduleSeason",
}

#: priority -> the objectName MASTER §3 colours (ok / warn / danger).  Same
#: map as ui/main_window.PRIORITY_OBJECT_NAMES; kept local so this widget
#: module does not import from main_window (which imports it).
_PRIORITY_OBJECT_NAMES = {
    "low": "priorityLow",
    "middle": "priorityMiddle",
    "medium": "priorityMiddle",
    "high": "priorityHigh",
}


def format_currency_price(value, currency: str = "kinah") -> str:
    """Shared k/m-suffix formatting for every real in-game currency
    (Kinah, Abyss Points, Nightmare Points, Shugo/Season Coins) -- module-
    level (not a ShoppingCard method) so other places that show a raw
    template/task price (e.g. TemplateDialog's shop-template picker row)
    can reuse the exact same, single implementation instead of each
    growing their own slightly-different copy.
    User-Wunsch, 2026-09-05: prices are entered/stored in THOUSANDS
    shorthand (e.g. "30" means "30k" = 30,000 real Kinah) -- reverted
    2026-09-08 after removing this pre-scale briefly on a single
    misleading example ("Commands (Green)" = 500 looking wrong as
    "500k"); the user then confirmed with a full list (screenshot:
    "Instant Clear Ticket..." = 30 must show "30k Kinah", not "30
    Kinah") that the thousands convention is the real, intended one
    app-wide -- that one earlier example was itself just a bad/legacy
    data point, not proof the formula was broken."""
    try:
        raw = float(str(value).replace(",", ".").strip())
    except ValueError:
        raw = 0

    # User-Wunsch, 2026-09-09: "SC" -> "Coins" in the price display (kept
    # as "SC" on the compact currency-selector toggle buttons elsewhere --
    # those are a different, size-constrained context this doesn't touch).
    units = {"kinah": "Kinah", "shugo": "Coins", "abyss": "AP", "nightmare": "NP"}
    unit = units.get(currency)
    if unit:
        scaled = raw * 1000
        if scaled >= 1_000_000:
            m = scaled / 1_000_000
            return f"{int(m)}m {unit}" if m == int(m) else f"{m:.1f}m {unit}"
        if scaled >= 1_000:
            k = scaled / 1_000
            return f"{int(k)}k {unit}" if k == int(k) else f"{k:.1f}k {unit}"
        return f"{int(scaled)} {unit}"

    return f"{int(raw) if raw == int(raw) else raw} {currency.upper()}"


class ShoppingCard(QFrame):
    def __init__(
        self,
        priority,
        amount,
        title,
        location,
        price,
        schedule="daily",
        is_event=False,   # legacy — mapped to "season" on load
        currency="kinah",
        character="",
        template_id="",
        card_id="",
    ):
        super().__init__()

        # legacy migration: is_event=True → schedule="season"
        if is_event and schedule == "daily":
            schedule = "season"

        # Same per-card identity as TaskCard.card_id -- see its own
        # docstring-comment for why (title, character) matching alone
        # isn't enough for "missed" tracking to reference one specific
        # card unambiguously.
        self.card_id = card_id or str(uuid4())
        self.priority = priority
        self.amount = amount
        self.title = title
        self.location = location
        self.price = price
        self.schedule = schedule
        self.currency = currency
        self.character = character
        self.template_id = template_id
        self.completed = False

        self.price_display = self.format_price(price, currency)

        self.setObjectName("taskCard")
        # Keyboard reachability (UX audit 2026-09-18, C1) -- mirrors
        # TaskCard. No focus styling here; the QSS is a separate pass.
        self.setFocusPolicy(Qt.StrongFocus)

        # Layout rebuilt to match TaskCard's own arrangement (User-Wunsch,
        # 2026-09-09: "das Layout von Shopping ... so anpassen, dass es
        # mit den Karten von den Tasks übereinstimmt ... Tags verschieben
        # ... Titel + Anzahl anpassen") -- schedule/character/missed move
        # into a badge row BELOW the title (previously always-visible on
        # the far right), and the amount badge is gone in favor of the
        # same "Title (Nx)" suffix TaskCard already uses.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        self.check_btn = QPushButton("○")
        self.check_btn.setObjectName("checkButton")
        self.check_btn.setFixedWidth(32)
        self.check_btn.clicked.connect(self.toggle)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)

        title_row = QHBoxLayout()
        self.title_label = QLabel()
        self.title_label.setObjectName("taskTitle")
        title_row.addWidget(self.title_label)
        title_row.addStretch()
        text_box.addLayout(title_row)
        self._refresh_title_display()

        self.info_label = QLabel(f"{location} • {self.price_display}")
        self.info_label.setObjectName("taskDescription")
        text_box.addWidget(self.info_label)

        # Schedule/character/missed badge row -- same arrangement as
        # TaskCard's own badge_row.
        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        schedule_text = {"daily": "DAILY", "weekly": "WEEKLY", "season": "SEASON"}.get(schedule, schedule.upper())
        self.schedule_label = QLabel(schedule_text)
        self.schedule_label.setObjectName(_SCHEDULE_OBJECT_NAMES.get(schedule, "scheduleDaily"))
        badge_row.addWidget(self.schedule_label)
        self.char_label = QLabel(character)
        self.char_label.setObjectName("scheduleWeekly")
        badge_row.addWidget(self.char_label)
        if not character:
            self.char_label.hide()
        # Same per-card "Missed" tag as TaskCard's own missed_badge -- see
        # its comment for why (User-reported, 2026-09-09: the aggregate
        # stat tile had no per-card equivalent).
        self.missed_badge = QLabel("MISSED")
        self.missed_badge.setObjectName("missedBadge")
        self.missed_badge.setVisible(False)
        badge_row.addWidget(self.missed_badge)
        badge_row.addStretch()
        text_box.addLayout(badge_row)

        self.priority_label = QLabel(priority.upper())
        # See the note in main_window.TaskCard: this was the literal
        # "priorityMedium" for every card, so every priority rendered warn.
        self._apply_priority_style()

        self.delete_btn = QPushButton("×")
        self.delete_btn.setObjectName("deleteButton")
        self.delete_btn.setFixedWidth(36)
        self.delete_btn.clicked.connect(self.deleteLater)

        layout.addWidget(self.check_btn)
        layout.addLayout(text_box, 1)
        layout.addWidget(self.priority_label)
        layout.addWidget(self.delete_btn)

    def set_missed(self, value: bool):
        self.missed_badge.setVisible(value)

    def _refresh_title_display(self):
        """Shows "Title (Nx)" once amount is more than 1 -- same convention
        as TaskCard._refresh_title_display(). title_label's TEXT is purely
        a display concern; self.title stays the plain, undecorated value
        everything else (serialization, template-title matching) uses."""
        amount = str(self.amount or "1")
        if amount not in ("1", "0", ""):
            self.title_label.setText(f"{self.title} ({amount}x)")
        else:
            self.title_label.setText(self.title)

    def set_title(self, title: str):
        self.title = title
        self._refresh_title_display()

    def set_amount(self, amount: str):
        self.amount = str(amount or "1")
        self._refresh_title_display()

    def update_from_template(self, tmpl: dict):
        """Refresh title/location/price/currency/priority/schedule from an edited template.
        Amount and character stay untouched — those are entry-specific, not template-specific."""
        self.priority = tmpl.get("priority", self.priority)
        self.location = tmpl.get("location", self.location)
        self.price = tmpl.get("price", self.price)
        self.schedule = tmpl.get("schedule", self.schedule)
        self.currency = tmpl.get("currency", self.currency)
        self.price_display = self.format_price(self.price, self.currency)

        self.set_title(tmpl.get("title", self.title))
        self.info_label.setText(f"{self.location} • {self.price_display}")
        self._apply_priority_style()

        schedule_text = {"daily": "DAILY", "weekly": "WEEKLY", "season": "SEASON"}.get(
            self.schedule, self.schedule.upper()
        )
        self.schedule_label.setText(schedule_text)
        self.schedule_label.setObjectName(_SCHEDULE_OBJECT_NAMES.get(self.schedule, "scheduleDaily"))
        self.style().unpolish(self.schedule_label)
        self.style().polish(self.schedule_label)

    def _apply_priority_style(self, text: str | None = None):
        """Label text + the objectName MASTER §3's ok/warn/danger rule needs.

        ``text`` is the already-translated label when the caller has one.
        """
        self.priority_label.setText(text if text is not None else str(self.priority or "").upper())
        self.priority_label.setObjectName(
            _PRIORITY_OBJECT_NAMES.get(self.priority, "priorityMiddle")
        )
        self.priority_label.style().unpolish(self.priority_label)
        self.priority_label.style().polish(self.priority_label)

    def toggle(self):
        self.completed = not self.completed
        self._apply_completed_style()

    def set_completed(self, value):
        self.completed = value
        self._apply_completed_style()

    def _apply_completed_style(self):
        self.check_btn.setText("●" if self.completed else "○")
        self.setProperty("completed", self.completed)
        # The muted, struck-through title and the green check come from
        # #taskCard[completed="true"] #taskTitle / #checkButton in the
        # template. A descendant rule keyed off an ANCESTOR's property is
        # only re-evaluated when the child itself is repolished, hence the
        # two extra passes below.
        for widget in (self, self.title_label, self.check_btn):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def format_price(self, value, currency: str = "kinah") -> str:
        return format_currency_price(value, currency)

    def format_kinah_price(self, value):
        return format_currency_price(value, "kinah")
