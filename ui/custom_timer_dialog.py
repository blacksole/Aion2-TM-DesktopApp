import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QButtonGroup, QGridLayout, QTimeEdit, QComboBox, QWidget, QSpinBox,
)
from PySide6.QtCore import Qt, QTime

CUSTOM_TIMER_COLORS = [
    ("#22d3ee", "Cyan"),
    ("#a855f7", "Lila"),
    ("#22c55e", "Grün"),
    ("#ef4444", "Rot"),
    ("#f97316", "Orange"),
    ("#ec4899", "Pink"),
    ("#f59e0b", "Gelb"),
    ("#3b82f6", "Blau"),
]

DISPLAY_FORMATS = [
    ("hh:mm:ss", "hh:mm:ss  (01:30:00)"),
    ("mm:ss",    "mm:ss  (90:00)"),
]

_HOUR_PRESETS = [1, 2, 3, 4, 5, 6]


class CustomTimerDialog(QDialog):
    def __init__(self, name: str = "", color: str = "#22d3ee",
                 interval_minutes: int = 60, display_format: str = "hh:mm:ss",
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Timer")
        self.setModal(True)
        self.setMinimumWidth(460)
        self._selected_color = color
        self._pencil_active = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title_lbl = QLabel("Custom Timer konfigurieren")
        title_lbl.setObjectName("settingsSectionTitle")
        layout.addWidget(title_lbl)

        # ── Live-Vorschau ────────────────────────────────────────────────
        preview_frame = QFrame()
        preview_frame.setObjectName("timerCard")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(16, 12, 16, 12)

        self.preview_title = QLabel((name or "NAME").upper())
        self.preview_title.setObjectName("statTitle")

        self.preview_value = QLabel(self._blank_for_fmt(display_format))
        self.preview_value.setStyleSheet(
            f"color: {color}; font-size: 30px; font-weight: bold;"
        )

        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.preview_value)
        layout.addWidget(preview_frame)

        # ── Name ─────────────────────────────────────────────────────────
        name_row = QHBoxLayout()
        name_lbl = QLabel("Name (max. 10 Zeichen)")
        name_lbl.setObjectName("settingsLabel")
        self.name_input = QLineEdit(name)
        self.name_input.setMaxLength(10)
        self.name_input.setObjectName("settingsTimeInput")
        self.name_input.setPlaceholderText("z.B. Lager")
        self.name_input.textChanged.connect(self._update_preview)
        name_row.addWidget(name_lbl)
        name_row.addWidget(self.name_input)
        layout.addLayout(name_row)

        # ── Farb-Panel ────────────────────────────────────────────────────
        color_lbl = QLabel("Farbe")
        color_lbl.setObjectName("settingsLabel")
        layout.addWidget(color_lbl)

        color_panel = QFrame()
        color_panel.setObjectName("settingsRow")
        color_panel_layout = QGridLayout(color_panel)
        color_panel_layout.setContentsMargins(10, 10, 10, 10)
        color_panel_layout.setSpacing(8)

        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)

        for i, (hex_color, color_name) in enumerate(CUSTOM_TIMER_COLORS):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(44, 30)
            btn.setToolTip(color_name)
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {hex_color};"
                f"  border-radius: 6px;"
                f"  border: 2px solid transparent;"
                f"}}"
                f"QPushButton:checked {{"
                f"  border: 2px solid #ffffff;"
                f"}}"
                f"QPushButton:hover {{"
                f"  border: 2px solid rgba(255,255,255,0.6);"
                f"}}"
            )
            if hex_color == color:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked=False, c=hex_color: self._select_color(c))
            self.color_group.addButton(btn)
            color_panel_layout.addWidget(btn, i // 4, i % 4)

        layout.addWidget(color_panel)

        # ── Anzeigeformat ─────────────────────────────────────────────────
        format_row = QHBoxLayout()
        format_lbl = QLabel("Anzeigeformat")
        format_lbl.setObjectName("settingsLabel")
        self.format_combo = QComboBox()
        self.format_combo.setObjectName("settingsCombo")
        self.format_combo.setFixedWidth(210)
        for key, label in DISPLAY_FORMATS:
            self.format_combo.addItem(label, key)
        idx = self.format_combo.findData(display_format)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)
        format_row.addWidget(format_lbl)
        format_row.addStretch()
        format_row.addWidget(self.format_combo)
        layout.addLayout(format_row)

        # ── Intervall ─────────────────────────────────────────────────────
        interval_lbl = QLabel("Intervall")
        interval_lbl.setObjectName("settingsLabel")
        layout.addWidget(interval_lbl)

        # Preset-Buttons (für hh:mm:ss)
        self._presets_widget = QWidget()
        presets_layout = QHBoxLayout(self._presets_widget)
        presets_layout.setContentsMargins(0, 0, 0, 0)
        presets_layout.setSpacing(6)

        self._preset_group = QButtonGroup(self)
        self._preset_group.setExclusive(True)
        preset_match = False
        for h in _HOUR_PRESETS:
            btn = QPushButton(f"{h}h")
            btn.setCheckable(True)
            btn.setObjectName("dayButton")
            btn.setFixedSize(46, 32)
            if h * 60 == interval_minutes:
                btn.setChecked(True)
                preset_match = True
            self._preset_group.addButton(btn)
            presets_layout.addWidget(btn)

        self._pencil_btn = QPushButton("✏")
        self._pencil_btn.setObjectName("secondaryButton")
        self._pencil_btn.setFixedSize(36, 32)
        self._pencil_btn.setCheckable(True)
        self._pencil_btn.setChecked(not preset_match and display_format == "hh:mm:ss")
        self._pencil_btn.clicked.connect(self._on_pencil_clicked)
        presets_layout.addWidget(self._pencil_btn)
        presets_layout.addStretch()

        layout.addWidget(self._presets_widget)

        # Manueller Zeit-Input (Stift-Modus bei hh:mm:ss)
        self._manual_widget = QWidget()
        manual_layout = QHBoxLayout(self._manual_widget)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(8)

        self.interval_time = QTimeEdit()
        self.interval_time.setObjectName("settingsTimeInput")
        self.interval_time.setDisplayFormat("HH:mm")
        h_val, m_val = divmod(max(1, interval_minutes), 60)
        self.interval_time.setTime(QTime(h_val, m_val))
        self.interval_time.setFixedWidth(110)
        manual_layout.addWidget(self.interval_time)
        manual_layout.addStretch()

        layout.addWidget(self._manual_widget)

        # Minuten-Input (nur für mm:ss Modus)
        self._minutes_widget = QWidget()
        minutes_layout = QHBoxLayout(self._minutes_widget)
        minutes_layout.setContentsMargins(0, 0, 0, 0)
        minutes_layout.setSpacing(8)

        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setObjectName("settingsTimeInput")
        self.interval_spinbox.setRange(1, 999)
        self.interval_spinbox.setSuffix(" min")
        self.interval_spinbox.setValue(max(1, interval_minutes))
        self.interval_spinbox.setFixedWidth(120)
        minutes_layout.addWidget(self.interval_spinbox)
        minutes_layout.addStretch()

        layout.addWidget(self._minutes_widget)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton("Abbrechen")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton("Speichern")
        self.ok_btn.setObjectName("primaryButton")
        self.ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.ok_btn)
        layout.addLayout(btn_row)

        # Format-Wechsel verdrahten (nach Widget-Erstellung)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        self._apply_format_ui(display_format, animate=False)

    # ── Slots ────────────────────────────────────────────────────────────

    def _select_color(self, color: str):
        self._selected_color = color
        self.preview_value.setStyleSheet(
            f"color: {color}; font-size: 30px; font-weight: bold;"
        )

    def _update_preview(self):
        text = self.name_input.text().strip().upper() or "NAME"
        self.preview_title.setText(text)

    def _on_format_changed(self):
        fmt = self.format_combo.currentData()
        self.preview_value.setText(self._blank_for_fmt(fmt))
        self._apply_format_ui(fmt)

    def _on_pencil_clicked(self):
        self._manual_widget.setVisible(self._pencil_btn.isChecked())

    def _apply_format_ui(self, fmt: str, animate: bool = True):
        is_hours = fmt == "hh:mm:ss"
        self._presets_widget.setVisible(is_hours)
        self._manual_widget.setVisible(is_hours and self._pencil_btn.isChecked())
        self._minutes_widget.setVisible(not is_hours)
        if not is_hours:
            self._pencil_btn.setChecked(False)

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _blank_for_fmt(fmt: str) -> str:
        return "00:00:00" if fmt == "hh:mm:ss" else "00:00"

    # ── Result ───────────────────────────────────────────────────────────

    def get_values(self) -> dict:
        fmt = self.format_combo.currentData()
        if fmt == "hh:mm:ss":
            checked = self._preset_group.checkedButton()
            if checked and not self._pencil_btn.isChecked():
                h = int(checked.text().replace("h", ""))
                total_minutes = h * 60
            else:
                t = self.interval_time.time()
                total_minutes = t.hour() * 60 + t.minute()
        else:
            total_minutes = self.interval_spinbox.value()

        if total_minutes < 1:
            total_minutes = 1

        return {
            "name": self.name_input.text().strip() or "Timer",
            "color": self._selected_color,
            "interval_minutes": total_minutes,
            "display_format": fmt,
        }
