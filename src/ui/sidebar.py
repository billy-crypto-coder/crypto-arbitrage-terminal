"""
Sidebar navigation component for CryptoRadar
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton, QSpacerItem, QSizePolicy
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from ui.styles.theme import Theme


class Sidebar(QWidget):
    """Left sidebar with navigation buttons."""
    
    # Signal emitted when a page is selected
    page_changed = Signal(int)
    
    # Page definitions: (icon_text, label, tooltip)
    PAGES = [
        ("📡", "Spread Scanner", "Scan for price spreads (Ctrl+1)"),
        ("⛽", "Gas Monitor", "Monitor network gas fees (Ctrl+2)"),
        ("📊", "Funding Rates", "View perpetual funding rates (Ctrl+3)"),
        ("💰", "Portfolio", "Portfolio and holdings (Ctrl+4)"),
        ("📋", "Trade Journal", "Trade history and journal (Ctrl+5)"),
        ("🔔", "Alerts", "Manage price and condition alerts (Ctrl+6)"),
    ]
    
    def __init__(self):
        super().__init__()
        self.buttons = []
        self.current_page = 0
        self.setup_ui()
    
    def setup_ui(self):
        """Setup sidebar UI."""
        # Set fixed width and background
        self.setFixedWidth(56)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_SECONDARY};
            }}
        """)
        
        # Create layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(4)
        
        # Top navigation buttons
        for index, (icon, label, tooltip) in enumerate(self.PAGES):
            btn = self._create_nav_button(icon, label, tooltip, index)
            layout.addWidget(btn)
            self.buttons.append(btn)
        
        # Add spacer to push Settings to bottom
        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Settings button at bottom
        settings_btn = self._create_nav_button("⚙️", "Settings", "Application settings (Ctrl+9)", len(self.PAGES))
        layout.addWidget(settings_btn)
        self.buttons.append(settings_btn)
        
        self.setLayout(layout)
        
        # Set first button as active
        self._set_active_button(0)
    
    def _create_nav_button(self, icon: str, label: str, tooltip: str, page_index: int) -> QToolButton:
        """Create a navigation button with icon, label, and tooltip."""
        btn = QToolButton()
        btn.setText(icon)
        btn.setFixedSize(40, 40)
        btn.setToolTip(label + "\n\n" + tooltip)
        btn.setObjectName(f"page_{page_index}")
        
        # Center text in button
        btn.setAutoRaise(True)
        
        # Styling
        font = QFont(Theme.FONT_FAMILY, 14)
        btn.setFont(font)
        
        btn.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                color: {Theme.TEXT_SECONDARY};
                margin: 0px;
                padding: 0px;
            }}
            
            QToolButton:hover {{
                background-color: {Theme.BG_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        
        # Store page index and connect click signal
        btn.page_index = page_index
        btn.clicked.connect(lambda: self._on_button_clicked(page_index, btn))
        
        return btn
    
    def _on_button_clicked(self, page_index: int, button: QToolButton):
        """Handle navigation button click."""
        self._set_active_button(page_index)
        self.page_changed.emit(page_index)
    
    def _set_active_button(self, page_index: int):
        """Set a button as active and update styles."""
        # Reset previous button
        if self.current_page < len(self.buttons):
            old_btn = self.buttons[self.current_page]
            old_btn.setStyleSheet(f"""
                QToolButton {{
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 8px;
                    color: {Theme.TEXT_SECONDARY};
                    margin: 0px;
                    padding: 0px;
                }}
                
                QToolButton:hover {{
                    background-color: {Theme.BG_HOVER};
                    color: {Theme.TEXT_PRIMARY};
                }}
            """)
        
        # Set new button as active
        if page_index < len(self.buttons):
            new_btn = self.buttons[page_index]
            new_btn.setStyleSheet(f"""
                QToolButton {{
                    background-color: {Theme.BG_HOVER};
                    border-left: 3px solid {Theme.ACCENT_GREEN};
                    border-radius: 8px;
                    color: {Theme.ACCENT_GREEN};
                    margin: 0px;
                    padding: 0px;
                    padding-left: 2px;
                }}
                
                QToolButton:hover {{
                    background-color: {Theme.BG_HOVER};
                    color: {Theme.ACCENT_GREEN};
                }}
            """)
        
        self.current_page = page_index
