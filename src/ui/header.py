"""
Header bar component for CryptoRadar
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QDateTime, Signal
from PySide6.QtGui import QFont

from ui.styles.theme import Theme


class Header(QWidget):
    """Header bar showing page title, status, clock, and controls."""

    minimize_clicked = Signal()

    def __init__(self):
        super().__init__()
        self._connected = True
        self._init_ui()
        self._start_clock()

    def _init_ui(self):
        self.setFixedHeight(48)
        self.setObjectName("headerBar")
        self.setStyleSheet(f"""
            QWidget#headerBar {{
                background-color: {Theme.BG_SECONDARY};
                border-bottom: 1px solid {Theme.BORDER};
            }}
        """)

        lbl_style = "background: transparent; border: none;"

        layout = QHBoxLayout()
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(12)

        # ---- Left: title + breadcrumb ----
        self.title_label = QLabel("Spread Scanner")
        self.title_label.setFont(QFont(Theme.FONT_FAMILY, 13, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; {lbl_style}")
        layout.addWidget(self.title_label)

        self.breadcrumb_label = QLabel("Home › Spread Scanner")
        self.breadcrumb_label.setFont(QFont(Theme.FONT_FAMILY, 9))
        self.breadcrumb_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; {lbl_style}")
        layout.addWidget(self.breadcrumb_label)

        layout.addStretch()

        # ---- Right: status, clock, minimize ----
        self.status_dot = QLabel("●")
        self.status_dot.setFixedWidth(14)
        self.status_dot.setAlignment(Qt.AlignCenter)
        self.status_dot.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; font-size: 10px; {lbl_style}")
        layout.addWidget(self.status_dot)

        self.status_label = QLabel("Connected")
        self.status_label.setFont(QFont(Theme.FONT_FAMILY, 9))
        self.status_label.setStyleSheet(f"color: {Theme.ACCENT_GREEN}; {lbl_style}")
        layout.addWidget(self.status_label)

        sep = QLabel("│")
        sep.setStyleSheet(f"color: {Theme.BORDER}; {lbl_style}")
        layout.addWidget(sep)

        self.clock_label = QLabel("UTC 00:00:00")
        self.clock_label.setFont(QFont(Theme.FONT_FAMILY, 9))
        self.clock_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; {lbl_style}")
        self.clock_label.setMinimumWidth(78)
        layout.addWidget(self.clock_label)

        self.minimize_btn = QPushButton("—")
        self.minimize_btn.setFixedSize(30, 30)
        self.minimize_btn.setToolTip("Minimize to tray (Ctrl+Shift+C)")
        self.minimize_btn.setCursor(Qt.PointingHandCursor)
        self.minimize_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.TEXT_SECONDARY};
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_HOVER if hasattr(Theme, 'BG_HOVER') else '#2a2a35'};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        self.minimize_btn.clicked.connect(self.minimize_clicked.emit)
        layout.addWidget(self.minimize_btn)

        self.setLayout(layout)

    def _start_clock(self):
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self):
        utc = QDateTime.currentDateTimeUtc().toString("hh:mm:ss")
        self.clock_label.setText(f"UTC {utc}")

    def set_page_title(self, title: str, breadcrumb: str = ""):
        self.title_label.setText(title)
        self.breadcrumb_label.setText(breadcrumb or f"Home › {title}")

    def set_connection_status(self, connected: bool):
        self._connected = connected
        color = Theme.ACCENT_GREEN if connected else Theme.ACCENT_RED
        text = "Connected" if connected else "Disconnected"
        base = "background: transparent; border: none;"
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 10px; {base}")
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; {base}")

    def hideEvent(self, event):
        self._clock_timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._clock_timer.isActive():
            self._clock_timer.start(1000)
            self._update_clock()

    def closeEvent(self, event):
        self._clock_timer.stop()
        super().closeEvent(event)