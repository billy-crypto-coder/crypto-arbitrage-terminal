"""
Portfolio Dashboard page for CryptoRadar
"""
import logging
import csv
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QScrollArea, QMessageBox, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QMargins
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtCharts import (
    QChart, QChartView, QPieSeries, QBarSeries, QBarSet,
    QBarCategoryAxis, QValueAxis
)

from ui.styles.theme import Theme
from ui.widgets.stat_card import StatCard
from ui.widgets.data_table import DataTable
from utils.encryption import KeyManager
from config import settings

try:
    import ccxt
except ImportError:
    ccxt = None

try:
    import requests as _requests
except ImportError:
    _requests = None

logger = logging.getLogger(__name__)


class BalanceFetchWorker(QThread):
    balances_fetched = Signal(dict, bool, str)

    def __init__(self, key_manager: KeyManager, exchanges: List[str]):
        super().__init__()
        self.key_manager = key_manager
        self.exchanges = exchanges

    def run(self):
        if not ccxt:
            self.balances_fetched.emit({}, False, "ccxt library not installed. Run: pip install ccxt")
            return

        balances = {}
        ok_count = 0
        errors = []

        for exchange_name in self.exchanges:
            try:
                keys = self.key_manager.get_api_keys(exchange_name)
                if not keys:
                    continue

                exchange_class = getattr(ccxt, exchange_name, None)
                if not exchange_class:
                    errors.append(f"{exchange_name}: not supported by ccxt")
                    continue

                exchange = exchange_class({
                    "apiKey": keys.get("key", ""),
                    "secret": keys.get("secret", ""),
                    "password": keys.get("passphrase", ""),
                    "enableRateLimit": True,
                    "timeout": 15000,
                })

                balance = exchange.fetch_balance()
                balances[exchange_name] = balance
                ok_count += 1
                logger.info(f"Fetched balance for {exchange_name}")

            except Exception as e:
                msg = f"{exchange_name}: {e}"
                logger.error(msg)
                errors.append(msg)
                balances[exchange_name] = None

        success = ok_count > 0
        message = f"Fetched {ok_count}/{len(self.exchanges)} exchange(s)"
        if errors:
            message += f" ({len(errors)} errors)"

        self.balances_fetched.emit(balances, success, message)


