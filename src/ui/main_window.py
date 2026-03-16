"""
Main window for CryptoRadar with sidebar and page management
"""
from PySide6.QtWidgets import (
    QMainWindow, QHBoxLayout, QWidget, QStackedWidget, QLabel, QVBoxLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.sidebar import Sidebar
from ui.header import Header
from ui.styles.theme import Theme
from ui.pages.spread_scanner import SpreadScannerPage
from ui.pages.gas_monitor import GasMonitorPage
from ui.pages.funding_rates import FundingRatesPage
from ui.pages.portfolio import PortfolioPage
from ui.pages.trade_journal import TradeJournalPage
from ui.pages.alerts import AlertsPage
from ui.pages.settings import SettingsPage


class MainWindow(QMainWindow):
    """Main application window with sidebar navigation and content pages."""
    
    # Page names corresponding to indices
    PAGE_NAMES = [
        "Spread Scanner",
        "Gas Monitor",
        "Funding Rates",
        "Portfolio",
        "Trade Journal",
        "Alerts",
        "Settings",
    ]
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CryptoRadar")
        self.setGeometry(100, 100, 1280, 800)
        self.setMinimumSize(1024, 600)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup main window UI with sidebar, header, and pages."""
        # Create main widget and horizontal layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left: Sidebar
        self.sidebar = Sidebar()
        main_layout.addWidget(self.sidebar)
        
        # Right: Vertical layout with header and stacked widget
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # Header bar
        self.header = Header()
        right_layout.addWidget(self.header)
        
        # Content area with pages
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet(f"""
            QStackedWidget {{
                background-color: {Theme.BG_PRIMARY};
            }}
        """)
        
        # Create placeholder pages
        for i, page_name in enumerate(self.PAGE_NAMES):
            if i == 0:
                # Use actual SpreadScannerPage for index 0
                page_widget = SpreadScannerPage()
            elif i == 1:
                # Use actual GasMonitorPage for index 1
                page_widget = GasMonitorPage()
            elif i == 2:
                # Use actual FundingRatesPage for index 2
                page_widget = FundingRatesPage()
            elif i == 3:
                # Use actual PortfolioPage for index 3
                page_widget = PortfolioPage()
                self.portfolio_page = page_widget
            elif i == 4:
                # Use actual TradeJournalPage for index 4
                page_widget = TradeJournalPage()
            elif i == 5:
                # Use actual AlertsPage for index 5
                page_widget = AlertsPage()
            elif i == 6:
                # Use actual SettingsPage for index 6
                page_widget = SettingsPage()
            else:
                # Use placeholder for other pages
                page_widget = self._create_placeholder_page(page_name)
            self.stacked_widget.addWidget(page_widget)
        
        right_layout.addWidget(self.stacked_widget)
        
        # Add right layout to main layout
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        main_layout.addWidget(right_widget)
        
        main_widget.setLayout(main_layout)
        
        # Connect signals
        self.sidebar.page_changed.connect(self._on_page_changed)
        
        # Connect portfolio navigation to settings
        if hasattr(self, 'portfolio_page'):
            self.portfolio_page.navigate_to_settings.connect(lambda: self._navigate_to_page(6))
        
        # Set default page (Spread Scanner - index 0)
        self.stacked_widget.setCurrentIndex(0)
        self.header.set_page_title(self.PAGE_NAMES[0])
    
    def _on_page_changed(self, page_index: int):
        """Handle page change from sidebar."""
        self.stacked_widget.setCurrentIndex(page_index)
        page_name = self.PAGE_NAMES[page_index]
        self.header.set_page_title(page_name)
    
    def _navigate_to_page(self, page_index: int):
        """Navigate to a specific page."""
        self.stacked_widget.setCurrentIndex(page_index)
        page_name = self.PAGE_NAMES[page_index]
        self.header.set_page_title(page_name)
    
    def _create_placeholder_page(self, page_name: str) -> QWidget:
        """Create a placeholder page with centered label."""
        page = QWidget()
        page.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_PRIMARY};
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create centered label
        label = QLabel(page_name)
        font = QFont(Theme.FONT_FAMILY, 18)
        font.setBold(True)
        label.setFont(font)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"""
            QLabel {{
                color: {Theme.TEXT_SECONDARY};
            }}
        """)
        
        layout.addWidget(label)
        page.setLayout(layout)
        
        return page
