"""
Spread Scanner page - Real-time arbitrage opportunity scanner
"""
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel,
    QFrame, QLineEdit, QSpacerItem, QSizePolicy, QTableWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, Slot, QDateTime
from PySide6.QtGui import QFont, QColor, QBrush
import logging

from ui.widgets.stat_card import StatCard
from ui.widgets.data_table import DataTable
from ui.styles.theme import Theme
from services.exchange_service import ExchangeService
from utils.crypto_utils import (
    get_trading_fee, get_withdraw_fee, calculate_net_profit,
    EXCHANGE_FEES
)

logger = logging.getLogger(__name__)


class DataFetchWorker(QThread):
    """Worker thread for fetching exchange data without blocking UI."""
    
    data_fetched = Signal(dict)  # Emits dict with tickers and spread data
    error_occurred = Signal(str)  # Emits error message
    
    def __init__(self, exchange_service: ExchangeService, symbol: str):
        super().__init__()
        self.exchange_service = exchange_service
        self.symbol = symbol
    
    def run(self):
        """Run in background thread."""
        try:
            # Fetch all tickers
            tickers = self.exchange_service.fetch_all_tickers_sync(self.symbol)
            
            if not tickers:
                self.error_occurred.emit(f"No ticker data available for {self.symbol}")
                return
            
            # Get best spread
            spread_data = self.exchange_service.get_best_spread_sync(self.symbol)
            
            self.data_fetched.emit({
                "tickers": tickers,
                "spread_data": spread_data,
                "symbol": self.symbol,
                "timestamp": QDateTime.currentDateTime().toString("hh:mm:ss")
            })
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            self.error_occurred.emit(f"Error fetching data: {str(e)}")


