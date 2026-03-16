"""
Gas Monitor page - Real-time blockchain gas fee monitoring
"""
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QSpacerItem, QSizePolicy, QTableWidgetItem, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, Slot, QDateTime
from PySide6.QtGui import QFont, QColor, QBrush, QResizeEvent
import pyqtgraph as pg
import numpy as np
import logging

from ui.widgets.data_table import DataTable
from ui.styles.theme import Theme
from services.gas_service import GasService

logger = logging.getLogger(__name__)


class GasFetchWorker(QThread):
    """Worker thread for fetching gas data without blocking UI."""

    data_fetched = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, gas_service: GasService):
        super().__init__()
        self.gas_service = gas_service

    def run(self):
        try:
            gas_data = self.gas_service.fetch_all_gas()
            self.data_fetched.emit(gas_data)
        except Exception as e:
            logger.error(f"Error fetching gas data: {e}")
            self.error_occurred.emit(f"Error fetching gas data: {str(e)}")


class NetworkCard(QFrame):
    """Network card widget showing gas info and sparkline chart."""

    def __init__(self, network_data: dict = None):
        super().__init__()
        self.network_data = network_data or {}
        self.sparkline_plot = None

        self.setObjectName("networkCard")
        self.setup_ui()

    def setup_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            QFrame#networkCard {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
            }}
        """)

        # Минимальный размер карточки чтобы текст не схлопывался
        self.setMinimumWidth(200)
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        label_style = "background: transparent; border: none;"

        # Network name
        network_name = self.network_data.get("network", "Unknown")
        icon = self.network_data.get("icon", "?")
        self.name_label = QLabel(f"{icon} {network_name}")
        name_font = QFont(Theme.FONT_FAMILY, 11)
        name_font.setBold(True)
        self.name_label.setFont(name_font)
        self.name_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; {label_style}")
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        # Gas price
        gas_price = self.network_data.get("gas_price_native", "—")
        self.gas_price_label = QLabel(f"Gas: {gas_price}")
        gas_font = QFont(Theme.FONT_FAMILY, 14)
        self.gas_price_label.setFont(gas_font)
        self.gas_price_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; {label_style}")
        self.gas_price_label.setWordWrap(True)
        layout.addWidget(self.gas_price_label)

        # USDT transfer cost
        usdt_cost = self.network_data.get("usdt_transfer_usd", 0)
        usdt_text = f"USDT: ${usdt_cost:.4f}" if usdt_cost > 0 else "USDT: —"
        self.usdt_label = QLabel(usdt_text)
        self.usdt_label.setStyleSheet(
            f"color: {Theme.TEXT_SECONDARY}; font-size: 10pt; {label_style}"
        )
        self.usdt_label.setWordWrap(True)
        layout.addWidget(self.usdt_label)

        # Speed
        speed = self.network_data.get("speed", "—")
        self.speed_label = QLabel(f"Speed: {speed}")
        self.speed_label.setStyleSheet(
            f"color: {Theme.TEXT_SECONDARY}; font-size: 10pt; {label_style}"
        )
        layout.addWidget(self.speed_label)

        # Load indicator
        congestion = self.network_data.get("congestion", "unknown")
        load_color = self._get_load_color(congestion)
        self.load_label = QLabel()
        self.load_label.setTextFormat(Qt.RichText)
        self.load_label.setText(
            f"<span style='color: {load_color};'>●</span> {congestion.title()}"
        )
        self.load_label.setStyleSheet(
            f"color: {Theme.TEXT_SECONDARY}; font-size: 10pt; {label_style}"
        )
        layout.addWidget(self.load_label)

        # Sparkline
        self.sparkline_frame = QFrame()
        self.sparkline_frame.setObjectName("sparklineFrame")
        self.sparkline_frame.setFixedHeight(36)
        self.sparkline_frame.setStyleSheet(
            "QFrame#sparklineFrame { background: transparent; border: none; }"
        )
        layout.addWidget(self.sparkline_frame)

        self.setLayout(layout)

    def _get_load_color(self, congestion: str) -> str:
        if congestion == "low":
            return Theme.ACCENT_GREEN
        elif congestion == "medium":
            return Theme.ACCENT_YELLOW
        elif congestion == "high":
            return Theme.ACCENT_RED
        return Theme.TEXT_SECONDARY

    def update_data(self, network_data: dict, history_data: list = None):
        self.network_data = network_data

        network_name = network_data.get("network", "Unknown")
        icon = network_data.get("icon", "?")
        self.name_label.setText(f"{icon} {network_name}")

        gas_price = network_data.get("gas_price_native", "—")
        self.gas_price_label.setText(f"Gas: {gas_price}")

        usdt_cost = network_data.get("usdt_transfer_usd", 0)
        self.usdt_label.setText(
            f"USDT: ${usdt_cost:.4f}" if usdt_cost > 0 else "USDT: —"
        )

        speed = network_data.get("speed", "—")
        self.speed_label.setText(f"Speed: {speed}")

        congestion = network_data.get("congestion", "unknown")
        load_color = self._get_load_color(congestion)
        self.load_label.setText(
            f"<span style='color: {load_color};'>●</span> {congestion.title()}"
        )

        if history_data and len(history_data) > 1:
            self._update_sparkline(history_data)

    def _update_sparkline(self, history_data: list):
        prices = []
        for data in history_data[-60:]:
            if not data.get("stale", False):
                price = data.get("gas_price_gwei", 0)
                if price > 0:
                    prices.append(price)

        if len(prices) < 2:
            return

        if self.sparkline_plot is None:
            self.sparkline_plot = pg.PlotWidget()
            self.sparkline_plot.setBackground("transparent")
            self.sparkline_plot.setFixedHeight(36)
            self.sparkline_plot.hideAxis("left")
            self.sparkline_plot.hideAxis("bottom")
            self.sparkline_plot.setMouseEnabled(False, False)
            self.sparkline_plot.setMenuEnabled(False)
            self.sparkline_plot.getViewBox().setDefaultPadding(0)

            sparkline_layout = QVBoxLayout()
            sparkline_layout.setContentsMargins(0, 0, 0, 0)
            sparkline_layout.addWidget(self.sparkline_plot)
            self.sparkline_frame.setLayout(sparkline_layout)

        self.sparkline_plot.clear()

        x = np.arange(len(prices))
        y = np.array(prices, dtype=float)

        pen = pg.mkPen(color=Theme.ACCENT_GREEN, width=2)
        self.sparkline_plot.plot(x, y, pen=pen)

        y_min, y_max = float(np.min(y)), float(np.max(y))
        y_range = y_max - y_min
        if y_range > 0:
            padding = y_range * 0.1
            self.sparkline_plot.setYRange(y_min - padding, y_max + padding)
        else:
            self.sparkline_plot.setYRange(y_min - 1, y_max + 1)


class GasMonitorPage(QWidget):
    """Gas Monitor page for blockchain gas fee monitoring."""

    NETWORK_IDS = [
        "ethereum", "bsc", "polygon", "arbitrum",
        "optimism", "avalanche", "solana", "tron",
    ]

    # Порог ширины: ниже — 1 колонка, выше — 2 колонки
    SINGLE_COLUMN_THRESHOLD = 500

    def __init__(self):
        super().__init__()
        self.gas_service = GasService()
        self.current_gas_data = []
        self.fetch_worker = None
        self.last_update_time = None
        self._initialized = False
        self._current_columns = 2

        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.timeout.connect(self.fetch_data)

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_elapsed_time)

        self.setup_ui()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initialized:
            self._initialized = True
            self.fetch_data()
        self.auto_refresh_timer.start(15_000)
        self.update_timer.start(1_000)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.auto_refresh_timer.stop()
        self.update_timer.stop()

    def closeEvent(self, event):
        self.auto_refresh_timer.stop()
        self.update_timer.stop()
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.quit()
            if not self.fetch_worker.wait(3000):
                logger.warning("Gas fetch worker did not finish in time")
                self.fetch_worker.terminate()
                self.fetch_worker.wait(1000)
        event.accept()

    def resizeEvent(self, event: QResizeEvent):
        """Перестраиваем сетку карточек при изменении размера окна."""
        super().resizeEvent(event)
        new_width = event.size().width()

        desired_columns = 1 if new_width < self.SINGLE_COLUMN_THRESHOLD else 2

        if desired_columns != self._current_columns:
            self._current_columns = desired_columns
            self._rebuild_cards_grid()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def setup_ui(self):
        # Корневой layout для страницы
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # === SCROLL AREA — главный фикс для маленьких окон ===
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {Theme.BG_PRIMARY};
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {Theme.BG_PRIMARY};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {Theme.BORDER};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        # Контейнер внутри scroll area
        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background-color: {Theme.BG_PRIMARY};")

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        # --- Top banner ---
        self.banner_frame = self._create_top_banner()
        content_layout.addWidget(self.banner_frame)

        # --- Network cards ---
        self.cards_container = QWidget()
        self.cards_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.network_cards: list[NetworkCard] = []
        for _ in self.NETWORK_IDS:
            card = NetworkCard()
            self.network_cards.append(card)

        self._rebuild_cards_grid()
        content_layout.addWidget(self.cards_container)

        # --- Comparison table ---
        self.comparison_table = DataTable([
            "Network", "Gas Price", "USDT Send", "ETH Send", "Speed", "Load"
        ])
        self.comparison_table.setMinimumHeight(120)
        self.comparison_table.setMaximumHeight(400)
        self.comparison_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        content_layout.addWidget(self.comparison_table)

        content_layout.addStretch()
        scroll_content.setLayout(content_layout)
        self.scroll_area.setWidget(scroll_content)

        root_layout.addWidget(self.scroll_area)
        self.setLayout(root_layout)

    def _rebuild_cards_grid(self):
        """Пересобрать сетку карточек под текущее кол-во колонок."""
        # Удаляем старый layout если есть
        old_layout = self.cards_container.layout()
        if old_layout is not None:
            # Убираем все виджеты из layout (не удаляя их!)
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)

            # Удаляем сам layout
            QWidget().setLayout(old_layout)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        cols = self._current_columns
        for i, card in enumerate(self.network_cards):
            row = i // cols
            col = i % cols
            grid.addWidget(card, row, col)

        self.cards_container.setLayout(grid)

    def _create_top_banner(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("gasBanner")
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet(f"""
            QFrame#gasBanner {{
                background-color: {Theme.BG_CARD};
                border: 2px solid {Theme.ACCENT_GREEN};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)

        label_style = "background: transparent; border: none;"

        self.banner_label = QLabel("💡 Cheapest USDT transfer: Loading...")
        banner_font = QFont(Theme.FONT_FAMILY, 10)
        self.banner_label.setFont(banner_font)
        self.banner_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; {label_style}")
        self.banner_label.setWordWrap(True)
        self.banner_label.setMinimumHeight(20)
        layout.addWidget(self.banner_label, 1)

        self.elapsed_label = QLabel("")
        self.elapsed_label.setStyleSheet(
            f"color: {Theme.TEXT_SECONDARY}; font-size: 9pt; {label_style}"
        )
        self.elapsed_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.elapsed_label, 0)

        frame.setLayout(layout)
        # Минимальная высота вместо фиксированной — растягивается под текст
        frame.setMinimumHeight(40)
        frame.setMaximumHeight(70)

        return frame

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def fetch_data(self):
        if self.fetch_worker and self.fetch_worker.isRunning():
            return

        self.banner_label.setText("💡 Cheapest USDT transfer: Loading...")

        self.fetch_worker = GasFetchWorker(self.gas_service)
        self.fetch_worker.data_fetched.connect(self._on_data_fetched)
        self.fetch_worker.error_occurred.connect(self._on_fetch_error)
        self.fetch_worker.finished.connect(self._cleanup_worker)
        self.fetch_worker.start()

    @Slot(list)
    def _on_data_fetched(self, gas_data: list):
        self.current_gas_data = gas_data
        self.last_update_time = QDateTime.currentDateTime()

        self._update_top_banner()
        self._update_network_cards()
        self._update_comparison_table()

    @Slot(str)
    def _on_fetch_error(self, error: str):
        logger.error(error)
        self.banner_label.setText(f"❌ {error}")

    def _cleanup_worker(self):
        if self.fetch_worker:
            self.fetch_worker.deleteLater()
            self.fetch_worker = None

    # ------------------------------------------------------------------
    # UI Updates
    # ------------------------------------------------------------------

    def _update_elapsed_time(self):
        if self.last_update_time:
            seconds_ago = self.last_update_time.secsTo(QDateTime.currentDateTime())
            self.elapsed_label.setText(f"{seconds_ago}s ago")

    def _update_top_banner(self):
        if not self.current_gas_data:
            return

        valid = [
            d for d in self.current_gas_data
            if not d.get("stale", False) and d.get("usdt_transfer_usd", 0) > 0
        ]

        if not valid:
            self.banner_label.setText("❌ No gas data available")
            return

        cheapest = min(valid, key=lambda x: x.get("usdt_transfer_usd", float("inf")))
        network = cheapest.get("network", "Unknown")
        cost = cheapest.get("usdt_transfer_usd", 0)
        speed = cheapest.get("speed", "—")
        self.banner_label.setText(
            f"💡 Cheapest USDT transfer: {network} — ${cost:.4f} (~{speed})"
        )

    def _update_network_cards(self):
        for i, network_id in enumerate(self.NETWORK_IDS):
            if i >= len(self.network_cards):
                break

            card = self.network_cards[i]

            network_data = next(
                (d for d in self.current_gas_data
                 if d.get("network", "").lower() == network_id),
                None,
            )

            if network_data:
                history = self.gas_service.get_history(network_id)
                card.update_data(network_data, history)
            else:
                card.update_data({
                    "network": network_id.title(),
                    "icon": "?",
                    "gas_price_native": "—",
                    "usdt_transfer_usd": 0,
                    "speed": "—",
                    "congestion": "unknown",
                })

    def _update_comparison_table(self):
        if not self.current_gas_data:
            return

        rows = []
        for data in self.current_gas_data:
            if data.get("stale", False):
                continue

            network = data.get("network", "Unknown")
            gas_price = data.get("gas_price_native", "—")

            usdt_send = data.get("usdt_transfer_usd", 0)
            usdt_text = f"${usdt_send:.4f}" if usdt_send > 0 else "—"

            native_send = data.get("native_transfer_usd", 0)
            native_text = f"${native_send:.4f}" if native_send > 0 else "—"

            speed = data.get("speed", "—")
            congestion = data.get("congestion", "unknown").title()

            rows.append([network, gas_price, usdt_text, native_text, speed, congestion])

        rows.sort(
            key=lambda x: float(x[2].replace("$", "")) if x[2] != "—" else float("inf")
        )

        logger.info(f"Updating comparison table with {len(rows)} networks")
        self.comparison_table.set_data(rows)

        if rows and rows[0][2] != "—":
            self.comparison_table.highlight_row(0, Theme.ACCENT_GREEN)