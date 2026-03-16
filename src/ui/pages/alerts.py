"""
Alerts page for CryptoRadar — manage and monitor alerts
"""
import logging
from datetime import datetime
from typing import Optional, Dict, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDoubleSpinBox, QDialog, QTableWidgetItem, QMessageBox, QHeaderView,
    QCheckBox, QListWidget, QListWidgetItem, QScrollArea, QFrame,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from ui.styles.theme import Theme
from ui.widgets.data_table import DataTable
from services.alert_service import AlertService
from database import Database

logger = logging.getLogger(__name__)

ALERT_TYPE_CONFIG = {
    "spread": {
        "name": "Spread",
        "color": Theme.ACCENT_GREEN,
        "bg": "#0f6944",
        "icon": "🔄",
    },
    "gas": {
        "name": "Gas",
        "color": getattr(Theme, "ACCENT_BLUE", "#3742fa"),
        "bg": "#0f3a6f",
        "icon": "⛽",
    },
    "funding": {
        "name": "Funding",
        "color": Theme.ACCENT_YELLOW,
        "bg": "#6f5f0f",
        "icon": "📊",
    },
    "price": {
        "name": "Price",
        "color": "#b366ff",
        "bg": "#4d1a99",
        "icon": "💰",
    },
    "whale": {
        "name": "Whale",
        "color": "#ff9933",
        "bg": "#664d00",
        "icon": "🐋",
    },
}

COOLDOWN_OPTIONS = {
    60: "1 minute",
    300: "5 minutes",
    900: "15 minutes",
    1800: "30 minutes",
    3600: "1 hour",
}

COINS = [
    "Any", "BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "AVAX",
    "LINK", "ARB", "OP", "BNB", "MATIC", "DOT", "ATOM", "UNI", "LTC",
]

NETWORKS = ["Ethereum", "BSC", "Polygon", "Arbitrum", "Optimism", "Avalanche"]

EXCHANGES = ["Any exchanges", "Binance", "Bybit", "OKX", "Bitget", "Kraken", "dYdX"]

OP_MAP = {">": "gt", "<": "lt", "=": "eq"}
OP_MAP_REV = {"gt": ">", "lt": "<", "eq": "="}


def _cfg(alert_type: str) -> dict:
    return ALERT_TYPE_CONFIG.get(alert_type, ALERT_TYPE_CONFIG["spread"])


# ------------------------------------------------------------------
# New / Edit Alert Dialog
# ------------------------------------------------------------------