class SpreadScannerPage(QWidget):
    """Spread Scanner page for price arbitrage scanning."""
    
    SUPPORTED_SYMBOLS = [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
        "ADA/USDT", "AVAX/USDT", "MATIC/USDT", "DOT/USDT", "LINK/USDT",
        "UNI/USDT", "ATOM/USDT", "ARB/USDT", "OP/USDT", "PEPE/USDT", "WLD/USDT"
    ]
    
    def __init__(self):
        super().__init__()
        self.exchange_service = ExchangeService()
        self.current_tickers = []
        self.current_spread_data = None
        self.fetch_worker = None
        self.last_update_time = None
        self.update_seconds = 0
        
        self.setup_ui()
        self.setup_timers()
    
    def setup_ui(self):
        """Setup Spread Scanner UI."""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # ===== TOP BAR =====
        top_bar = self._create_top_bar()
        main_layout.addLayout(top_bar)
        
        # ===== BEST OPPORTUNITY CARD =====
        self.opportunity_card = self._create_opportunity_card()
        main_layout.addWidget(self.opportunity_card)
        
        # ===== SPREAD TABLE =====
        self.spread_table = DataTable([
            "#", "Exchange", "Bid", "Ask", "Spread %", "Volume 24h", "Status"
        ])
        self.spread_table.setMaximumHeight(280)  # Limit height to ~6-7 rows
        self.spread_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        main_layout.addWidget(self.spread_table, 0)  # Don't stretch
        
        # ===== PROFIT CALCULATOR =====
        profit_calc = self._create_profit_calculator()
        main_layout.addWidget(profit_calc, 0)  # Don't stretch
        
        # Add stretch to push everything to top
        main_layout.addStretch()
        self.setLayout(main_layout)
        self.setStyleSheet(f"QWidget {{ background-color: {Theme.BG_PRIMARY}; }}")
    
    def _create_top_bar(self) -> QHBoxLayout:
        """Create top control bar."""
        layout = QHBoxLayout()
        layout.setSpacing(12)
        
        # Coin selector
        self.coin_combo = QComboBox()
        self.coin_combo.addItems(self.SUPPORTED_SYMBOLS)
        self.coin_combo.setCurrentText("BTC/USDT")
        self.coin_combo.setFixedWidth(150)
        self.coin_combo.currentTextChanged.connect(self.on_coin_changed)
        layout.addWidget(self.coin_combo)
        
        # Refresh button
        self.refresh_btn = QPushButton("↻ Refresh")
        self.refresh_btn.setFixedWidth(120)
        self.refresh_btn.clicked.connect(self.fetch_data)
        layout.addWidget(self.refresh_btn)
        
        # Last update label
        self.last_update_label = QLabel("Last update: never")
        self.last_update_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
        layout.addWidget(self.last_update_label)
        
        layout.addSpacing(20)
        
        # Auto-refresh label and combo
        auto_label = QLabel("Auto-refresh:")
        auto_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(auto_label)
        
        self.auto_refresh_combo = QComboBox()
        self.auto_refresh_combo.addItems(["Off", "10s", "30s", "60s"])
        self.auto_refresh_combo.setCurrentText("30s")
        self.auto_refresh_combo.setFixedWidth(80)
        self.auto_refresh_combo.currentTextChanged.connect(self.on_auto_refresh_changed)
        layout.addWidget(self.auto_refresh_combo)
        
        layout.addStretch()
        return layout
    
    def _create_opportunity_card(self) -> QFrame:
        """Create best opportunity card."""
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        
        self.opportunity_label = QLabel("🔥 Loading...")
        opportunity_font = QFont(Theme.FONT_FAMILY, 11)
        self.opportunity_label.setFont(opportunity_font)
        self.opportunity_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        self.opportunity_label.setWordWrap(True)
        
        layout.addWidget(self.opportunity_label)
        card.setLayout(layout)
        card.setFixedHeight(50)
        
        return card
    
    def _create_profit_calculator(self) -> QFrame:
        """Create profit calculator section."""
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("💰 Profit Calculator")
        title_font = QFont(Theme.FONT_FAMILY, 12)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(title)
        
        # Input controls
        input_layout = QHBoxLayout()
        input_layout.setSpacing(12)
        
        # Amount input
        amount_label = QLabel("Amount:")
        amount_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        input_layout.addWidget(amount_label)
        
        self.amount_input = QLineEdit()
        self.amount_input.setText("10000")
        self.amount_input.setFixedWidth(120)
        self.amount_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Theme.BG_PRIMARY};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 4px;
            }}
        """)
        self.amount_input.textChanged.connect(self.on_calculator_changed)
        input_layout.addWidget(self.amount_input)
        
        usdt_label = QLabel("USDT")
        usdt_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
        input_layout.addWidget(usdt_label)
        
        input_layout.addSpacing(20)
        
        # Buy on combo
        buy_label = QLabel("Buy on:")
        buy_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        input_layout.addWidget(buy_label)
        
        self.buy_exchange_combo = QComboBox()
        self.buy_exchange_combo.setFixedWidth(120)
        self.buy_exchange_combo.currentTextChanged.connect(self.on_calculator_changed)
        input_layout.addWidget(self.buy_exchange_combo)
        
        input_layout.addSpacing(20)
        
        # Sell on combo
        sell_label = QLabel("Sell on:")
        sell_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        input_layout.addWidget(sell_label)
        
        self.sell_exchange_combo = QComboBox()
        self.sell_exchange_combo.setFixedWidth(120)
        self.sell_exchange_combo.currentTextChanged.connect(self.on_calculator_changed)
        input_layout.addWidget(self.sell_exchange_combo)
        
        input_layout.addStretch()
        layout.addLayout(input_layout)
        
        # Results
        results_layout = QVBoxLayout()
        results_layout.setSpacing(4)
        
        self.result_labels = {}
        for key, label_text in [
            ("gross_spread", "Gross spread:"),
            ("buy_fee", "Buy fee:"),
            ("sell_fee", "Sell fee:"),
            ("withdraw_fee", "Withdrawal fee:"),
        ]:
            label = QLabel(f"{label_text} --")
            label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 9pt;")
            self.result_labels[key] = label
            results_layout.addWidget(label)
        
        # Separator
        sep = QLabel("―" * 40)
        sep.setStyleSheet(f"color: {Theme.BORDER};")
        results_layout.addWidget(sep)
        
        # Net profit
        self.net_profit_label = QLabel("NET PROFIT: --")
        net_font = QFont(Theme.FONT_FAMILY, 11)
        net_font.setBold(True)
        self.net_profit_label.setFont(net_font)
        self.net_profit_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
        results_layout.addWidget(self.net_profit_label)
        
        layout.addLayout(results_layout)
        card.setLayout(layout)
        
        return card
    
    def setup_timers(self):
        """Setup timers for auto-refresh and UI updates."""
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.fetch_data)
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.on_update_timer)
        self.update_timer.start(1000)  # Update every second
    
    def on_update_timer(self):
        """Update last update time display."""
        if self.last_update_time:
            current = QDateTime.currentDateTime()
            seconds_ago = self.last_update_time.secsTo(current)
            self.last_update_label.setText(f"Last update: {seconds_ago}s ago")
    
    def on_coin_changed(self, symbol: str):
        """Handle coin symbol change."""
        self.fetch_data()
    
    def on_auto_refresh_changed(self, value: str):
        """Handle auto-refresh interval change."""
        self.auto_refresh_timer.stop()
        
        if value == "Off":
            self.update_seconds = 0
        elif value == "10s":
            self.update_seconds = 10000
        elif value == "30s":
            self.update_seconds = 30000
        elif value == "60s":
            self.update_seconds = 60000
        
        if self.update_seconds > 0:
            self.auto_refresh_timer.start(self.update_seconds)
    
    def fetch_data(self):
        """Fetch data from exchanges in background thread."""
        if self.fetch_worker and self.fetch_worker.isRunning():
            return  # Don't start if already fetching
        
        symbol = self.coin_combo.currentText()
        
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("↻ Fetching...")
        
        self.fetch_worker = DataFetchWorker(self.exchange_service, symbol)
        self.fetch_worker.data_fetched.connect(self.on_data_fetched)
        self.fetch_worker.error_occurred.connect(self.on_fetch_error)
        self.fetch_worker.finished.connect(self.on_fetch_finished)
        self.fetch_worker.start()
    
    @Slot(dict)
    def on_data_fetched(self, data: dict):
        """Handle fetched data."""
        self.current_tickers = data.get("tickers", [])
        self.current_spread_data = data.get("spread_data")
        self.last_update_time = QDateTime.currentDateTime()
        
        self._update_opportunity_card()
        self._update_spread_table()
        self._update_calculator_exchanges()
        self._update_profit_calculator()
    
    @Slot(str)
    def on_fetch_error(self, error: str):
        """Handle fetch error - show demo data."""
        logger.error(error)
        
        # Load demo data for testing UI
        self._load_demo_data()
    
    def _load_demo_data(self):
        """Load sample demo data for UI testing."""
        # Demo tickers from 8 exchanges
        demo_tickers = [
            {"exchange": "binance", "symbol": "BTC/USDT", "bid": 67495.00, "ask": 67500.00, "last": 67498.50, "volume_24h_usd": 2500000000, "timestamp": int(time.time() * 1000)},
            {"exchange": "coinbase", "symbol": "BTC/USDT", "bid": 67490.00, "ask": 67510.00, "last": 67500.25, "volume_24h_usd": 1800000000, "timestamp": int(time.time() * 1000)},
            {"exchange": "kraken", "symbol": "BTC/USDT", "bid": 67480.00, "ask": 67485.00, "last": 67482.75, "volume_24h_usd": 1200000000, "timestamp": int(time.time() * 1000)},
            {"exchange": "okx", "symbol": "BTC/USDT", "bid": 67500.00, "ask": 67505.00, "last": 67502.50, "volume_24h_usd": 900000000, "timestamp": int(time.time() * 1000)},
            {"exchange": "bybit", "symbol": "BTC/USDT", "bid": 67492.00, "ask": 67518.00, "last": 67505.00, "volume_24h_usd": 1500000000, "timestamp": int(time.time() * 1000)},
            {"exchange": "gateio", "symbol": "BTC/USDT", "bid": 67505.00, "ask": 67512.00, "last": 67508.50, "volume_24h_usd": 700000000, "timestamp": int(time.time() * 1000)},
            {"exchange": "kucoin", "symbol": "BTC/USDT", "bid": 67498.00, "ask": 67520.00, "last": 67509.00, "volume_24h_usd": 400000000, "timestamp": int(time.time() * 1000)},
            {"exchange": "mexc", "symbol": "BTC/USDT", "bid": 67499.00, "ask": 67520.00, "last": 67509.50, "volume_24h_usd": 350000000, "timestamp": int(time.time() * 1000)},
        ]
        
        # Build spread data
        best_buy = min(demo_tickers, key=lambda x: x.get("ask", float("inf")))
        best_sell = max(demo_tickers, key=lambda x: x.get("bid", 0))
        spread_pct = ((best_sell["bid"] - best_buy["ask"]) / best_buy["ask"]) * 100
        
        # Set data
        self.current_tickers = demo_tickers
        self.current_spread_data = {
            "buy_exchange": best_buy["exchange"],
            "buy_price": best_buy["ask"],
            "sell_exchange": best_sell["exchange"],
            "sell_price": best_sell["bid"],
            "spread_pct": spread_pct,
            "tickers": demo_tickers
        }
        self.last_update_time = QDateTime.currentDateTime()
        
        # Update UI
        self.opportunity_label.setText("📊 Demo Data (API Timeout)")
        self.opportunity_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
        
        self._update_spread_table()
        self._update_calculator_exchanges()
        self._update_profit_calculator()
    
    def on_fetch_finished(self):
        """Re-enable refresh button."""
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("↻ Refresh")
    
    def _update_opportunity_card(self):
        """Update best opportunity card."""
        if not self.current_spread_data:
            self.opportunity_label.setText("❌ No data available")
            self.opportunity_label.setStyleSheet(f"color: {Theme.ACCENT_RED};")
            return
        
        data = self.current_spread_data
        buy_ex = data.get("buy_exchange", "?")
        buy_price = data.get("buy_price", 0)
        sell_ex = data.get("sell_exchange", "?")
        sell_price = data.get("sell_price", 0)
        spread = data.get("spread_pct", 0)
        
        # Calculate net profit
        symbol = self.coin_combo.currentText().split("/")[0]  # Get coin part
        amount_usdt = 10000  # Default for display
        
        profit_data = calculate_net_profit(
            buy_exchange=buy_ex,
            sell_exchange=sell_ex,
            coin=symbol,
            amount_usdt=amount_usdt,
            buy_price=buy_price,
            sell_price=sell_price
        )
        
        net_profit = profit_data.get("net_profit", 0)
        net_pct = profit_data.get("net_profit_pct", 0)
        
        if net_profit > 0:
            text = f"🔥 Best: Buy on {buy_ex} @ ${buy_price:,.2f} → Sell on {sell_ex} @ ${sell_price:,.2f} | Spread: {spread:.3f}% | Net: +${net_profit:.2f} per ${amount_usdt:,}"
            self.opportunity_label.setStyleSheet(f"color: {Theme.ACCENT_GREEN};")
        else:
            text = f"❌ No profitable opportunity after fees (Net: -${abs(net_profit):.2f})"
            self.opportunity_label.setStyleSheet(f"color: {Theme.ACCENT_RED};")
        
        self.opportunity_label.setText(text)
    
    def _update_spread_table(self):
        """Update spread data table."""
        if not self.current_tickers:
            logger.warning(f"No tickers available for table update")
            return
        
        logger.info(f"Updating table with {len(self.current_tickers)} tickers")
        
        rows = []
        for i, ticker in enumerate(self.current_tickers):
            exchange = ticker.get("exchange", "?")
            bid = ticker.get("bid", 0)
            ask = ticker.get("ask", 0)
            volume = ticker.get("volume_24h_usd") or 0  # Handle None values
            
            # Calculate spread
            if ask > 0:
                spread_pct = ((bid - ask) / ask) * 100
            else:
                spread_pct = 0
            
            # Format values
            bid_str = self._format_price(bid)
            ask_str = self._format_price(ask)
            spread_str = f"{spread_pct:.4f}%"
            volume_str = self._format_volume(volume)
            status = "🟢 Live"
            
            row = [
                str(i + 1),
                exchange,
                bid_str,
                ask_str,
                spread_str,
                volume_str,
                status
            ]
            rows.append(row)
            logger.debug(f"Row {i+1}: {row}")
        
        logger.info(f"Prepared {len(rows)} rows for table display")
        if rows:
            logger.info(f"First row has {len(rows[0])} columns: {rows[0]}")
            if len(rows) > 1:
                logger.info(f"Second row has {len(rows[1])} columns: {rows[1]}")
        
        logger.info(f"Calling set_data with {len(rows)} rows")
        self.spread_table.set_data(rows)
        
        logger.info(f"Table now shows {self.spread_table.rowCount()} rows, {self.spread_table.columnCount()} cols")
        
        # Verify data was actually set
        if self.spread_table.rowCount() > 0:
            for row_idx in range(min(3, self.spread_table.rowCount())):  # Check first 3 rows
                row_text = []
                for col_idx in range(self.spread_table.columnCount()):
                    item = self.spread_table.item(row_idx, col_idx)
                    if item:
                        row_text.append(item.text())
                    else:
                        row_text.append("(empty)")
                logger.debug(f"  Row {row_idx}: {row_text}")
        
        # Highlight best buy (lowest ask) in green
        if self.current_spread_data:
            best_buy_exchange = self.current_spread_data.get("buy_exchange")
            best_sell_exchange = self.current_spread_data.get("sell_exchange")
            
            for i, ticker in enumerate(self.current_tickers):
                if ticker.get("exchange") == best_buy_exchange:
                    self.spread_table.highlight_row(i, Theme.ACCENT_GREEN)
                    break
        
        # Note: Highlighting best sell (highest bid) would require additional UI support
    
    def _update_calculator_exchanges(self):
        """Update exchange combos in calculator."""
        exchanges = [t.get("exchange", "") for t in self.current_tickers]
        exchanges = list(dict.fromkeys(exchanges))  # Remove duplicates
        
        self.buy_exchange_combo.blockSignals(True)
        self.sell_exchange_combo.blockSignals(True)
        
        self.buy_exchange_combo.clear()
        self.sell_exchange_combo.clear()
        
        self.buy_exchange_combo.addItems(exchanges)
        self.sell_exchange_combo.addItems(exchanges)
        
        # Set defaults to best buy/sell
        if self.current_spread_data:
            default_buy = self.current_spread_data.get("buy_exchange")
            default_sell = self.current_spread_data.get("sell_exchange")
            
            idx = self.buy_exchange_combo.findText(default_buy)
            if idx >= 0:
                self.buy_exchange_combo.setCurrentIndex(idx)
            
            idx = self.sell_exchange_combo.findText(default_sell)
            if idx >= 0:
                self.sell_exchange_combo.setCurrentIndex(idx)
        
        self.buy_exchange_combo.blockSignals(False)
        self.sell_exchange_combo.blockSignals(False)
    
    def on_calculator_changed(self):
        """Handle calculator input changes."""
        self._update_profit_calculator()
    
    def _update_profit_calculator(self):
        """Update profit calculation results."""
        try:
            amount = float(self.amount_input.text())
        except ValueError:
            amount = 10000
        
        buy_exchange = self.buy_exchange_combo.currentText()
        sell_exchange = self.sell_exchange_combo.currentText()
        symbol = self.coin_combo.currentText().split("/")[0]
        
        # Find prices
        buy_price = 0
        sell_price = 0
        
        for ticker in self.current_tickers:
            if ticker.get("exchange") == buy_exchange:
                buy_price = ticker.get("ask", 0)
            if ticker.get("exchange") == sell_exchange:
                sell_price = ticker.get("bid", 0)
        
        if buy_price == 0 or sell_price == 0:
            return
        
        # Calculate profit
        profit_data = calculate_net_profit(
            buy_exchange=buy_exchange,
            sell_exchange=sell_exchange,
            coin=symbol,
            amount_usdt=amount,
            buy_price=buy_price,
            sell_price=sell_price
        )
        
        # Update result labels
        gross_spread = (sell_price - buy_price) / buy_price * 100
        self.result_labels["gross_spread"].setText(
            f"Gross spread: {gross_spread:.4f}% (${(sell_price - buy_price) * (amount / buy_price):.2f})"
        )
        self.result_labels["buy_fee"].setText(
            f"Buy fee ({get_trading_fee(buy_exchange, 'taker'):.2f}%): -${profit_data['buy_fee']:.2f}"
        )
        self.result_labels["sell_fee"].setText(
            f"Sell fee ({get_trading_fee(sell_exchange, 'taker'):.2f}%): -${profit_data['sell_fee']:.2f}"
        )
        self.result_labels["withdraw_fee"].setText(
            f"Withdrawal fee: -${profit_data['withdraw_fee']:.2f}"
        )
        
        # Update net profit
        net_profit = profit_data.get("net_profit", 0)
        net_pct = profit_data.get("net_profit_pct", 0)
        
        if net_profit >= 0:
            profit_text = f"NET PROFIT: +${net_profit:.2f} (+{net_pct:.3f}%)"
            self.net_profit_label.setStyleSheet(f"color: {Theme.ACCENT_GREEN};")
        else:
            profit_text = f"NET PROFIT: -${abs(net_profit):.2f} ({net_pct:.3f}%)"
            self.net_profit_label.setStyleSheet(f"color: {Theme.ACCENT_RED};")
        
        self.net_profit_label.setText(profit_text)
    
    def _format_price(self, price: float) -> str:
        """Format price with appropriate decimals."""
        # Handle None or invalid values
        if not price or price is None:
            return "$0"
        
        try:
            price = float(price)
        except (TypeError, ValueError):
            return "$0"
        
        if price < 0.01:
            return f"${price:.8f}"
        elif price < 1:
            return f"${price:.6f}"
        elif price < 100:
            return f"${price:,.4f}"
        else:
            return f"${price:,.2f}"
    
    def _format_volume(self, volume: float) -> str:
        """Format volume in human-readable format."""
        # Handle None or invalid values
        if not volume or volume is None:
            return "$0"
        
        try:
            volume = float(volume)
        except (TypeError, ValueError):
            return "$0"
        
        if volume >= 1_000_000_000:
            return f"${volume / 1_000_000_000:.1f}B"
        elif volume >= 1_000_000:
            return f"${volume / 1_000_000:.1f}M"
        elif volume >= 1_000:
            return f"${volume / 1_000:.1f}K"
        else:
            return f"${volume:.0f}"
    
    def closeEvent(self, event):
        """Clean up on close."""
        self.auto_refresh_timer.stop()
        self.update_timer.stop()
        if self.fetch_worker:
            self.fetch_worker.quit()
            self.fetch_worker.wait()
        event.accept()
