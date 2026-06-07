from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QComboBox,
)

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon


class NodeEditorPanel(QFrame):
    def __init__(self, language="en", tr_func=None, icon_dir=None):
        super().__init__()

        self.language = language
        self.tr_func = tr_func
        self.icon_dir = icon_dir

        self.setObjectName("NodeEditorPanel")
        self.setFixedWidth(390)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()

        self.panel_title = QLabel()
        self.panel_title.setObjectName("PanelTitle")

        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("PanelCloseButton")
        self.close_btn.setFixedSize(34, 34)
        self.close_btn.setCursor(Qt.PointingHandCursor)

        header.addWidget(self.panel_title)
        header.addStretch()
        header.addWidget(self.close_btn)

        self.title_label = QLabel()
        self.title_label.setObjectName("FieldLabel")

        self.title_input = QLineEdit()
        self.title_input.setObjectName("FlowInput")

        self.desc_label = QLabel()
        self.desc_label.setObjectName("FieldLabel")

        self.desc_input = QTextEdit()
        self.desc_input.setObjectName("FlowTextEdit")
        self.desc_input.setFixedHeight(150)

        self.symbol_label = QLabel()
        self.symbol_label.setObjectName("FieldLabel")

        self.symbol_combo = QComboBox()
        self.symbol_combo.setObjectName("FlowSymbolCombo")
        self.symbol_combo.setIconSize(QSize(42, 42))
        self.symbol_combo.setMinimumHeight(58)
        self.symbol_combo.view().setIconSize(QSize(42, 42))
        self.symbol_combo.view().setMinimumHeight(260)

        self.symbol_options = [
            ("character", "Character"),
            ("level", "Level"),
            ("expedition", "Expedition"),
            ("daily_dungeon", "Daily Dungeon"),
            ("sanctuary", "Sanctuary"),
            ("pets", "Pets"),
            ("closet", "Closet"),
            ("enhancement", "Enhancement"),
            ("crafting", "Crafting"),
            ("supply_request", "Supply Request"),
        ]

        if self.icon_dir:
            for key, label in self.symbol_options:
                icon_path = self.icon_dir / f"{key}.png"
                self.symbol_combo.addItem(QIcon(str(icon_path)), label, key)
        else:
            for key, label in self.symbol_options:
                self.symbol_combo.addItem(label, key)

        button_row = QHBoxLayout()
        button_row.setSpacing(14)

        self.node_cancel_btn = QPushButton()
        self.node_cancel_btn.setObjectName("FlowCancelButton")

        self.node_save_btn = QPushButton()
        self.node_save_btn.setObjectName("FlowSaveButton")

        button_row.addWidget(self.node_cancel_btn)
        button_row.addWidget(self.node_save_btn)

        layout.addLayout(header)
        layout.addWidget(self.title_label)
        layout.addWidget(self.title_input)
        layout.addWidget(self.desc_label)
        layout.addWidget(self.desc_input)
        layout.addWidget(self.symbol_label)
        layout.addWidget(self.symbol_combo)
        layout.addSpacing(14)
        layout.addLayout(button_row)

        self.update_language(language, tr_func)

    def update_language(self, language, tr_func):
        self.language = language
        self.tr_func = tr_func

        if not tr_func:
            return

        self.panel_title.setText(tr_func(language, "flow_node_edit"))
        self.title_label.setText(tr_func(language, "flow_title_placeholder"))
        self.desc_label.setText(tr_func(language, "flow_description_placeholder"))
        self.symbol_label.setText(tr_func(language, "flow_symbol"))
        self.node_cancel_btn.setText(tr_func(language, "cancel"))
        self.node_save_btn.setText(tr_func(language, "flow_save"))