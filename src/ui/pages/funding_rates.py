"""
Funding Rates monitoring page — real-time perpetual futures funding data.
"""
from time import time as current_time
from typing import Dict, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QColor, QFont, QBrush

from ui.styles.theme import Theme
from services.funding_service import FundingService

import logging

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Worker
# ------------------------------------------------------------------

class FundingDataWorker(QThread):
    """Background worker thread for fetching funding data."""

    data_fetched = Signal(list, list)   # all_data, arbitrage_opportunities
    error_occurred = Signal(str)

    def __init__(self, service: FundingService):
        super().__init__()
        # Original created a NEW FundingService each time → no cache, leaked sessions.
        self.service = service

    def run(self):
        try:
            all_data = self.service.fetch_all_funding_rates()
            arb_ops = self.service.get_funding_arbitrage()  # uses cached data
            self.data_fetched.emit(all_data, arb_ops)
        except Exception as e:
            logger.error(f"Funding fetch error: {e}")
            self.error_occurred.emit(str(e))


# ------------------------------------------------------------------
# Page
# ------------------------------------------------------------------

class FundingRatesPage(QWidget):
    """Funding rates monitoring page."""

    EXCHANGES_DISPLAY = ["binance", "bybit", "okx", "bitget"]

    def __init__(self):
        super().__init__()
        self.service = FundingService()
        self.all_data: List[Dict] = []
        self.arbitrage_opportunities: List[Dict] = []
        self.next_funding_time: float = 0
        self.worker = None
        self._initialized = False

        # if closeEvent fires before showEvent.
        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.fetch_data)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._update_countdown)

        self._init_ui()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)

        # Original started timers in __init__ — wasted API calls when hidden.
        if not self._initialized:
            self._initialized = True
            self.fetch_data()

        self.data_timer.start(60_000)
        self.countdown_timer.start(1_000)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.data_timer.stop()
        self.countdown_timer.stop()

    def closeEvent(self, event):
        self.data_timer.stop()
        self.countdown_timer.stop()
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            if not self.worker.wait(3000):
                self.worker.terminate()
                self.worker.wait(1000)
        self.service.close()
        event.accept()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)

        # on small windows.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: {Theme.BG_PRIMARY}; border: none; }}
            QScrollBar:vertical {{
                background: {Theme.BG_PRIMARY}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {Theme.BORDER}; border-radius: 4px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        content = QWidget()
        content.setStyleSheet(f"background: {Theme.BG_PRIMARY};")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- Anomaly Banner ---
        self.anomaly_frame = self._create_anomaly_banner()
        layout.addWidget(self.anomaly_frame)

        # --- Countdown ---
        self.countdown_label = QLabel("⏱ Next funding in: --:--:--")
        countdown_font = QFont(Theme.FONT_FAMILY, 12)
        countdown_font.setBold(True)
        self.countdown_label.setFont(countdown_font)
        self.countdown_label.setStyleSheet(
            f"color: {Theme.ACCENT_BLUE if hasattr(Theme, 'ACCENT_BLUE') else '#2196F3'};"
        )
        layout.addWidget(self.countdown_label)

        # --- Status ---
        self.status_label = QLabel("Loading funding rates...")
        self.status_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 10pt;")
        layout.addWidget(self.status_label)

        # --- Main Table ---
        self.table = self._create_table()
        self.table.setMinimumHeight(200)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.table, 1)

        # --- Arbitrage Section ---
        arb_frame = self._create_arbitrage_section()
        layout.addWidget(arb_frame)

        layout.addStretch()
        content.setLayout(layout)
        scroll.setWidget(content)
        root.addWidget(scroll)
        self.setLayout(root)

    def _create_anomaly_banner(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("anomalyBanner")
        frame.setStyleSheet(f"""
            QFrame#anomalyBanner {{
                background-color: {Theme.ACCENT_RED};
                border-radius: 8px;
            }}
        """)
        frame.setVisible(False)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)

        lbl_style = "background: transparent; border: none; color: white;"

        title = QLabel("🚨 Anomalous Funding Detected")
        title.setFont(QFont(Theme.FONT_FAMILY, 11, QFont.Weight.Bold))
        title.setStyleSheet(lbl_style)
        layout.addWidget(title)

        self.anomaly_detail_label = QLabel()
        self.anomaly_detail_label.setWordWrap(True)
        self.anomaly_detail_label.setFont(QFont(Theme.FONT_FAMILY, 10))
        self.anomaly_detail_label.setStyleSheet(lbl_style)
        layout.addWidget(self.anomaly_detail_label)

        frame.setLayout(layout)
        return frame

    def _create_table(self) -> QTableWidget:
        headers = ["Symbol", "Binance", "Bybit", "OKX", "Bitget", "Max Diff", "Signal"]
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for col in range(1, 5):
            header.setSectionResizeMode(col, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)

        table.setStyleSheet(f"""
            QTableWidget {{
                gridline-color: {Theme.BORDER};
                background-color: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
            }}
            QTableWidget::item {{
                padding: 6px;
            }}
            QHeaderView::section {{
                background-color: {Theme.BG_PRIMARY};
                color: {Theme.TEXT_SECONDARY};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {Theme.BORDER};
                font-weight: bold;
            }}
        """)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(38)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)

        return table

    def _create_arbitrage_section(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("arbSection")
        frame.setStyleSheet(f"""
            QFrame#arbSection {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        lbl_style = "background: transparent; border: none;"

        header = QLabel("📈 Funding Arbitrage Opportunities")
        header.setFont(QFont(Theme.FONT_FAMILY, 12, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; {lbl_style}")
        layout.addWidget(header)

        self.arb_container = QVBoxLayout()
        self.arb_container.setSpacing(6)
        layout.addLayout(self.arb_container)

        self.arb_empty_label = QLabel("No arbitrage opportunities detected yet")
        self.arb_empty_label.setStyleSheet(
            f"color: {Theme.TEXT_SECONDARY}; font-style: italic; {lbl_style}"
        )
        self.arb_container.addWidget(self.arb_empty_label)

        frame.setLayout(layout)
        return frame

    # ------------------------------------------------------------------
    # Data Fetching
    # ------------------------------------------------------------------

    def fetch_data(self):
        if self.worker and self.worker.isRunning():
            return

        self.status_label.setText("⏳ Refreshing funding rates...")

        self.worker = FundingDataWorker(self.service)
        self.worker.data_fetched.connect(self._on_data_fetched)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.finished.connect(self._cleanup_worker)
        self.worker.start()

    def _on_data_fetched(self, all_data: List[Dict], arb_ops: List[Dict]):
        self.all_data = all_data
        self.arbitrage_opportunities = arb_ops

        # Extract next funding time from first available data point
        for sym_data in all_data:
            for rate_entry in sym_data.get("rates", {}).values():
                nft = rate_entry.get("next_funding_time", 0)
                if nft > 0:
                    self.next_funding_time = nft / 1000.0  # ms → seconds
                    break
            if self.next_funding_time:
                break

        exchanges_ok = sum(
            1 for s in all_data if s.get("rates")
            for _ in s["rates"]
        )
        self.status_label.setText(
            f"✅ {len(all_data)} symbols loaded, {exchanges_ok} rate entries"
        )

        self._update_anomaly_banner()
        self._populate_table()
        self._populate_arbitrage()
        self._update_countdown()

    def _on_error(self, msg: str):
        logger.error(msg)
        self.status_label.setText(f"❌ {msg}")

    def _cleanup_worker(self):
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    # ------------------------------------------------------------------
    # UI Updates
    # ------------------------------------------------------------------

    def _update_countdown(self):
        if not self.next_funding_time:
            self.countdown_label.setText("⏱ Next funding in: --:--:--")
            return

        remaining = self.next_funding_time - current_time()

        if remaining < 0:
            remaining = remaining % (8 * 3600)

        h = int(remaining // 3600)
        m = int((remaining % 3600) // 60)
        s = int(remaining % 60)
        self.countdown_label.setText(f"⏱ Next funding in: {h:02d}:{m:02d}:{s:02d}")

    def _update_anomaly_banner(self):
        anomalies = [d for d in self.all_data if d.get("is_anomaly")]

        if not anomalies:
            self.anomaly_frame.setVisible(False)
            return

        self.anomaly_frame.setVisible(True)

        parts = []
        for sym_data in anomalies[:3]:
            symbol = sym_data["symbol"]
            ex = sym_data.get("max_rate_exchange", "")
            rates = sym_data.get("rates", {})
            if ex and ex in rates:
                rate = rates[ex]["rate"]
                ann = rates[ex]["annualized"]
                parts.append(
                    f"{symbol} {rate * 100:+.3f}% on {ex.upper()} "
                    f"(ann. {ann:+.1f}%)"
                )

        self.anomaly_detail_label.setText(" | ".join(parts) if parts else "")

    def _populate_table(self):
        sorted_data = sorted(
            self.all_data,
            key=lambda x: x.get("max_diff", 0),
            reverse=True,
        )

        self.table.setRowCount(len(sorted_data))

        for row, sym_data in enumerate(sorted_data):
            symbol = sym_data["symbol"]
            rates = sym_data.get("rates", {})
            max_diff = sym_data.get("max_diff", 0)
            is_anomaly = sym_data.get("is_anomaly", False)

            # Column 0: Symbol
            sym_item = QTableWidgetItem(symbol)
            sym_item.setFont(QFont(Theme.FONT_FAMILY, 10, QFont.Weight.Bold))
            sym_item.setForeground(QBrush(QColor(Theme.TEXT_PRIMARY)))
            self.table.setItem(row, 0, sym_item)

            # Columns 1-4: Exchange rates
            for col, exchange in enumerate(self.EXCHANGES_DISPLAY, start=1):
                if exchange in rates:
                    item = self._make_rate_cell(rates[exchange])
                else:
                    item = QTableWidgetItem("—")
                    item.setForeground(QBrush(QColor(Theme.TEXT_SECONDARY)))
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)

            # Column 5: Max Diff
            diff_item = QTableWidgetItem(f"{max_diff * 100:.4f}%")
            diff_item.setTextAlignment(Qt.AlignCenter)
            diff_item.setForeground(QBrush(QColor(Theme.TEXT_PRIMARY)))
            if max_diff > 0.0002:
                diff_item.setFont(QFont(Theme.FONT_FAMILY, 10, QFont.Weight.Bold))
                diff_item.setBackground(QBrush(QColor(Theme.ACCENT_YELLOW)))
            self.table.setItem(row, 5, diff_item)

            # Column 6: Signal
            signal_item = self._make_signal_cell(is_anomaly, max_diff)
            self.table.setItem(row, 6, signal_item)

    def _make_rate_cell(self, rate_data: Dict) -> QTableWidgetItem:
        """Create a styled table cell for a funding rate."""
        rate = rate_data["rate"]
        text = rate_data["rate_pct"]
        abs_rate = abs(rate)

        item = QTableWidgetItem()
        item.setTextAlignment(Qt.AlignCenter)

        if abs_rate > 0.001:       # > 0.1% — extreme
            item.setText(f"🚨 {text}")
            item.setFont(QFont(Theme.FONT_FAMILY, 10, QFont.Weight.Bold))
            if rate > 0:
                item.setForeground(QBrush(QColor(Theme.ACCENT_RED)))
            else:
                item.setForeground(QBrush(QColor(Theme.ACCENT_GREEN)))

        elif abs_rate > 0.0005:    # > 0.05% — elevated
            item.setText(f"🔥 {text}")
            item.setFont(QFont(Theme.FONT_FAMILY, 10, QFont.Weight.Bold))
            if rate > 0:
                item.setForeground(QBrush(QColor("#FF5722")))
            else:
                item.setForeground(QBrush(QColor("#00897B")))

        else:                       # normal
            item.setText(text)
            if rate > 0:
                item.setForeground(QBrush(QColor("#EF9A9A")))   # light red
            elif rate < 0:
                item.setForeground(QBrush(QColor("#A5D6A7")))   # light green
            else:
                item.setForeground(QBrush(QColor(Theme.TEXT_SECONDARY)))

        return item

    @staticmethod
    def _make_signal_cell(is_anomaly: bool, max_diff: float) -> QTableWidgetItem:
        """Create the Signal column cell."""
        if is_anomaly:
            item = QTableWidgetItem("HIGH FUNDING 🔥")
            item.setForeground(QBrush(QColor("#E65100")))
            item.setFont(QFont(Theme.FONT_FAMILY, 9, QFont.Weight.Bold))
        elif max_diff > 0.0002:
            item = QTableWidgetItem("ARB ⚡")
            item.setForeground(QBrush(QColor(Theme.ACCENT_GREEN)))
            item.setFont(QFont(Theme.FONT_FAMILY, 9, QFont.Weight.Bold))
        else:
            item = QTableWidgetItem("NORMAL")
            item.setForeground(QBrush(QColor(Theme.TEXT_SECONDARY)))

        item.setTextAlignment(Qt.AlignCenter)
        return item

    def _populate_arbitrage(self):
        """Rebuild arbitrage cards."""
        while self.arb_container.count():
            item = self.arb_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self.arbitrage_opportunities:
            empty = QLabel("No arbitrage opportunities detected yet")
            empty.setStyleSheet(
                f"color: {Theme.TEXT_SECONDARY}; font-style: italic; "
                "background: transparent; border: none;"
            )
            self.arb_container.addWidget(empty)
            return

        for opp in self.arbitrage_opportunities[:8]:
            card = self._make_arb_card(opp)
            self.arb_container.addWidget(card)

    def _make_arb_card(self, opp: Dict) -> QFrame:
        """Create a single arbitrage opportunity card."""
        card = QFrame()
        card.setObjectName("arbCard")
        card.setStyleSheet(f"""
            QFrame#arbCard {{
                background-color: {Theme.BG_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
            }}
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        lbl_style = "background: transparent; border: none;"

        symbol = opp["symbol"]
        long_ex = opp["long_exchange"].upper()
        short_ex = opp["short_exchange"].upper()
        diff = opp["diff_pct"]
        ann = opp["annualized_profit_pct"]

        title = QLabel(f"<b>{symbol}</b>: Long {long_ex} / Short {short_ex}")
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; {lbl_style}")
        layout.addWidget(title)

        detail = QLabel(f"Diff: {diff:+.4f}% per 8h  •  ~{ann:.1f}% annualized")
        detail.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 10pt; {lbl_style}")
        layout.addWidget(detail)

        card.setLayout(layout)
        return card