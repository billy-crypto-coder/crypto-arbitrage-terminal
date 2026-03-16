"""
Settings page for CryptoRadar
"""
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox, QCheckBox,
    QLineEdit, QDialog, QMessageBox, QSizePolicy, QHeaderView
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor

from ui.styles.theme import Theme
from config import settings
from utils.encryption import KeyManager

logger = logging.getLogger(__name__)


class TestConnectionWorker(QThread):
    connection_tested = Signal(bool, str)

    def __init__(self, key_manager: KeyManager, exchange: str,
                 api_key: str, api_secret: str, passphrase: str = ""):
        super().__init__()
        self.key_manager = key_manager
        self.exchange = exchange
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase

    def run(self):
        try:
            success, message = self.key_manager.test_connection(
                self.exchange, self.api_key, self.api_secret, self.passphrase
            )
            self.connection_tested.emit(success, message)
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            self.connection_tested.emit(False, f"Connection test error: {e}")


class APIKeyDialog(QDialog):
    PASSPHRASE_EXCHANGES = frozenset({"okx", "kraken", "kucoin"})

    def __init__(self, key_manager: KeyManager, exchange: str,
                 parent=None, existing_keys: Optional[dict] = None):
        super().__init__(parent)
        self.key_manager = key_manager
        self.exchange = exchange
        self.existing_keys = existing_keys or {}
        self.connection_worker = None

        self.setWindowTitle(
            f"{'Edit' if existing_keys else 'Add'} {exchange.upper()} API Keys"
        )
        self.setMinimumWidth(500)
        self.setMinimumHeight(350)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        lbl_style = f"color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;"
        input_style = f"""
            QLineEdit {{
                background-color: {Theme.BG_PRIMARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 11pt;
            }}
            QLineEdit:focus {{
                border: 1px solid {Theme.ACCENT_GREEN};
            }}
        """

        exchange_label = QLabel(f"Exchange: {self.exchange.upper()}")
        exchange_label.setFont(QFont(Theme.FONT_FAMILY, 12, QFont.Weight.Bold))
        exchange_label.setStyleSheet(lbl_style)
        layout.addWidget(exchange_label)

        self.api_key_input = self._create_secret_row(
            layout, "API Key:", self.existing_keys.get("key", ""),
            input_style, lbl_style
        )

        self.api_secret_input = self._create_secret_row(
            layout, "API Secret:", self.existing_keys.get("secret", ""),
            input_style, lbl_style
        )

        if self.exchange.lower() in self.PASSPHRASE_EXCHANGES:
            self.passphrase_input = self._create_secret_row(
                layout, "Passphrase:", self.existing_keys.get("passphrase", ""),
                input_style, lbl_style
            )
        else:
            self.passphrase_input = None

        self.test_btn = QPushButton("🔗 Test Connection")
        self.test_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.BG_PRIMARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 10pt;
            }}
            QPushButton:hover {{ border-color: {Theme.ACCENT_GREEN}; }}
            QPushButton:disabled {{ color: {Theme.TEXT_SECONDARY}; }}
        """)
        self.test_btn.clicked.connect(self._test_connection)
        layout.addWidget(self.test_btn)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; {lbl_style}")
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.BG_PRIMARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{ border-color: {Theme.ACCENT_RED}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.ACCENT_GREEN};
                color: #000000;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #00e894; }}
        """)
        save_btn.clicked.connect(self._save_keys)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        self.setLayout(layout)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.BG_CARD};
            }}
        """)

    def _create_secret_row(self, parent_layout: QVBoxLayout, label_text: str,
                           initial_value: str, input_style: str,
                           lbl_style: str) -> QLineEdit:
        row = QHBoxLayout()

        label = QLabel(label_text)
        label.setMinimumWidth(90)
        label.setStyleSheet(lbl_style)
        row.addWidget(label)

        field = QLineEdit()
        field.setEchoMode(QLineEdit.Password)
        field.setText(initial_value)
        field.setStyleSheet(input_style)
        row.addWidget(field, 1)

        toggle = QPushButton("👁")
        toggle.setFixedWidth(36)
        toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.BG_PRIMARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                font-size: 12pt;
            }}
            QPushButton:hover {{ border-color: {Theme.ACCENT_GREEN}; }}
        """)
        toggle.clicked.connect(lambda: self._toggle_echo(field, toggle))
        row.addWidget(toggle)

        parent_layout.addLayout(row)
        return field

    @staticmethod
    def _toggle_echo(field: QLineEdit, btn: QPushButton):
        if field.echoMode() == QLineEdit.Password:
            field.setEchoMode(QLineEdit.Normal)
            btn.setText("🙈")
        else:
            field.setEchoMode(QLineEdit.Password)
            btn.setText("👁")

    def _test_connection(self):
        api_key = self.api_key_input.text().strip()
        api_secret = self.api_secret_input.text().strip()
        passphrase = self.passphrase_input.text().strip() if self.passphrase_input else ""

        if not api_key or not api_secret:
            self.status_label.setText("❌ Please enter API key and secret")
            self.status_label.setStyleSheet(f"color: {Theme.ACCENT_RED};")
            return

        self.test_btn.setEnabled(False)
        self.test_btn.setText("⏳ Testing...")
        self.status_label.setText("")

        self.connection_worker = TestConnectionWorker(
            self.key_manager, self.exchange, api_key, api_secret, passphrase
        )
        self.connection_worker.connection_tested.connect(self._on_connection_tested)
        self.connection_worker.finished.connect(self._cleanup_worker)
        self.connection_worker.start()

    def _on_connection_tested(self, success: bool, message: str):
        self.test_btn.setEnabled(True)
        self.test_btn.setText("🔗 Test Connection")
        
        if success:
            self.status_label.setText(f"✅ {message}")
            self.status_label.setStyleSheet(f"color: {Theme.ACCENT_GREEN};")
        else:
            self.status_label.setText(f"❌ {message}")
            self.status_label.setStyleSheet(f"color: {Theme.ACCENT_RED};")

    def _cleanup_worker(self):
        if self.connection_worker:
            self.connection_worker.deleteLater()
            self.connection_worker = None

    def _save_keys(self):
        api_key = self.api_key_input.text().strip()
        api_secret = self.api_secret_input.text().strip()
        passphrase = self.passphrase_input.text().strip() if self.passphrase_input else ""

        if not api_key or not api_secret:
            QMessageBox.warning(self, "Validation Error", "API Key and Secret are required")
            return

        try:
            self.key_manager.save_api_keys(
                self.exchange, api_key, api_secret, passphrase
            )
            self.accept()
        except Exception as e:
            logger.error(f"Failed to save keys for {self.exchange}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save keys: {e}")

    def closeEvent(self, event):
        if self.connection_worker and self.connection_worker.isRunning():
            self.connection_worker.quit()
            self.connection_worker.wait(2000)
        event.accept()