class NewAlertDialog(QDialog):
    def __init__(self, alert_service: AlertService, parent=None,
                 alert_id: Optional[int] = None):
        super().__init__(parent)
        self.alert_service = alert_service
        self.alert_id = alert_id
        self.db = Database()
        self.current_step = 0
        self.alert_data: Dict = {}

        self.setWindowTitle("Edit Alert" if alert_id else "New Alert")
        self.setMinimumWidth(520)
        self.setMinimumHeight(400)

        self._init_ui()

        if alert_id:
            self._load_existing(alert_id)

        self._show_step(1)

    # ---- styles ----

    @staticmethod
    def _btn_style(accent: bool) -> str:
        if accent:
            return f"""
                QPushButton {{
                    background-color: {Theme.ACCENT_GREEN};
                    color: #000;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 20px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: #00e894; }}
                QPushButton:disabled {{ background-color: {Theme.BORDER}; color: {Theme.TEXT_SECONDARY}; }}
            """
        return f"""
            QPushButton {{
                background-color: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{ border-color: {Theme.ACCENT_GREEN}; }}
        """

    @staticmethod
    def _combo_style() -> str:
        return f"""
            QComboBox {{
                background-color: {Theme.BG_PRIMARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                min-width: 120px;
            }}
            QComboBox:hover {{ border-color: {Theme.ACCENT_GREEN}; }}
            QComboBox QAbstractItemView {{
                background-color: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                selection-background-color: {Theme.ACCENT_GREEN};
            }}
        """

    @staticmethod
    def _spin_style() -> str:
        return f"""
            QDoubleSpinBox, QSpinBox {{
                background-color: {Theme.BG_PRIMARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 6px;
            }}
            QDoubleSpinBox:hover, QSpinBox:hover {{
                border-color: {Theme.ACCENT_GREEN};
            }}
        """

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;"
        )
        return lbl

    # ---- UI ----

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self.step_label = QLabel()
        self.step_label.setFont(QFont(Theme.FONT_FAMILY, 12, QFont.Weight.Bold))
        self.step_label.setStyleSheet(
            f"color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;"
        )
        layout.addWidget(self.step_label)

        self.content_layout = QVBoxLayout()
        layout.addLayout(self.content_layout, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.back_btn = QPushButton("← Back")
        self.back_btn.setStyleSheet(self._btn_style(False))
        self.back_btn.clicked.connect(self._go_back)
        self.back_btn.setVisible(False)
        btn_row.addWidget(self.back_btn)

        self.next_btn = QPushButton("Next →")
        self.next_btn.setStyleSheet(self._btn_style(True))
        self.next_btn.clicked.connect(self._go_next)
        btn_row.addWidget(self.next_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(self._btn_style(False))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)
        self.setLayout(layout)

        self.setStyleSheet(f"QDialog {{ background-color: {Theme.BG_CARD}; }}")

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                self._clear_child_layout(item.layout())

    @staticmethod
    def _clear_child_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                NewAlertDialog._clear_child_layout(item.layout())

    def _frame(self) -> QFrame:
        f = QFrame()
        f.setObjectName("alertDialogFrame")
        f.setStyleSheet(f"""
            QFrame#alertDialogFrame {{
                background-color: {Theme.BG_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
            }}
        """)
        return f

    # ---- Step navigation ----

    def _show_step(self, step: int):
        self.current_step = step
        self._clear_content()

        if step == 1:
            self._build_step1()
        elif step == 2:
            self._build_step2()
        elif step == 3:
            self._build_step3()

    def _go_next(self):
        if self.current_step == 1:
            if "alert_type" not in self.alert_data:
                QMessageBox.warning(self, "Select Type", "Please select an alert type first.")
                return
            self._show_step(2)

        elif self.current_step == 2:
            if self._collect_step2():
                self._show_step(3)

        elif self.current_step == 3:
            if self._save_alert():
                self.accept()

    def _go_back(self):
        if self.current_step > 1:
            self._show_step(self.current_step - 1)

    # ---- Step 1: Type selection ----

    def _build_step1(self):
        self.step_label.setText("Step 1 / 3 — Select Alert Type")
        self.back_btn.setVisible(False)
        self.next_btn.setText("Next →")

        frame = self._frame()
        grid = QHBoxLayout()
        grid.setSpacing(8)
        grid.setContentsMargins(16, 16, 16, 16)

        self._type_buttons: Dict[str, QPushButton] = {}

        for atype, cfg in ALERT_TYPE_CONFIG.items():
            btn = QPushButton(f"{cfg['icon']}\n{cfg['name']}")
            btn.setMinimumHeight(80)
            btn.setMinimumWidth(90)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            btn.clicked.connect(lambda _, t=atype: self._select_type(t))
            self._type_buttons[atype] = btn
            grid.addWidget(btn)

        self._highlight_selected_type()
        frame.setLayout(grid)
        self.content_layout.addWidget(frame)
        self.content_layout.addStretch()

    def _select_type(self, atype: str):
        self.alert_data["alert_type"] = atype
        self._highlight_selected_type()

    def _highlight_selected_type(self):
        selected = self.alert_data.get("alert_type")
        for atype, btn in self._type_buttons.items():
            cfg = _cfg(atype)
            if atype == selected:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {cfg['bg']};
                        color: {cfg['color']};
                        border: 2px solid {cfg['color']};
                        border-radius: 8px;
                        font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {Theme.BG_CARD};
                        color: {Theme.TEXT_PRIMARY};
                        border: 2px solid {Theme.BORDER};
                        border-radius: 8px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        border-color: {cfg['color']};
                    }}
                """)

    # ---- Step 2: Condition ----

    def _build_step2(self):
        atype = self.alert_data["alert_type"]
        cfg = _cfg(atype)
        self.step_label.setText(f"Step 2 / 3 — {cfg['icon']} {cfg['name']} Condition")
        self.back_btn.setVisible(True)
        self.next_btn.setText("Next →")

        frame = self._frame()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        builder = {
            "spread": self._build_spread_fields,
            "gas": self._build_gas_fields,
            "funding": self._build_funding_fields,
            "price": self._build_price_fields,
            "whale": self._build_whale_fields,
        }.get(atype)

        if builder:
            builder(layout)

        layout.addStretch()
        frame.setLayout(layout)
        self.content_layout.addWidget(frame)
        self.content_layout.addStretch()

    def _make_combo(self, items: list, current: str = "") -> QComboBox:
        cb = QComboBox()
        cb.addItems(items)
        cb.setStyleSheet(self._combo_style())
        if current and current in items:
            cb.setCurrentText(current)
        return cb

    def _make_op_combo(self, ops: list, current_op: str = "gt") -> QComboBox:
        cb = QComboBox()
        cb.addItems(ops)
        cb.setStyleSheet(self._combo_style())
        rev = OP_MAP_REV.get(current_op, ">")
        if rev in ops:
            cb.setCurrentText(rev)
        return cb

    def _make_spin(self, maximum: float, value: float, decimals: int) -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setMaximum(maximum)
        sb.setValue(value)
        sb.setDecimals(decimals)
        sb.setStyleSheet(self._spin_style())
        return sb

    def _hrow(self, layout, *widgets):
        row = QHBoxLayout()
        for w in widgets:
            if isinstance(w, str):
                row.addWidget(self._label(w))
            else:
                row.addWidget(w)
        row.addStretch()
        layout.addLayout(row)

    def _build_spread_fields(self, layout):
        self._s2_coin = self._make_combo(COINS, self.alert_data.get("coin", "Any"))
        self._hrow(layout, "Coin:", self._s2_coin)

        self._s2_op = self._make_op_combo([">", "<", "="], self.alert_data.get("condition_op", "gt"))
        self._s2_val = self._make_spin(100.0, self.alert_data.get("threshold", 0.3), 2)
        self._hrow(layout, "Spread", self._s2_op, self._s2_val, "%")

        self._s2_ex = self._make_combo(EXCHANGES, self.alert_data.get("exchange1", ""))
        self._hrow(layout, "Exchange:", self._s2_ex)

    def _build_gas_fields(self, layout):
        self._s2_network = self._make_combo(NETWORKS, self.alert_data.get("network", "Ethereum"))
        self._hrow(layout, "Network:", self._s2_network)

        self._s2_op = self._make_op_combo(["<", ">", "="], self.alert_data.get("condition_op", "lt"))
        self._s2_val = self._make_spin(10000.0, self.alert_data.get("threshold", 15.0), 1)
        self._hrow(layout, "Gas price", self._s2_op, self._s2_val, "gwei")

    def _build_funding_fields(self, layout):
        self._s2_coin = self._make_combo(COINS, self.alert_data.get("coin", "Any"))
        self._hrow(layout, "Coin:", self._s2_coin)

        self._s2_op = self._make_op_combo([">", "<", "="], self.alert_data.get("condition_op", "gt"))
        self._s2_val = self._make_spin(100.0, self.alert_data.get("threshold", 0.05), 3)
        self._hrow(layout, "|Funding rate|", self._s2_op, self._s2_val, "%")

    def _build_price_fields(self, layout):
        coins_no_any = COINS[1:]
        self._s2_coin = self._make_combo(coins_no_any, self.alert_data.get("coin", "BTC"))
        self._hrow(layout, "Coin:", self._s2_coin)

        self._s2_op = self._make_op_combo([">", "<", "="], self.alert_data.get("condition_op", "gt"))
        self._s2_val = self._make_spin(10_000_000.0, self.alert_data.get("threshold", 50000.0), 2)
        self._hrow(layout, "Price", self._s2_op, self._s2_val, "USD")

    def _build_whale_fields(self, layout):
        coins_no_any = COINS[1:]
        self._s2_coin = self._make_combo(coins_no_any, self.alert_data.get("coin", "BTC"))
        self._hrow(layout, "Coin:", self._s2_coin)

        self._s2_val = self._make_spin(1_000_000_000.0, self.alert_data.get("threshold", 1000.0), 2)
        self._hrow(layout, "Transfer >", self._s2_val, "coins")

    def _collect_step2(self) -> bool:
        atype = self.alert_data["alert_type"]

        if atype in ("spread", "funding"):
            coin = self._s2_coin.currentText()
            if coin == "Any":
                QMessageBox.warning(self, "Select Coin", f"Please select a coin for {atype} alerts.")
                return False
            self.alert_data["coin"] = coin
            self.alert_data["condition_op"] = OP_MAP.get(self._s2_op.currentText(), "gt")
            self.alert_data["threshold"] = self._s2_val.value()
            if atype == "spread":
                self.alert_data["exchange1"] = self._s2_ex.currentText()

        elif atype == "gas":
            self.alert_data["network"] = self._s2_network.currentText()
            self.alert_data["condition_op"] = OP_MAP.get(self._s2_op.currentText(), "lt")
            self.alert_data["threshold"] = self._s2_val.value()

        elif atype == "price":
            self.alert_data["coin"] = self._s2_coin.currentText()
            self.alert_data["condition_op"] = OP_MAP.get(self._s2_op.currentText(), "gt")
            self.alert_data["threshold"] = self._s2_val.value()

        elif atype == "whale":
            self.alert_data["coin"] = self._s2_coin.currentText()
            self.alert_data["condition_op"] = "gt"
            self.alert_data["threshold"] = self._s2_val.value()

        return True

    # ---- Step 3: Notifications ----

    def _build_step3(self):
        self.step_label.setText("Step 3 / 3 — Notification Settings")
        self.back_btn.setVisible(True)
        self.next_btn.setText("✓ Create Alert" if not self.alert_id else "✓ Save")

        cb_style = f"""
            QCheckBox {{
                color: {Theme.TEXT_PRIMARY};
                background: transparent;
                border: none;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px; height: 18px;
                border: 2px solid {Theme.BORDER};
                border-radius: 4px;
                background: {Theme.BG_PRIMARY};
            }}
            QCheckBox::indicator:checked {{
                background: {Theme.ACCENT_GREEN};
                border-color: {Theme.ACCENT_GREEN};
            }}
        """

        frame = self._frame()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._s3_notify = QCheckBox("🔔 Windows notification")
        self._s3_notify.setChecked(True)
        self._s3_notify.setStyleSheet(cb_style)
        layout.addWidget(self._s3_notify)

        self._s3_sound = QCheckBox("🔊 Sound alert")
        self._s3_sound.setChecked(True)
        self._s3_sound.setStyleSheet(cb_style)
        layout.addWidget(self._s3_sound)

        self._s3_cooldown = self._make_combo(
            list(COOLDOWN_OPTIONS.values()), "5 minutes"
        )
        self._hrow(layout, "Cooldown:", self._s3_cooldown)

        # Summary
        layout.addSpacing(8)
        summary = self._build_summary()
        summary_lbl = QLabel(summary)
        summary_lbl.setWordWrap(True)
        summary_lbl.setStyleSheet(
            f"color: {Theme.TEXT_SECONDARY}; background: transparent; "
            f"border: none; font-size: 10pt;"
        )
        layout.addWidget(summary_lbl)

        layout.addStretch()
        frame.setLayout(layout)
        self.content_layout.addWidget(frame)
        self.content_layout.addStretch()

    def _build_summary(self) -> str:
        atype = self.alert_data.get("alert_type", "")
        cfg = _cfg(atype)
        op = OP_MAP_REV.get(self.alert_data.get("condition_op", "gt"), ">")
        threshold = self.alert_data.get("threshold", 0)
        coin = self.alert_data.get("coin", "")
        network = self.alert_data.get("network", "")

        parts = [f"{cfg['icon']} {cfg['name']} alert:"]

        if atype == "spread":
            parts.append(f"{coin} spread {op} {threshold}%")
        elif atype == "gas":
            parts.append(f"{network} gas {op} {threshold} gwei")
        elif atype == "funding":
            parts.append(f"{coin} |funding| {op} {threshold}%")
        elif atype == "price":
            parts.append(f"{coin} price {op} ${threshold:,.0f}")
        elif atype == "whale":
            parts.append(f"{coin} transfer > {threshold:,.0f} coins")

        return " ".join(parts)

    # ---- Save ----

    def _save_alert(self) -> bool:
        try:
            cooldown_text = self._s3_cooldown.currentText()
            cooldown_secs = next(
                (k for k, v in COOLDOWN_OPTIONS.items() if v == cooldown_text),
                300,
            )

            alert_dict = {
                "alert_type": self.alert_data.get("alert_type"),
                "condition_op": self.alert_data.get("condition_op", "gt"),
                "threshold": self.alert_data.get("threshold", 0),
                "enabled": 1,
                "cooldown_seconds": cooldown_secs,
            }

            for key in ("coin", "network", "exchange1"):
                if key in self.alert_data:
                    alert_dict[key] = self.alert_data[key]

            if self.alert_id:
                self.db.update_alert(self.alert_id, alert_dict)
            else:
                self.alert_service.add_alert(alert_dict)

            logger.info(f"Alert saved: {alert_dict}")
            return True

        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save alert: {e}")
            return False

    def _load_existing(self, alert_id: int):
        try:
            alerts = self.db.get_alerts()
            for alert in alerts:
                if alert.get("id") == alert_id:
                    self.alert_data = dict(alert)
                    break
        except Exception as e:
            logger.error(f"Failed to load alert {alert_id}: {e}")


# ------------------------------------------------------------------
# Alerts Page
# ------------------------------------------------------------------

class AlertsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.alert_service = AlertService()
        self.db = Database()
        self._initialized = False

        if hasattr(self.alert_service, "alert_triggered"):
            self.alert_service.alert_triggered.connect(self._on_alert_triggered)

        self._init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initialized:
            self._initialized = True
        self._refresh_alerts()

    def _init_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {Theme.BG_PRIMARY};
                border: none;
            }}
            QScrollBar:vertical {{
                background: {Theme.BG_PRIMARY};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {Theme.BORDER};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        content = QWidget()
        content.setStyleSheet(f"background: {Theme.BG_PRIMARY};")
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl_style = f"background: transparent; border: none; color: {Theme.TEXT_PRIMARY};"

        # Header
        header = QHBoxLayout()
        title = QLabel("Alerts")
        title.setFont(QFont(Theme.FONT_FAMILY, 16, QFont.Weight.Bold))
        title.setStyleSheet(lbl_style)
        header.addWidget(title)
        header.addStretch()

        new_btn = QPushButton("+ New Alert")
        new_btn.setMinimumHeight(38)
        new_btn.setMinimumWidth(140)
        new_btn.setFont(QFont(Theme.FONT_FAMILY, 10, QFont.Weight.Bold))
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.ACCENT_GREEN};
                color: #000;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
            }}
            QPushButton:hover {{ background-color: #00e894; }}
        """)
        new_btn.clicked.connect(self._show_new_dialog)
        header.addWidget(new_btn)
        layout.addLayout(header)

        # Active alerts label
        active_lbl = QLabel("Active Alerts")
        active_lbl.setFont(QFont(Theme.FONT_FAMILY, 12, QFont.Weight.Bold))
        active_lbl.setStyleSheet(lbl_style)
        layout.addWidget(active_lbl)

        # Table
        self.alerts_table = DataTable([
            "Type", "Condition", "Enabled", "Triggered", "Actions"
        ])
        self.alerts_table.setMinimumHeight(180)
        self.alerts_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.alerts_table, 1)

        # History label
        hist_lbl = QLabel("📜 Recent Alert History")
        hist_lbl.setFont(QFont(Theme.FONT_FAMILY, 12, QFont.Weight.Bold))
        hist_lbl.setStyleSheet(lbl_style)
        layout.addWidget(hist_lbl)

        # History list
        self.history_list = QListWidget()
        self.history_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                color: {Theme.TEXT_PRIMARY};
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {Theme.BORDER};
            }}
        """)
        self.history_list.setMinimumHeight(120)
        self.history_list.setMaximumHeight(280)
        layout.addWidget(self.history_list)

        layout.addStretch()
        content.setLayout(layout)
        scroll.setWidget(content)
        root.addWidget(scroll)
        self.setLayout(root)

    # ---- refresh ----

    def _refresh_alerts(self):
        try:
            alerts = self.alert_service.get_alerts()
            self.alerts_table.setRowCount(0)

            for alert in alerts:
                row = self.alerts_table.rowCount()
                self.alerts_table.insertRow(row)

                atype = alert.get("alert_type", "spread")
                cfg = _cfg(atype)

                # Type
                type_item = QTableWidgetItem(f"{cfg['icon']} {cfg['name']}")
                type_item.setBackground(QColor(cfg["bg"]))
                type_item.setForeground(QColor(cfg["color"]))
                type_item.setFont(QFont(Theme.FONT_FAMILY, 10, QFont.Weight.Bold))
                self.alerts_table.setItem(row, 0, type_item)

                # Condition
                cond_item = QTableWidgetItem(self._fmt_condition(alert))
                cond_item.setForeground(QColor(Theme.TEXT_PRIMARY))
                self.alerts_table.setItem(row, 1, cond_item)

                # Enabled toggle
                cb = QCheckBox()
                cb.setChecked(bool(alert.get("enabled", 1)))
                cb.setStyleSheet(f"""
                    QCheckBox::indicator {{
                        width: 18px; height: 18px;
                        border: 2px solid {Theme.BORDER};
                        border-radius: 4px;
                        background: {Theme.BG_PRIMARY};
                    }}
                    QCheckBox::indicator:checked {{
                        background: {Theme.ACCENT_GREEN};
                        border-color: {Theme.ACCENT_GREEN};
                    }}
                """)
                aid = alert.get("id")
                cb.stateChanged.connect(
                    lambda state, a=aid: self._toggle_alert(a, state == Qt.Checked.value
                                                            if hasattr(Qt.Checked, "value")
                                                            else state == 2)
                )
                self.alerts_table.setCellWidget(row, 2, cb)

                # Triggered
                count = alert.get("trigger_count", 0)
                last = alert.get("last_triggered", "")
                t_item = QTableWidgetItem(f"{count}×")
                if last:
                    t_item.setToolTip(f"Last: {last}")
                t_item.setForeground(QColor(Theme.TEXT_SECONDARY))
                self.alerts_table.setItem(row, 3, t_item)

                # Actions
                actions = QWidget()
                actions.setStyleSheet("background: transparent; border: none;")
                a_layout = QHBoxLayout()
                a_layout.setContentsMargins(2, 2, 2, 2)
                a_layout.setSpacing(4)

                edit_btn = QPushButton("✏ Edit")
                edit_btn.setMaximumWidth(70)
                edit_btn.setStyleSheet(self._action_style())
                edit_btn.clicked.connect(lambda _, a=aid: self._edit_alert(a))
                a_layout.addWidget(edit_btn)

                del_btn = QPushButton("🗑")
                del_btn.setMaximumWidth(36)
                del_btn.setStyleSheet(self._action_style(delete=True))
                del_btn.clicked.connect(lambda _, a=aid: self._delete_alert(a))
                a_layout.addWidget(del_btn)

                a_layout.addStretch()
                actions.setLayout(a_layout)
                self.alerts_table.setCellWidget(row, 4, actions)

            self._refresh_history()

        except Exception as e:
            logger.error(f"Failed to refresh alerts: {e}")

    def _refresh_history(self):
        try:
            self.history_list.clear()
            logs = self.db.get_alert_logs(limit=50)

            for log in logs:
                ts = log.get("timestamp", "")
                atype = log.get("alert_type", "")
                message = log.get("message", "")
                cfg = _cfg(atype)

                try:
                    dt = datetime.fromisoformat(ts)
                    time_str = dt.strftime("%H:%M:%S")
                except (ValueError, TypeError):
                    time_str = str(ts)[:8]

                item = QListWidgetItem(f"{cfg['icon']} {time_str} — {message}")
                item.setForeground(QColor(cfg["color"]))
                item.setFont(QFont(Theme.FONT_FAMILY, 9))
                self.history_list.addItem(item)

        except Exception as e:
            logger.error(f"Failed to refresh history: {e}")

    # ---- helpers ----

    @staticmethod
    def _fmt_condition(alert: Dict) -> str:
        atype = alert.get("alert_type", "")
        op = OP_MAP_REV.get(alert.get("condition_op", "gt"), ">")
        threshold = alert.get("threshold", 0)
        coin = alert.get("coin", "")
        network = alert.get("network", "")

        if atype == "spread":
            return f"{coin} spread {op} {threshold}%"
        if atype == "gas":
            return f"{network} gas {op} {threshold} gwei"
        if atype == "funding":
            return f"{coin} |funding| {op} {threshold}%"
        if atype == "price":
            return f"{coin} price {op} ${threshold:,.0f}"
        if atype == "whale":
            return f"{coin} transfer > {threshold:,.0f} coins"
        return "Unknown"

    @staticmethod
    def _action_style(delete: bool = False) -> str:
        if delete:
            return f"""
                QPushButton {{
                    background-color: transparent;
                    color: {Theme.ACCENT_RED};
                    border: 1px solid {Theme.ACCENT_RED};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 9pt;
                }}
                QPushButton:hover {{ background-color: {Theme.ACCENT_RED}; color: #fff; }}
            """
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9pt;
            }}
            QPushButton:hover {{ border-color: {Theme.ACCENT_GREEN}; }}
        """

    # ---- actions ----

    def _show_new_dialog(self):
        try:
            dialog = NewAlertDialog(self.alert_service, self)
            if dialog.exec() == QDialog.Accepted:
                self._refresh_alerts()
        except Exception as e:
            logger.error(f"Error opening alert dialog: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open dialog: {e}")

    def _edit_alert(self, alert_id: int):
        try:
            dialog = NewAlertDialog(self.alert_service, self, alert_id)
            if dialog.exec() == QDialog.Accepted:
                self._refresh_alerts()
        except Exception as e:
            logger.error(f"Error editing alert {alert_id}: {e}")

    def _delete_alert(self, alert_id: int):
        reply = QMessageBox.question(
            self, "Delete Alert", "Delete this alert?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.alert_service.delete_alert(alert_id)
                self._refresh_alerts()
            except Exception as e:
                logger.error(f"Error deleting alert {alert_id}: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def _toggle_alert(self, alert_id: int, enabled: bool):
        try:
            self.alert_service.toggle_alert(alert_id, enabled)
        except Exception as e:
            logger.error(f"Error toggling alert {alert_id}: {e}")

    def _on_alert_triggered(self, alert_info: Dict):
        try:
            self._refresh_history()
        except Exception as e:
            logger.error(f"Error handling triggered alert: {e}")