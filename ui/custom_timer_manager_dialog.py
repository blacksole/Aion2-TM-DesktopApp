from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QWidget, QInputDialog,
)
from ui.custom_timer_dialog import CustomTimerDialog
from ui.widgets.empty_state import EmptyStateWidget


class CustomTimerManagerDialog(QDialog):
    """Popup for managing custom timer categories and the custom timers
    themselves (add/edit/remove) — invoked directly from the Timers page
    instead of living inline as a Settings tab. Operates on local copies of
    the categories/timers lists so Cancel discards any changes made during
    this session; only accept() commits them back to the caller."""

    def __init__(self, categories: list, custom_timers: list,
                 language: str = "en", tr_func=None, parent=None):
        super().__init__(parent)
        self._language = language
        self._tr = tr_func or (lambda _l, k, **kw: k)
        self.setWindowTitle(self._tr(self._language, "ct_manager_title"))
        self.setModal(True)
        self.setMinimumWidth(560)

        self._timer_categories = list(categories) if categories else ["Custom Timer"]
        self._custom_timer_configs = [dict(t) for t in custom_timers]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # ── Kategorien ────────────────────────────────────────────────────
        cat_hdr = QHBoxLayout()
        cat_title = QLabel(self._tr(self._language, "ct_manager_categories_title"))
        cat_title.setObjectName("settingsSectionTitle")
        cat_hdr.addWidget(cat_title)
        cat_hdr.addStretch()
        layout.addLayout(cat_hdr)

        self._cat_rows_container = QWidget()
        self._cat_rows_layout = QVBoxLayout(self._cat_rows_container)
        self._cat_rows_layout.setContentsMargins(0, 0, 0, 4)
        self._cat_rows_layout.setSpacing(4)
        layout.addWidget(self._cat_rows_container)
        self._rebuild_category_rows()

        # ── Timer ─────────────────────────────────────────────────────────
        timer_hdr = QHBoxLayout()
        timer_title = QLabel(self._tr(self._language, "ct_manager_timer_section_title"))
        timer_title.setObjectName("settingsSectionTitle")
        self._add_ct_btn = QPushButton("＋")
        self._add_ct_btn.setObjectName("secondaryButton")
        self._add_ct_btn.setFixedWidth(44)
        self._add_ct_btn.setFixedHeight(32)
        self._add_ct_btn.clicked.connect(self._add_custom_timer)
        timer_hdr.addWidget(timer_title)
        timer_hdr.addStretch()
        timer_hdr.addWidget(self._add_ct_btn)
        layout.addLayout(timer_hdr)

        self._custom_ct_container = QWidget()
        self._custom_ct_layout = QVBoxLayout(self._custom_ct_container)
        self._custom_ct_layout.setContentsMargins(0, 0, 0, 0)
        self._custom_ct_layout.setSpacing(8)
        layout.addWidget(self._custom_ct_container)

        # UX audit 2026-09-18, M2: with no timers configured this section
        # showed nothing at all but the "＋" button in its header.
        self._ct_empty_state = EmptyStateWidget()
        layout.addWidget(self._ct_empty_state)

        self._rebuild_custom_timer_rows()

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._tr(self._language, "cancel"))
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        close_btn = QPushButton(self._tr(self._language, "ct_manager_done_button"))
        close_btn.setObjectName("primaryButton")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    # ── Result ────────────────────────────────────────────────────────────

    def get_categories(self) -> list:
        return self._timer_categories

    def get_custom_timers(self) -> list:
        return self._custom_timer_configs

    # ── Kategorien-Verwaltung ─────────────────────────────────────────────

    def _rebuild_category_rows(self):
        while self._cat_rows_layout.count():
            item = self._cat_rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for cat in self._timer_categories:
            self._cat_rows_layout.addWidget(self._build_category_row(cat))
        if len(self._timer_categories) < 4:
            add_btn = QPushButton(self._tr(self._language, "ct_manager_add_category_button"))
            add_btn.setObjectName("secondaryButton")
            add_btn.clicked.connect(self._add_category)
            self._cat_rows_layout.addWidget(add_btn)

    def _build_category_row(self, cat_name: str) -> QFrame:
        row = QFrame()
        row.setObjectName("settingsRow")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 6, 14, 6)
        rl.setSpacing(8)
        dot = QLabel("●")
        dot.setFixedWidth(16)
        dot.setStyleSheet("color: #22d3ee; font-size: 14px;")
        name_lbl = QLabel(cat_name)
        name_lbl.setObjectName("settingsLabel")
        rename_btn = QPushButton(self._tr(self._language, "ct_manager_rename_button"))
        rename_btn.setObjectName("secondaryButton")
        rename_btn.setFixedWidth(110)
        rename_btn.clicked.connect(lambda checked=False, cn=cat_name: self._rename_category(cn))
        rl.addWidget(dot)
        rl.addWidget(name_lbl, 1)
        rl.addWidget(rename_btn)
        has_timers = any(
            cfg.get("category", self._timer_categories[0]) == cat_name
            for cfg in self._custom_timer_configs
        )
        if len(self._timer_categories) > 1 and not has_timers:
            del_btn = QPushButton("✕")
            del_btn.setObjectName("secondaryButton")
            del_btn.setFixedWidth(36)
            del_btn.clicked.connect(lambda checked=False, cn=cat_name: self._remove_category(cn))
            rl.addWidget(del_btn)
        return row

    def _add_category(self):
        if len(self._timer_categories) >= 4:
            return
        name, ok = QInputDialog.getText(
            self,
            self._tr(self._language, "ct_manager_add_category_dialog_title"),
            self._tr(self._language, "ct_manager_name_label"),
        )
        if ok and name.strip():
            name = name.strip()[:20]
            if name not in self._timer_categories:
                self._timer_categories.append(name)
                self._rebuild_category_rows()

    def _remove_category(self, cat_name: str):
        if cat_name in self._timer_categories and len(self._timer_categories) > 1:
            self._timer_categories.remove(cat_name)
            self._rebuild_category_rows()

    def _rename_category(self, old_name: str):
        new_name, ok = QInputDialog.getText(
            self,
            self._tr(self._language, "ct_manager_rename_category_dialog_title"),
            self._tr(self._language, "ct_manager_new_name_label"),
            text=old_name,
        )
        if ok and new_name.strip():
            new_name = new_name.strip()[:20]
            if new_name != old_name and new_name not in self._timer_categories:
                idx = self._timer_categories.index(old_name)
                self._timer_categories[idx] = new_name
                for cfg in self._custom_timer_configs:
                    if cfg.get("category", "") == old_name:
                        cfg["category"] = new_name
                self._rebuild_category_rows()
                self._rebuild_custom_timer_rows()

    # ── Custom-Timer-Verwaltung ───────────────────────────────────────────

    def _add_custom_timer(self):
        if len(self._custom_timer_configs) >= 8:
            return
        dlg = CustomTimerDialog(
            categories=self._timer_categories,
            category=self._timer_categories[0],
            language=self._language, tr_func=self._tr,
            parent=self,
        )
        if dlg.exec():
            values = dlg.get_values()
            self._custom_timer_configs.append({
                "enabled": False,
                **values,
            })
            self._rebuild_custom_timer_rows()
            self._rebuild_category_rows()

    def _edit_custom_timer(self, idx: int):
        if idx >= len(self._custom_timer_configs):
            return
        cfg = self._custom_timer_configs[idx]
        dlg = CustomTimerDialog(
            name=cfg.get("name", ""),
            color=cfg.get("color", "#22d3ee"),
            timer_mode=cfg.get("timer_mode", "hourly"),
            reset_time=cfg.get("reset_time", "09:00"),
            reset_day=cfg.get("reset_day", "Mo"),
            interval_minutes=cfg.get("interval_minutes", 60),
            interval_seconds=cfg.get("interval_seconds", 3600),
            start_time=cfg.get("start_time", ""),
            countdown_duration_seconds=cfg.get("countdown_duration_seconds", 7200),
            countdown_restart_delay_seconds=cfg.get("countdown_restart_delay_seconds", 0),
            categories=self._timer_categories,
            category=cfg.get("category", self._timer_categories[0]),
            notification_sound=cfg.get("notification_sound", ""),
            notification_warn_minutes=cfg.get("notification_warn_minutes", 1),
            language=self._language, tr_func=self._tr,
            parent=self,
        )
        if dlg.exec():
            values = dlg.get_values()
            for field in ("name", "color", "timer_mode", "reset_time",
                          "reset_day", "interval_minutes", "interval_seconds",
                          "start_time", "countdown_duration_seconds",
                          "countdown_restart_delay_seconds", "category",
                          "notification_sound", "notification_warn_minutes"):
                if field in values:
                    cfg[field] = values[field]
                else:
                    cfg.pop(field, None)
            self._rebuild_custom_timer_rows()
            self._rebuild_category_rows()

    def _remove_custom_timer(self, idx: int):
        if idx < len(self._custom_timer_configs):
            del self._custom_timer_configs[idx]
            self._rebuild_custom_timer_rows()
            self._rebuild_category_rows()

    def _rebuild_custom_timer_rows(self):
        while self._custom_ct_layout.count():
            item = self._custom_ct_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, cfg in enumerate(self._custom_timer_configs):
            row = self._build_custom_timer_row(i, cfg)
            self._custom_ct_layout.addWidget(row)

        self._add_ct_btn.setVisible(len(self._custom_timer_configs) < 8)
        self._update_ct_empty_state()

    def _update_ct_empty_state(self):
        """Placeholder for the Timers section, gone as soon as one timer
        exists. Falls back to a neutral title while the translation keys
        are still missing -- core.translations.tr returns the raw key
        itself for an unknown one, which would show as "empty_timers_title".
        """
        if self._custom_timer_configs:
            self._ct_empty_state.setVisible(False)
            return

        title = self._tr(self._language, "empty_timers_title")
        hint = self._tr(self._language, "empty_timers_hint")
        if title == "empty_timers_title":
            title = self._tr(self._language, "ct_manager_timer_section_title")
        if hint == "empty_timers_hint":
            hint = ""
        self._ct_empty_state.set_content(title, hint)
        self._ct_empty_state.setVisible(True)

    def _build_custom_timer_row(self, idx: int, cfg: dict) -> QFrame:
        row = QFrame()
        row.setObjectName("settingsRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(14, 12, 14, 12)
        row_layout.setSpacing(10)

        color_dot = QLabel("●")
        color_dot.setFixedWidth(18)
        color_dot.setStyleSheet(f"color: {cfg['color']}; font-size: 18px;")

        name_lbl = QLabel(cfg["name"])
        name_lbl.setObjectName("settingsLabel")

        interval_lbl = QLabel(self._format_timer_summary(cfg))
        interval_lbl.setObjectName("settingsDescription")

        default_cat = self._timer_categories[0] if self._timer_categories else "Custom Timer"
        cat_lbl = QLabel(f"[{cfg.get('category', default_cat)}]")
        cat_lbl.setObjectName("settingsDescription")

        edit_btn = QPushButton(self._tr(self._language, "ct_manager_edit_button"))
        edit_btn.setObjectName("secondaryButton")
        edit_btn.setFixedWidth(110)
        edit_btn.clicked.connect(lambda checked=False, i=idx: self._edit_custom_timer(i))

        remove_btn = QPushButton("✕")
        remove_btn.setObjectName("secondaryButton")
        remove_btn.setFixedWidth(36)
        remove_btn.clicked.connect(lambda checked=False, i=idx: self._remove_custom_timer(i))

        toggle_btn = QPushButton()
        toggle_btn.setCheckable(True)
        toggle_btn.setChecked(cfg.get("enabled", False))
        toggle_btn.setObjectName("toggleButton")
        toggle_btn.setFixedWidth(70)
        on_text = self._tr(self._language, "ct_manager_on")
        off_text = self._tr(self._language, "ct_manager_off")
        toggle_btn.setText(on_text if cfg.get("enabled", False) else off_text)
        toggle_btn.toggled.connect(
            lambda checked, i=idx, btn=toggle_btn: self._on_custom_timer_toggled(i, checked, btn)
        )

        row_layout.addWidget(color_dot)
        row_layout.addWidget(name_lbl)
        row_layout.addWidget(interval_lbl)
        row_layout.addWidget(cat_lbl)
        row_layout.addStretch()
        row_layout.addWidget(edit_btn)
        row_layout.addWidget(remove_btn)
        row_layout.addWidget(toggle_btn)

        return row

    def _on_custom_timer_toggled(self, idx: int, checked: bool, btn=None):
        if idx < len(self._custom_timer_configs):
            self._custom_timer_configs[idx]["enabled"] = checked
        if btn:
            key = "ct_manager_on" if checked else "ct_manager_off"
            btn.setText(self._tr(self._language, key))

    def _format_timer_summary(self, cfg: dict) -> str:
        mode = cfg.get("timer_mode", "hourly")
        if mode == "daily":
            return self._tr(
                self._language, "ct_manager_summary_daily",
                time=cfg.get("reset_time", "09:00"),
            )
        if mode == "weekly":
            return self._tr(
                self._language, "ct_manager_summary_weekly",
                day=cfg.get("reset_day", "Mo"), time=cfg.get("reset_time", "09:00"),
            )
        if mode == "hourly":
            mins = cfg.get("interval_minutes", 60)
            h, m = divmod(mins, 60)
            if m == 0:
                return self._tr(self._language, "ct_manager_summary_hourly_h", h=h)
            return self._tr(self._language, "ct_manager_summary_hourly_hm", h=h, m=m)
        if mode == "countdown":
            secs = cfg.get("countdown_duration_seconds", 7200)
            h, rem = divmod(secs, 3600)
            m, _s = divmod(rem, 60)
            delay = cfg.get("countdown_restart_delay_seconds", 0)
            base = f"{h}h {m}min" if m else f"{h}h"
            prefix = self._tr(self._language, "ct_manager_summary_countdown_prefix", base=base)
            return prefix + (f" (+{delay}s)" if delay else "")
        # custom
        secs = cfg.get("interval_seconds", 3600)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02}:{m:02}:{s:02}"