class SettingsPage(QWidget):
    EXCHANGES = ["binance", "bybit", "okx", "bitget", "kraken", "dydx"]

    def __init__(self):
        super().__init__()
        self.key_manager = KeyManager()
        self._init_ui()

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
        layout.setSpacing(16)

        layout.addWidget(self._create_api_keys_section())
        layout.addWidget(self._create_general_section())
        layout.addWidget(self._create_notifications_section())
        layout.addWidget(self._create_about_section())

        layout.addStretch()
        content.setLayout(layout)
        scroll.setWidget(content)
        root.addWidget(scroll)
        self.setLayout(root)

    def _section_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("settingsSection")
        frame.setStyleSheet(f"""
            QFrame#settingsSection {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
            }}
        """)
        return frame

    def _section_header(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont(Theme.FONT_FAMILY, 13, QFont.Weight.Bold))
        lbl.setStyleSheet(
            f"color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;"
        )
        return lbl

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;"
        )
        return lbl

    def _checkbox(self, text: str, checked: bool, section: str, key: str) -> QCheckBox:
        cb = QCheckBox(text)
        cb.setChecked(checked)
        cb.setStyleSheet(f"""
            QCheckBox {{
                color: {Theme.TEXT_PRIMARY};
                background: transparent;
                border: none;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {Theme.BORDER};
                border-radius: 4px;
                background: {Theme.BG_PRIMARY};
            }}
            QCheckBox::indicator:checked {{
                background: {Theme.ACCENT_GREEN};
                border-color: {Theme.ACCENT_GREEN};
            }}
        """)
        cb.stateChanged.connect(
            lambda: settings.set(section, key, cb.isChecked())
        )
        return cb

    def _combo(self, items: list, current: str) -> QComboBox:
        combo = QComboBox()
        combo.addItems(items)
        combo.setCurrentText(current)
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {Theme.BG_PRIMARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                min-width: 100px;
            }}
            QComboBox:hover {{ border-color: {Theme.ACCENT_GREEN}; }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                selection-background-color: {Theme.ACCENT_GREEN};
            }}
        """)
        return combo

    def _action_button(self, text: str, accent: bool = False) -> QPushButton:
        if accent:
            style = f"""
                QPushButton {{
                    background-color: {Theme.ACCENT_GREEN};
                    color: #000;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-weight: bold;
                    font-size: 10pt;
                }}
                QPushButton:hover {{ background-color: #00e894; }}
            """
        else:
            style = f"""
                QPushButton {{
                    background-color: {Theme.BG_PRIMARY};
                    color: {Theme.TEXT_PRIMARY};
                    border: 1px solid {Theme.BORDER};
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-size: 10pt;
                }}
                QPushButton:hover {{ border-color: {Theme.ACCENT_GREEN}; }}
            """
        btn = QPushButton(text)
        btn.setStyleSheet(style)
        btn.setMaximumWidth(100)
        return btn

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def _create_api_keys_section(self) -> QFrame:
        frame = self._section_frame()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(self._section_header("🔑 Exchange API Keys"))

        warning = QFrame()
        warning.setObjectName("warningBanner")
        warning.setStyleSheet(f"""
            QFrame#warningBanner {{
                background-color: {Theme.ACCENT_YELLOW};
                border-radius: 6px;
            }}
        """)
        w_layout = QVBoxLayout()
        w_layout.setContentsMargins(12, 8, 12, 8)
        w_label = QLabel("⚠️ Use READ-ONLY API keys! Never grant withdrawal permissions!")
        w_label.setWordWrap(True)
        w_label.setStyleSheet(
            "color: #000; font-weight: bold; background: transparent; border: none;"
        )
        w_layout.addWidget(w_label)
        warning.setLayout(w_layout)
        layout.addWidget(warning)

        self.api_table = QTableWidget()
        self.api_table.setColumnCount(3)
        self.api_table.setHorizontalHeaderLabels(["Exchange", "Status", "Actions"])
        self.api_table.verticalHeader().setVisible(False)
        self.api_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.api_table.setSelectionMode(QTableWidget.NoSelection)
        self.api_table.verticalHeader().setDefaultSectionSize(44)

        header = self.api_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.api_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Theme.BG_PRIMARY};
                color: {Theme.TEXT_PRIMARY};
                gridline-color: {Theme.BORDER};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
            }}
            QHeaderView::section {{
                background-color: {Theme.BG_CARD};
                color: {Theme.TEXT_SECONDARY};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {Theme.BORDER};
                font-weight: bold;
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
        """)

        self._populate_api_table()
        layout.addWidget(self.api_table)

        frame.setLayout(layout)
        return frame

    def _populate_api_table(self):
        configured = self.key_manager.list_configured_exchanges()
        self.api_table.setRowCount(len(self.EXCHANGES))

        for row, exchange in enumerate(self.EXCHANGES):
            ex_item = QTableWidgetItem(exchange.upper())
            ex_item.setFont(QFont(Theme.FONT_FAMILY, 10, QFont.Weight.Bold))
            ex_item.setForeground(QColor(Theme.TEXT_PRIMARY))
            self.api_table.setItem(row, 0, ex_item)

            is_configured = exchange in configured
            if is_configured:
                status_item = QTableWidgetItem("✅ Connected")
                status_item.setForeground(QColor(Theme.ACCENT_GREEN))
            else:
                status_item = QTableWidgetItem("❌ Not configured")
                status_item.setForeground(QColor(Theme.ACCENT_RED))
            self.api_table.setItem(row, 1, status_item)

            actions = QWidget()
            actions.setStyleSheet("background: transparent; border: none;")
            a_layout = QHBoxLayout()
            a_layout.setContentsMargins(4, 2, 4, 2)
            a_layout.setSpacing(6)

            if is_configured:
                edit_btn = self._action_button("✏ Edit")
                edit_btn.clicked.connect(
                    lambda _, ex=exchange: self._edit_api_keys(ex)
                )
                a_layout.addWidget(edit_btn)

                del_btn = self._action_button("🗑 Delete")
                del_btn.clicked.connect(
                    lambda _, ex=exchange: self._delete_api_keys(ex)
                )
                a_layout.addWidget(del_btn)
            else:
                add_btn = self._action_button("➕ Add", accent=True)
                add_btn.clicked.connect(
                    lambda _, ex=exchange: self._add_api_keys(ex)
                )
                a_layout.addWidget(add_btn)

            a_layout.addStretch()
            actions.setLayout(a_layout)
            self.api_table.setCellWidget(row, 2, actions)

    def _create_general_section(self) -> QFrame:
        frame = self._section_frame()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._section_header("⚙️ General"))

        currency_row = QHBoxLayout()
        currency_row.addWidget(self._label("Display Currency:"))
        current_currency = settings.get("general", "display_currency", "USD")
        self.currency_combo = self._combo(["USD", "EUR", "GBP"], current_currency)
        self.currency_combo.currentTextChanged.connect(
            lambda t: settings.set("general", "display_currency", t)
        )
        currency_row.addWidget(self.currency_combo)
        currency_row.addStretch()
        layout.addLayout(currency_row)

        refresh_row = QHBoxLayout()
        refresh_row.addWidget(self._label("Auto-refresh Interval:"))
        current_refresh = settings.get("general", "auto_refresh_interval", "60")
        refresh_map = {"10": "10s", "30": "30s", "60": "60s", "0": "Off"}
        self.refresh_combo = self._combo(
            ["10s", "30s", "60s", "Off"],
            refresh_map.get(str(current_refresh), "60s")
        )
        self.refresh_combo.currentTextChanged.connect(
            lambda t: settings.set(
                "general", "auto_refresh_interval",
                t.rstrip("s") if t != "Off" else "0"
            )
        )
        refresh_row.addWidget(self.refresh_combo)
        refresh_row.addStretch()
        layout.addLayout(refresh_row)

        layout.addWidget(self._checkbox(
            "Start with Windows",
            settings.get("general", "start_with_windows", False),
            "general", "start_with_windows"
        ))

        layout.addWidget(self._checkbox(
            "Minimize to tray on close",
            settings.get("general", "minimize_to_tray", True),
            "general", "minimize_to_tray"
        ))

        layout.addWidget(self._checkbox(
            "Clipboard Guard enabled",
            settings.get("general", "clipboard_guard_enabled", True),
            "general", "clipboard_guard_enabled"
        ))

        layout.addStretch()
        frame.setLayout(layout)
        return frame

    def _create_notifications_section(self) -> QFrame:
        frame = self._section_frame()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self._section_header("🔔 Notifications"))

        layout.addWidget(self._checkbox(
            "Enable sound notifications",
            settings.get("notifications", "enable_sound", True),
            "notifications", "enable_sound"
        ))

        layout.addWidget(self._checkbox(
            "Enable Windows notifications",
            settings.get("notifications", "enable_windows_notifications", True),
            "notifications", "enable_windows_notifications"
        ))

        layout.addStretch()
        frame.setLayout(layout)
        return frame

    def _create_about_section(self) -> QFrame:
        frame = self._section_frame()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        lbl_style = f"color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;"
        sub_style = f"color: {Theme.TEXT_SECONDARY}; background: transparent; border: none;"

        title = QLabel("CryptoRadar v1.0.0")
        title.setFont(QFont(Theme.FONT_FAMILY, 13, QFont.Weight.Bold))
        title.setStyleSheet(lbl_style)
        layout.addWidget(title)

        desc = QLabel("Open-source crypto arbitrage terminal")
        desc.setStyleSheet(sub_style)
        layout.addWidget(desc)

        github = QLabel(
            f'<a href="https://github.com/billy-crypto-coder/crypto-arbitrage-terminal" '
            f'style="color: {Theme.ACCENT_GREEN}; text-decoration: none;">'
            f'GitHub: billy-crypto-coder/crypto-arbitrage-terminal</a>'
        )
        github.setOpenExternalLinks(True)
        github.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(github)

        license_lbl = QLabel("License: MIT")
        license_lbl.setStyleSheet(sub_style)
        layout.addWidget(license_lbl)

        layout.addStretch()
        frame.setLayout(layout)
        return frame

    # ------------------------------------------------------------------
    # API Key actions
    # ------------------------------------------------------------------

    def _add_api_keys(self, exchange: str):
        dialog = APIKeyDialog(self.key_manager, exchange, self)
        if dialog.exec() == QDialog.Accepted:
            self._populate_api_table()

    def _edit_api_keys(self, exchange: str):
        keys = self.key_manager.get_api_keys(exchange)
        if keys:
            dialog = APIKeyDialog(self.key_manager, exchange, self, keys)
            if dialog.exec() == QDialog.Accepted:
                self._populate_api_table()

    def _delete_api_keys(self, exchange: str):
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete API keys for {exchange.upper()}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.key_manager.delete_api_keys(exchange)
                self._populate_api_table()
            except Exception as e:
                logger.error(f"Failed to delete keys for {exchange}: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete keys: {e}")

    def closeEvent(self, event):
        try:
            settings.save()
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
        event.accept()