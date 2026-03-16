"""
Trade Journal page for CryptoRadar
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDateEdit, QDateTimeEdit, QDoubleSpinBox, QSpinBox, QTextEdit, QLineEdit,
    QDialog, QTableWidgetItem, QMessageBox, QHeaderView, QSizePolicy, QMenu
)
from PySide6.QtCore import Qt, QDate, QDateTime
from PySide6.QtGui import QFont, QColor

from ui.styles.theme import Theme
from ui.widgets.stat_card import StatCard
from ui.widgets.data_table import DataTable
from database import Database

try:
    import pyqtgraph as pg
except ImportError:
    pg = None

logger = logging.getLogger(__name__)

# Trade type configurations
TRADE_TYPES = {
    'cex_arb': ('CEX↔CEX Arbitrage', '🟢'),
    'dex_arb': ('DEX↔CEX Arbitrage', '🔵'),
    'funding': ('Funding Rate', '🟡'),
    'other': ('Other', '⚪'),
}

SUPPORTED_COINS = ['BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'DOGE', 'AVAX', 'LINK', 
                   'ARB', 'OP', 'BNB', 'MATIC', 'DOT', 'ATOM', 'UNI', 'LTC']

SUPPORTED_EXCHANGES = ['binance', 'bybit', 'okx', 'bitget', 'kraken', 'dydx']


class NewTradeDialog(QDialog):
    """Dialog for adding/editing trades"""

    def __init__(self, parent=None, trade_data: Optional[Dict] = None):
        super().__init__(parent)
        self.trade_data = trade_data
        self.db = Database()
        self.setWindowTitle('New Trade' if not trade_data else 'Edit Trade')
        self.setGeometry(100, 100, 700, 900)
        self.init_ui()
        
        if trade_data:
            self.load_trade_data(trade_data)

    def init_ui(self):
        """Initialize dialog UI"""
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Date/Time
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Date/Time:"))
        self.date_time_edit = QDateTimeEdit()
        self.date_time_edit.setDateTime(QDateTime.currentDateTime())
        date_layout.addWidget(self.date_time_edit)
        layout.addLayout(date_layout)

        # Type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Trade Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems([v[0] for v in TRADE_TYPES.values()])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)

        # Coin
        coin_layout = QHBoxLayout()
        coin_layout.addWidget(QLabel("Coin:"))
        self.coin_combo = QComboBox()
        self.coin_combo.addItems(SUPPORTED_COINS)
        coin_layout.addWidget(self.coin_combo)
        layout.addLayout(coin_layout)

        # Buy Exchange
        buy_exch_layout = QHBoxLayout()
        buy_exch_layout.addWidget(QLabel("Buy Exchange:"))
        self.buy_exchange_combo = QComboBox()
        self.buy_exchange_combo.addItems(SUPPORTED_EXCHANGES)
        buy_exch_layout.addWidget(self.buy_exchange_combo)
        layout.addLayout(buy_exch_layout)

        # Sell Exchange
        sell_exch_layout = QHBoxLayout()
        sell_exch_label = QLabel("Sell Exchange:")
        sell_exch_layout.addWidget(sell_exch_label)
        self.sell_exchange_combo = QComboBox()
        self.sell_exchange_combo.addItems([''] + SUPPORTED_EXCHANGES)
        sell_exch_layout.addWidget(self.sell_exchange_combo)
        self.sell_exchange_label = sell_exch_label
        layout.addLayout(sell_exch_layout)

        # Buy Price
        buy_price_layout = QHBoxLayout()
        buy_price_layout.addWidget(QLabel("Buy Price (USD):"))
        self.buy_price_spin = QDoubleSpinBox()
        self.buy_price_spin.setRange(0.00000001, 999999999)
        self.buy_price_spin.setDecimals(8)
        self.buy_price_spin.valueChanged.connect(self._recalculate_fields)
        buy_price_layout.addWidget(self.buy_price_spin)
        layout.addLayout(buy_price_layout)

        # Sell Price
        sell_price_layout = QHBoxLayout()
        sell_price_label = QLabel("Sell Price (USD):")
        sell_price_layout.addWidget(sell_price_label)
        self.sell_price_spin = QDoubleSpinBox()
        self.sell_price_spin.setRange(0.00000001, 999999999)
        self.sell_price_spin.setDecimals(8)
        self.sell_price_spin.valueChanged.connect(self._recalculate_fields)
        sell_price_layout.addWidget(self.sell_price_spin)
        self.sell_price_label = sell_price_label
        layout.addLayout(sell_price_layout)

        # Amount
        amount_layout = QHBoxLayout()
        amount_layout.addWidget(QLabel("Amount (coins):"))
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.00000001, 999999999)
        self.amount_spin.setDecimals(8)
        self.amount_spin.valueChanged.connect(self._recalculate_fields)
        amount_layout.addWidget(self.amount_spin)
        layout.addLayout(amount_layout)

        # Amount USDT
        usdt_layout = QHBoxLayout()
        usdt_layout.addWidget(QLabel("Amount (USDT):"))
        self.amount_usdt_spin = QDoubleSpinBox()
        self.amount_usdt_spin.setRange(0, 999999999)
        self.amount_usdt_spin.setDecimals(2)
        self.amount_usdt_spin.valueChanged.connect(self._recalculate_fields)
        usdt_layout.addWidget(self.amount_usdt_spin)
        layout.addLayout(usdt_layout)

        # Total Fees
        fees_layout = QHBoxLayout()
        fees_layout.addWidget(QLabel("Total Fees (USD):"))
        self.fees_spin = QDoubleSpinBox()
        self.fees_spin.setRange(0, 999999999)
        self.fees_spin.setDecimals(2)
        self.fees_spin.valueChanged.connect(self._recalculate_fields)
        fees_layout.addWidget(self.fees_spin)
        layout.addLayout(fees_layout)

        # Net Profit (read-only)
        profit_layout = QHBoxLayout()
        profit_layout.addWidget(QLabel("Net Profit (USD):"))
        self.profit_label = QLabel("$0.00")
        self.profit_label.setFont(QFont(Theme.FONT_FAMILY, 11, QFont.Weight.Bold))
        self.profit_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        profit_layout.addWidget(self.profit_label)
        profit_layout.addStretch()
        layout.addLayout(profit_layout)

        # Notes
        notes_layout = QHBoxLayout()
        notes_layout.addWidget(QLabel("Notes:"))
        self.notes_text = QTextEdit()
        self.notes_text.setMaximumHeight(60)
        notes_layout.addWidget(self.notes_text)
        layout.addLayout(notes_layout)

        # Tags
        tags_layout = QHBoxLayout()
        tags_layout.addWidget(QLabel("Tags:"))
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("comma-separated")
        tags_layout.addWidget(self.tags_input)
        layout.addLayout(tags_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Trade")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.ACCENT_GREEN};
                color: #000;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #00e894; }}
        """)
        save_btn.clicked.connect(self.save_trade)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()

        self.setLayout(layout)

    def _on_type_changed(self):
        """Handle trade type change"""
        trade_type = self._get_trade_type_key()
        is_funding = trade_type == 'funding'
        
        # Toggle sell exchange/price visibility
        self.sell_exchange_label.setVisible(not is_funding)
        self.sell_exchange_combo.setVisible(not is_funding)
        self.sell_price_label.setVisible(not is_funding)
        self.sell_price_spin.setVisible(not is_funding)
        
        self._recalculate_fields()

    def _recalculate_fields(self):
        """Recalculate derived fields"""
        amount = self.amount_spin.value()
        buy_price = self.buy_price_spin.value()
        sell_price = self.sell_price_spin.value()
        amount_usdt = self.amount_usdt_spin.value()
        fees = self.fees_spin.value()
        
        # Auto-calculate amount_usdt if amount or buy_price changed
        if amount > 0 and buy_price > 0:
            calc_usdt = amount * buy_price
            if abs(amount_usdt - calc_usdt) > 0.01:
                self.amount_usdt_spin.blockSignals(True)
                self.amount_usdt_spin.setValue(calc_usdt)
                self.amount_usdt_spin.blockSignals(False)
        
        # Calculate net profit
        trade_type = self._get_trade_type_key()
        
        if trade_type == 'funding':
            # Funding: profit = amount * rate (rate is in sell_price)
            net_profit = amount * sell_price - fees
        elif buy_price > 0 and sell_price > 0 and amount > 0:
            # Arb: gross profit = (sell_price - buy_price) * amount
            gross_profit = (sell_price - buy_price) * amount
            net_profit = gross_profit - fees
        else:
            net_profit = -fees if fees > 0 else 0
        
        # Update profit label
        color = Theme.ACCENT_GREEN if net_profit >= 0 else Theme.ACCENT_RED
        self.profit_label.setText(f"${net_profit:,.2f}")
        self.profit_label.setStyleSheet(f"color: {color};")

    def _get_trade_type_key(self) -> str:
        """Get trade type key from combo box"""
        text = self.type_combo.currentText()
        for key, (label, _) in TRADE_TYPES.items():
            if label == text:
                return key
        return 'other'

    def load_trade_data(self, trade_data: Dict):
        """Load trade data into form"""
        # Parse datetime
        dt = datetime.fromisoformat(trade_data['trade_date'])
        self.date_time_edit.setDateTime(QDateTime(dt.date(), dt.time()))
        
        # Set type
        trade_type = trade_data.get('trade_type', 'other')
        type_label = TRADE_TYPES.get(trade_type, ('Other', '⚪'))[0]
        self.type_combo.setCurrentText(type_label)
        
        # Set coin and exchanges
        self.coin_combo.setCurrentText(trade_data.get('coin', 'BTC'))
        self.buy_exchange_combo.setCurrentText(trade_data.get('buy_exchange', 'binance'))
        
        sell_exch = trade_data.get('sell_exchange', '')
        if sell_exch:
            self.sell_exchange_combo.setCurrentText(sell_exch)
        
        # Set prices and amounts
        self.buy_price_spin.setValue(trade_data.get('buy_price', 0))
        sell_price = trade_data.get('sell_price', 0)
        if sell_price:
            self.sell_price_spin.setValue(sell_price)
        
        self.amount_spin.setValue(trade_data.get('amount', 0))
        self.amount_usdt_spin.setValue(trade_data.get('amount_usdt', 0))
        self.fees_spin.setValue(trade_data.get('total_fees', 0))
        
        # Set notes and tags
        self.notes_text.setText(trade_data.get('notes', ''))
        tags = trade_data.get('tags', [])
        if isinstance(tags, list):
            self.tags_input.setText(', '.join(tags))

    def save_trade(self):
        """Save trade to database"""
        trade_type = self._get_trade_type_key()
        
        trade_dict = {
            'trade_date': self.date_time_edit.dateTime().toString(Qt.ISODate),
            'trade_type': trade_type,
            'coin': self.coin_combo.currentText(),
            'buy_exchange': self.buy_exchange_combo.currentText(),
            'sell_exchange': self.sell_exchange_combo.currentText() if trade_type != 'funding' else None,
            'buy_price': self.buy_price_spin.value(),
            'sell_price': self.sell_price_spin.value() if trade_type != 'funding' else None,
            'amount': self.amount_spin.value(),
            'amount_usdt': self.amount_usdt_spin.value(),
            'total_fees': self.fees_spin.value(),
            'notes': self.notes_text.toPlainText(),
            'tags': [t.strip() for t in self.tags_input.text().split(',') if t.strip()],
        }
        
        # Calculate profit
        if trade_type == 'funding':
            trade_dict['gross_profit'] = trade_dict['amount'] * trade_dict['sell_price']
        else:
            trade_dict['gross_profit'] = (trade_dict['sell_price'] - trade_dict['buy_price']) * trade_dict['amount']
        
        trade_dict['net_profit'] = trade_dict['gross_profit'] - trade_dict['total_fees']
        
        try:
            if self.trade_data:
                # Update existing trade
                self.db.update_trade(self.trade_data['id'], trade_dict)
                QMessageBox.information(self, "Success", "Trade updated successfully")
            else:
                # Add new trade
                self.db.add_trade(trade_dict)
                QMessageBox.information(self, "Success", "Trade added successfully")
            
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save trade: {e}")
            logger.error(f"Trade save error: {e}")