class PriceFetchWorker(QThread):
    prices_fetched = Signal(dict)

    COINGECKO_IDS = {
        "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
        "XRP": "ripple", "DOGE": "dogecoin", "ADA": "cardano",
        "AVAX": "avalanche-2", "LINK": "chainlink", "ARB": "arbitrum",
        "OP": "optimism", "BNB": "binancecoin", "MATIC": "matic-network",
        "DOT": "polkadot", "ATOM": "cosmos", "UNI": "uniswap",
        "LTC": "litecoin", "PEPE": "pepe", "WLD": "worldcoin-wld",
        "NEAR": "near", "FTM": "fantom", "ALGO": "algorand",
    }

    STABLECOINS = {"USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "UST", "USDP"}

    def __init__(self, assets: List[str]):
        super().__init__()
        self.assets = assets

    def run(self):
        prices = {}

        for asset in self.assets:
            if asset.upper() in self.STABLECOINS:
                prices[asset] = 1.0

        if not _requests:
            self.prices_fetched.emit(prices)
            return

        cg_ids = []
        cg_map = {}
        for asset in self.assets:
            upper = asset.upper()
            if upper in self.STABLECOINS:
                continue
            cg_id = self.COINGECKO_IDS.get(upper)
            if cg_id:
                cg_ids.append(cg_id)
                cg_map[cg_id] = asset

        if not cg_ids:
            self.prices_fetched.emit(prices)
            return

        try:
            resp = _requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": ",".join(cg_ids),
                    "vs_currencies": "usd",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            for cg_id, asset in cg_map.items():
                usd = data.get(cg_id, {}).get("usd", 0)
                if usd > 0:
                    prices[asset] = usd

        except Exception as e:
            logger.warning(f"CoinGecko price fetch failed: {e}")

        self.prices_fetched.emit(prices)


class PortfolioPage(QWidget):
    navigate_to_settings = Signal()

    CHART_COLORS = [
        "#00d4aa", "#3742fa", "#ffa502", "#ff4757",
        "#2ed573", "#1e90ff", "#ff6348", "#a55eea",
    ]

    def __init__(self):
        super().__init__()
        self.key_manager = KeyManager()
        self.balances: Dict = {}
        self.prices: Dict[str, float] = {}
        self.last_fetch_time: Optional[datetime] = None
        self.fetch_worker: Optional[BalanceFetchWorker] = None
        self.price_worker: Optional[PriceFetchWorker] = None
        self._dashboard_built = False
        self._init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        self._check_state()

    def _init_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(f"""
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

        self.content = QWidget()
        self.content.setStyleSheet(f"background: {Theme.BG_PRIMARY};")
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(16)
        self.content.setLayout(self.content_layout)
        self.scroll.setWidget(self.content)

        root.addWidget(self.scroll)
        self.setLayout(root)

    def _check_state(self):
        configured = self.key_manager.list_configured_exchanges()
        self._clear_layout()
        self._dashboard_built = False

        if not configured:
            self._build_empty_state()
        else:
            self._build_dashboard(configured)
            self._refresh_balances()

    def _clear_layout(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
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
                PortfolioPage._clear_child_layout(item.layout())

    def _styled_button(self, text: str, accent: bool = False,
                       max_width: int = 180) -> QPushButton:
        btn = QPushButton(text)
        btn.setMaximumWidth(max_width)
        btn.setMinimumHeight(38)
        btn.setFont(QFont(Theme.FONT_FAMILY, 10, QFont.Weight.Bold))

        if accent:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Theme.ACCENT_GREEN};
                    color: #000;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                }}
                QPushButton:hover {{ background-color: #00e894; }}
                QPushButton:disabled {{ background-color: {Theme.BORDER}; color: {Theme.TEXT_SECONDARY}; }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Theme.BG_CARD};
                    color: {Theme.TEXT_PRIMARY};
                    border: 1px solid {Theme.BORDER};
                    border-radius: 6px;
                    padding: 8px 16px;
                }}
                QPushButton:hover {{ border-color: {Theme.ACCENT_GREEN}; }}
                QPushButton:disabled {{ color: {Theme.TEXT_SECONDARY}; }}
            """)
        return btn

    # ------------------------------------------------------------------
    # Empty state
    # ------------------------------------------------------------------

    def _build_empty_state(self):
        lbl_style = f"background: transparent; border: none; color: {Theme.TEXT_PRIMARY};"
        sub_style = f"background: transparent; border: none; color: {Theme.TEXT_SECONDARY};"

        spacer = QWidget()
        spacer.setFixedHeight(60)
        spacer.setStyleSheet("background: transparent; border: none;")
        self.content_layout.addWidget(spacer)

        icon = QLabel("💰")
        icon.setFont(QFont(Theme.FONT_FAMILY, 52))
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("background: transparent; border: none;")
        self.content_layout.addWidget(icon)

        title = QLabel("No exchanges connected")
        title.setFont(QFont(Theme.FONT_FAMILY, 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(lbl_style)
        self.content_layout.addWidget(title)

        subtitle = QLabel("Go to Settings → API Keys to add your exchanges")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(sub_style)
        self.content_layout.addWidget(subtitle)

        if not ccxt:
            warn = QLabel("⚠ ccxt library not installed. Run: pip install ccxt")
            warn.setAlignment(Qt.AlignCenter)
            warn.setWordWrap(True)
            warn.setStyleSheet(
                f"color: {Theme.ACCENT_YELLOW}; background: transparent; border: none;"
            )
            self.content_layout.addWidget(warn)

        btn = self._styled_button("⚙️ Open Settings", accent=True)
        btn.clicked.connect(self.navigate_to_settings.emit)
        self.content_layout.addWidget(btn, alignment=Qt.AlignCenter)

        self.content_layout.addStretch()

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def _build_dashboard(self, configured: List[str]):
        self._dashboard_built = True

        top_bar = QHBoxLayout()

        self.refresh_btn = self._styled_button("↻ Refresh Balances")
        self.refresh_btn.clicked.connect(self._refresh_balances)
        top_bar.addWidget(self.refresh_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            f"color: {Theme.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        top_bar.addWidget(self.status_label)
        top_bar.addStretch()

        top_container = QWidget()
        top_container.setStyleSheet("background: transparent; border: none;")
        top_container.setLayout(top_bar)
        self.content_layout.addWidget(top_container)

        stats_container = QWidget()
        stats_container.setStyleSheet("background: transparent; border: none;")
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
        stats_layout.setContentsMargins(0, 0, 0, 0)

        self.total_value_card = StatCard("Total Value", "$0.00")
        self.change_card = StatCard("24h Change", "—")
        self.exchanges_card = StatCard("Exchanges", str(len(configured)))
        self.assets_card = StatCard("Assets", "0")

        stats_layout.addWidget(self.total_value_card)
        stats_layout.addWidget(self.change_card)
        stats_layout.addWidget(self.exchanges_card)
        stats_layout.addWidget(self.assets_card)

        stats_container.setLayout(stats_layout)
        self.content_layout.addWidget(stats_container)

        self.balances_table = DataTable(
            headers=["Asset", "Amount", "Price (USD)", "Value (USD)", "Share"]
        )
        self.balances_table.setMinimumHeight(180)
        self.balances_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_layout.addWidget(self.balances_table)

        charts_container = QWidget()
        charts_container.setStyleSheet("background: transparent; border: none;")
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(12)
        charts_layout.setContentsMargins(0, 0, 0, 0)

        self.pie_view = QChartView()
        self.pie_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.pie_view.setMinimumHeight(280)
        self.pie_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.pie_view.setStyleSheet(f"background: {Theme.BG_CARD}; border-radius: 8px;")
        charts_layout.addWidget(self.pie_view)

        self.bar_view = QChartView()
        self.bar_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.bar_view.setMinimumHeight(280)
        self.bar_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.bar_view.setStyleSheet(f"background: {Theme.BG_CARD}; border-radius: 8px;")
        charts_layout.addWidget(self.bar_view)
        charts_container.setLayout(charts_layout)
        self.content_layout.addWidget(charts_container)

        export_btn = self._styled_button("📥 Export CSV")
        export_btn.clicked.connect(self._export_csv)
        self.content_layout.addWidget(export_btn)

        self.content_layout.addStretch()

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def _refresh_balances(self):
        configured = self.key_manager.list_configured_exchanges()
        if not configured:
            return

        if self.fetch_worker and self.fetch_worker.isRunning():
            return

        if (self.last_fetch_time
                and datetime.now() - self.last_fetch_time < timedelta(seconds=30)):
            if self._dashboard_built:
                self.status_label.setText("(cached — next refresh in <30s)")
            return

        if self._dashboard_built:
            self.refresh_btn.setEnabled(False)
            self.status_label.setText("⏳ Fetching balances...")
            self.status_label.setStyleSheet(
                f"color: {Theme.ACCENT_YELLOW}; background: transparent; border: none;"
            )

        self.fetch_worker = BalanceFetchWorker(self.key_manager, configured)
        self.fetch_worker.balances_fetched.connect(self._on_balances_fetched)
        self.fetch_worker.finished.connect(self._cleanup_balance_worker)
        self.fetch_worker.start()

    def _on_balances_fetched(self, balances: dict, success: bool, message: str):
        self.balances = balances
        self.last_fetch_time = datetime.now()

        if self._dashboard_built:
            self.refresh_btn.setEnabled(True)

        if success:
            if self._dashboard_built:
                self.status_label.setText(f"✅ {message}")
                self.status_label.setStyleSheet(
                    f"color: {Theme.ACCENT_GREEN}; background: transparent; border: none;"
                )
            self._fetch_prices()
        else:
            if self._dashboard_built:
                self.status_label.setText(f"❌ {message}")
                self.status_label.setStyleSheet(
                    f"color: {Theme.ACCENT_RED}; background: transparent; border: none;"
                )

    def _fetch_prices(self):
        if self.price_worker and self.price_worker.isRunning():
            return

        assets = set()
        for balance in self.balances.values():
            if balance is None:
                continue
            for asset, info in balance.get("total", {}).items():
                if isinstance(info, (int, float)) and info > 0:
                    assets.add(asset)
                elif isinstance(info, dict):
                    total = info.get("total", 0) or 0
                    if total > 0:
                        assets.add(asset)

        if not assets:
            self._update_dashboard_data()
            return

        self.price_worker = PriceFetchWorker(list(assets))
        self.price_worker.prices_fetched.connect(self._on_prices_fetched)
        self.price_worker.finished.connect(self._cleanup_price_worker)
        self.price_worker.start()

    def _on_prices_fetched(self, prices: dict):
        self.prices = prices
        self._update_dashboard_data()

    def _cleanup_balance_worker(self):
        if self.fetch_worker:
            self.fetch_worker.deleteLater()
            self.fetch_worker = None

    def _cleanup_price_worker(self):
        if self.price_worker:
            self.price_worker.deleteLater()
            self.price_worker = None

    # ------------------------------------------------------------------
    # Dashboard update
    # ------------------------------------------------------------------

    def _update_dashboard_data(self):
        if not self._dashboard_built:
            return

        asset_totals: Dict[str, float] = {}
        exchange_totals: Dict[str, float] = {}

        for exchange_name, balance in self.balances.items():
            if balance is None:
                continue

            exchange_totals[exchange_name] = 0
            total_dict = balance.get("total", {})

            for asset, amount in total_dict.items():
                if isinstance(amount, dict):
                    amount = amount.get("total", 0) or 0
                if not isinstance(amount, (int, float)) or amount <= 0:
                    continue

                asset_totals[asset] = asset_totals.get(asset, 0) + amount

                price = self.prices.get(asset, 0)
                exchange_totals[exchange_name] += amount * price

        asset_values: Dict[str, float] = {}
        total_portfolio = 0.0

        for asset, amount in asset_totals.items():
            price = self.prices.get(asset, 0)
            value = amount * price
            asset_values[asset] = value
            total_portfolio += value

        self.total_value_card.set_value(f"${total_portfolio:,.2f}")
        self.exchanges_card.set_value(
            str(sum(1 for v in self.balances.values() if v is not None))
        )
        self.assets_card.set_value(str(len(asset_totals)))

        self._update_table(asset_totals, asset_values, total_portfolio)
        self._update_pie_chart(asset_values, total_portfolio)
        self._update_bar_chart(asset_values)

    def _update_table(self, asset_totals: dict, asset_values: dict,
                      total_portfolio: float):
        sorted_assets = sorted(
            asset_totals.items(),
            key=lambda x: asset_values.get(x[0], 0),
            reverse=True,
        )

        rows = []
        for asset, amount in sorted_assets:
            price = self.prices.get(asset, 0)
            value = asset_values.get(asset, 0)
            share = (value / total_portfolio * 100) if total_portfolio > 0 else 0

            if asset in ("BTC", "ETH"):
                fmt_amount = f"{amount:.8f}"
            elif amount >= 1000:
                fmt_amount = f"{amount:,.2f}"
            elif amount >= 1:
                fmt_amount = f"{amount:.4f}"
            else:
                fmt_amount = f"{amount:.6f}"

            if price > 0:
                fmt_price = f"${price:,.2f}" if price >= 1 else f"${price:.6f}"
            else:
                fmt_price = "—"

            fmt_value = f"${value:,.2f}" if value > 0 else "—"
            fmt_share = f"{share:.1f}%" if share > 0 else "—"

            rows.append([asset, fmt_amount, fmt_price, fmt_value, fmt_share])

        self.balances_table.set_data(rows)

    def _update_pie_chart(self, asset_values: dict, total_portfolio: float):
        if not asset_values or total_portfolio <= 0:
            return

        series = QPieSeries()
        sorted_assets = sorted(asset_values.items(), key=lambda x: x[1], reverse=True)

        top_n = 6
        for idx, (asset, value) in enumerate(sorted_assets[:top_n]):
            if value <= 0:
                continue
            pct = value / total_portfolio * 100
            slc = series.append(f"{asset} {pct:.1f}%", value)
            slc.setColor(QColor(self.CHART_COLORS[idx % len(self.CHART_COLORS)]))
            slc.setLabelVisible(True)
            slc.setLabelColor(QColor(Theme.TEXT_PRIMARY))

        if len(sorted_assets) > top_n:
            other_val = sum(v for _, v in sorted_assets[top_n:] if v > 0)
            if other_val > 0:
                pct = other_val / total_portfolio * 100
                slc = series.append(f"Other {pct:.1f}%", other_val)
                slc.setColor(QColor(Theme.BORDER))
                slc.setLabelVisible(True)
                slc.setLabelColor(QColor(Theme.TEXT_PRIMARY))

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Asset Distribution")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setBackgroundBrush(QColor(Theme.BG_CARD))
        chart.setTitleBrush(QColor(Theme.TEXT_PRIMARY))
        chart.setMargins(QMargins(8, 8, 8, 8))
        chart.legend().setVisible(False)

        self.pie_view.setChart(chart)

    def _update_bar_chart(self, asset_values: dict):
        sorted_assets = sorted(
            [(a, v) for a, v in asset_values.items() if v > 0],
            key=lambda x: x[1],
            reverse=True,
        )[:8]

        if not sorted_assets:
            return

        series = QBarSeries()

        for idx, (asset, value) in enumerate(sorted_assets):
            bar_set = QBarSet(asset)
            bar_set.append(value)
            bar_set.setColor(QColor(self.CHART_COLORS[idx % len(self.CHART_COLORS)]))
            series.append(bar_set)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Top Assets by Value (USD)")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setBackgroundBrush(QColor(Theme.BG_CARD))
        chart.setTitleBrush(QColor(Theme.TEXT_PRIMARY))
        chart.setMargins(QMargins(8, 8, 8, 8))
        chart.legend().setVisible(False)

        categories = [a for a, _ in sorted_assets]
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsColor(QColor(Theme.TEXT_SECONDARY))
        axis_x.setGridLineVisible(False)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setLabelsColor(QColor(Theme.TEXT_SECONDARY))
        axis_y.setGridLineColor(QColor(Theme.BORDER))
        if sorted_assets:
            max_val = sorted_assets[0][1]
            axis_y.setRange(0, max_val * 1.15)
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        self.bar_view.setChart(chart)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_csv(self):
        if not self.balances:
            QMessageBox.warning(
                self, "No Data",
                "No balance data to export. Fetch balances first."
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Portfolio",
            f"portfolio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv);;All Files (*)",
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Export Date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow([])
                writer.writerow(["Asset", "Exchange", "Amount", "Price USD", "Value USD"])

                for exchange_name, balance in self.balances.items():
                    if balance is None:
                        continue
                    total_dict = balance.get("total", {})
                    for asset, amount in total_dict.items():
                        if isinstance(amount, dict):
                            amount = amount.get("total", 0) or 0
                        if not isinstance(amount, (int, float)) or amount <= 0:
                            continue
                        price = self.prices.get(asset, 0)
                        value = amount * price
                        writer.writerow([
                            asset,
                            exchange_name,
                            f"{amount:.8f}",
                            f"{price:.2f}" if price > 0 else "",
                            f"{value:.2f}" if value > 0 else "",
                        ])

            QMessageBox.information(self, "Success", f"Portfolio exported to:\n{file_path}")

        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        for worker in (self.fetch_worker, self.price_worker):
            if worker and worker.isRunning():
                worker.quit()
                if not worker.wait(3000):
                    worker.terminate()
                    worker.wait(1000)
        event.accept()