class TradeJournalPage(QWidget):
    """Trade Journal page for tracking and analyzing trades"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.current_page = 0
        self.page_size = 50
        self.filters = {'coin': None, 'trade_type': None, 'date_from': None, 'date_to': None}
        self.all_trades = []
        
        self.setStyleSheet(f"QWidget {{ background-color: {Theme.BG_PRIMARY}; }}")
        self.init_ui()
        self.refresh_data()

    def init_ui(self):
        """Initialize page UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Stat cards
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
        
        self.stats_cards = {
            'total_trades': StatCard("Total Trades", "0"),
            'net_profit': StatCard("Net Profit", "$0.00"),
            'win_rate': StatCard("Win Rate", "0%"),
            'avg_profit': StatCard("Avg Profit", "$0.00"),
            'best_trade': StatCard("Best Trade", "$0.00"),
        }
        
        for card in self.stats_cards.values():
            stats_layout.addWidget(card)
        
        main_layout.addLayout(stats_layout)

        # Action bar
        action_layout = QHBoxLayout()
        
        new_trade_btn = QPushButton("+ New Trade")
        new_trade_btn.setMaximumWidth(150)
        new_trade_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.ACCENT_GREEN};
                color: #000;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #00e894; }}
        """)
        new_trade_btn.clicked.connect(self.open_new_trade_dialog)
        action_layout.addWidget(new_trade_btn)
        
        action_layout.addStretch()
        
        # Filters
        action_layout.addWidget(QLabel("Coin:"))
        self.coin_filter = QComboBox()
        self.coin_filter.addItems(['All'] + SUPPORTED_COINS)
        action_layout.addWidget(self.coin_filter)
        
        action_layout.addWidget(QLabel("Type:"))
        self.type_filter = QComboBox()
        self.type_filter.addItems(['All'] + [v[0] for v in TRADE_TYPES.values()])
        action_layout.addWidget(self.type_filter)
        
        action_layout.addWidget(QLabel("From:"))
        self.date_from_filter = QDateEdit()
        self.date_from_filter.setDate(QDate.currentDate().addDays(-30))
        action_layout.addWidget(self.date_from_filter)
        
        action_layout.addWidget(QLabel("To:"))
        self.date_to_filter = QDateEdit()
        self.date_to_filter.setDate(QDate.currentDate())
        action_layout.addWidget(self.date_to_filter)
        
        apply_filters_btn = QPushButton("Apply Filters")
        apply_filters_btn.clicked.connect(self.apply_filters)
        action_layout.addWidget(apply_filters_btn)
        
        main_layout.addLayout(action_layout)

        # Trades table
        headers = ["Date", "Type", "Coin", "Buy On", "Sell On", "Amount", "Net P&L", "Notes"]
        self.trades_table = DataTable(headers=headers)
        self.trades_table.setMinimumHeight(300)
        self.trades_table.itemDoubleClicked.connect(self.on_table_double_click)
        self.trades_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.trades_table.customContextMenuRequested.connect(self.on_table_context_menu)
        main_layout.addWidget(self.trades_table)

        # Pagination
        pagination_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.clicked.connect(self.previous_page)
        pagination_layout.addWidget(self.prev_btn)
        
        self.page_label = QLabel("Page 1")
        pagination_layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("Next →")
        self.next_btn.clicked.connect(self.next_page)
        pagination_layout.addWidget(self.next_btn)
        
        pagination_layout.addStretch()
        
        main_layout.addLayout(pagination_layout)

        # P&L Chart
        if pg:
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setLabel('left', 'Cumulative P&L (USD)')
            self.plot_widget.setLabel('bottom', 'Time')
            self.plot_widget.setMaximumHeight(200)
            self.plot_widget.setStyleSheet(f"background-color: {Theme.BG_CARD};")
            main_layout.addWidget(self.plot_widget)

        main_layout.addStretch()
        self.setLayout(main_layout)

    def refresh_data(self):
        """Refresh stats and trades"""
        try:
            # Get stats
            stats = self.db.get_trade_stats(
                date_from=self.filters['date_from'],
                date_to=self.filters['date_to']
            )
            
            # Update stat cards
            self.stats_cards['total_trades'].value_label.setText(str(stats.get('total_trades', 0)))
            
            net_profit = stats.get('total_net_profit', 0) or 0
            self.stats_cards['net_profit'].value_label.setText(f"${net_profit:,.2f}")
            
            win_rate = stats.get('win_rate', 0) or 0
            self.stats_cards['win_rate'].value_label.setText(f"{win_rate:.1f}%")
            
            avg_profit = stats.get('avg_profit', 0) or 0
            self.stats_cards['avg_profit'].value_label.setText(f"${avg_profit:,.2f}")
            
            best_trade = stats.get('best_trade', 0) or 0
            self.stats_cards['best_trade'].value_label.setText(f"${best_trade:,.2f}")
            
            # Get and display trades
            self.load_trades()
            
            # Update chart
            if pg:
                self.update_chart(stats.get('profit_by_day', []))
            
        except Exception as e:
            logger.error(f"Failed to refresh data: {e}")

    def load_trades(self):
        """Load trades table"""
        self.all_trades = self.db.get_trades(
            limit=999999,
            coin=self.filters['coin'],
            trade_type=self.filters.get('trade_type_key'),
            date_from=self.filters['date_from'],
            date_to=self.filters['date_to']
        )
        
        # Paginate
        start = self.current_page * self.page_size
        end = start + self.page_size
        trades = self.all_trades[start:end]
        
        rows = []
        for trade in trades:
            # Format datetime
            dt = datetime.fromisoformat(trade['trade_date'])
            date_str = dt.strftime("%d %b %Y, %H:%M")
            
            # Format type
            type_key = trade.get('trade_type', 'other')
            type_label, emoji = TRADE_TYPES.get(type_key, ('Other', '⚪'))
            type_str = f"{emoji} {type_label}"
            
            # Format amounts
            amount_str = f"{trade['amount']:.4f}"
            
            # Format P&L
            net_profit = trade.get('net_profit', 0)
            pnl_str = f"${net_profit:,.2f}"
            
            rows.append([
                date_str,
                type_str,
                trade.get('coin', ''),
                trade.get('buy_exchange', ''),
                trade.get('sell_exchange', '') or '—',
                amount_str,
                pnl_str,
                trade.get('notes', '')[:50],
            ])
        
        self.trades_table.set_data(rows)
        
        # Update pagination
        total_trades = len(self.all_trades)
        total_pages = (total_trades + self.page_size - 1) // self.page_size
        self.page_label.setText(f"Page {self.current_page + 1} of {max(1, total_pages)} (Showing {min(start + 1, total_trades)}-{min(end, total_trades)} of {total_trades})")
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < total_pages - 1)

    def update_chart(self, profit_by_day: List[tuple]):
        """Update P&L chart"""
        if not pg or not hasattr(self, 'plot_widget'):
            return
        
        self.plot_widget.clear()
        
        if not profit_by_day:
            return
        
        # Calculate cumulative profit
        cumulative = 0
        x_data = []
        y_data = []
        
        for idx, (date_str, profit) in enumerate(profit_by_day):
            cumulative += profit or 0
            x_data.append(idx)
            y_data.append(cumulative)
        
        # Plot
        pen_color = Theme.ACCENT_GREEN if cumulative >= 0 else Theme.ACCENT_RED
        pen = pg.mkPen(pen_color, width=2)
        self.plot_widget.plot(x_data, y_data, pen=pen)
        
        # Add 0 line
        self.plot_widget.addLine(y=0, pen=pg.mkPen(Theme.BORDER, style=Qt.DashLine))

    def apply_filters(self):
        """Apply selected filters"""
        coin_text = self.coin_filter.currentText()
        self.filters['coin'] = coin_text if coin_text != 'All' else None
        
        type_text = self.type_filter.currentText()
        if type_text != 'All':
            for key, (label, _) in TRADE_TYPES.items():
                if label == type_text:
                    self.filters['trade_type_key'] = key
                    break
        else:
            self.filters['trade_type_key'] = None
        
        self.filters['date_from'] = self.date_from_filter.date().toString(Qt.ISODate)
        self.filters['date_to'] = self.date_to_filter.date().toString(Qt.ISODate)
        
        self.current_page = 0
        self.refresh_data()

    def open_new_trade_dialog(self):
        """Open dialog to add new trade"""
        dialog = NewTradeDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.current_page = 0
            self.refresh_data()

    def on_table_double_click(self):
        """Edit trade on double-click"""
        row = self.trades_table.currentRow()
        if row >= 0 and row < len(self.all_trades):
            trade = self.all_trades[self.current_page * self.page_size + row]
            dialog = NewTradeDialog(self, trade)
            if dialog.exec() == QDialog.Accepted:
                self.refresh_data()

    def on_table_context_menu(self, position):
        """Show context menu on right-click"""
        row = self.trades_table.rowAt(position.y())
        if row >= 0 and row < len(self.all_trades):
            menu = QMenu(self)
            
            edit_action = menu.addAction("✏️ Edit")
            delete_action = menu.addAction("🗑️ Delete")
            
            action = menu.exec(self.trades_table.mapToGlobal(position))
            
            if action == edit_action:
                trade = self.all_trades[self.current_page * self.page_size + row]
                dialog = NewTradeDialog(self, trade)
                if dialog.exec() == QDialog.Accepted:
                    self.refresh_data()
            
            elif action == delete_action:
                reply = QMessageBox.question(
                    self, "Confirm Delete",
                    "Are you sure you want to delete this trade?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    trade = self.all_trades[self.current_page * self.page_size + row]
                    self.db.delete_trade(trade['id'])
                    self.refresh_data()

    def previous_page(self):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self.load_trades()

    def next_page(self):
        """Go to next page"""
        self.current_page += 1
        self.load_trades()
