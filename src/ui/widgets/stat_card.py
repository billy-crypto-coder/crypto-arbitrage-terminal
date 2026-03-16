"""
Reusable stat card widget for CryptoRadar
"""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.styles.theme import Theme


class StatCard(QFrame):
    """Card widget for displaying statistics with value and change indicator."""
    
    def __init__(self, title: str, value: str, change: str = "", positive: bool = True):
        """
        Initialize stat card.
        
        Args:
            title: Stat title (e.g., "Total Profit")
            value: Stat value (e.g., "$2,340")
            change: Change indicator (e.g., "+12.5%")
            positive: If True, change is green; if False, red
        """
        super().__init__()
        self.positive = positive
        self.setup_ui(title, value, change)
    
    def setup_ui(self, title: str, value: str, change: str):
        """Setup stat card UI."""
        # Set styling
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Plain)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_CARD};
                border-radius: 12px;
                border: 1px solid {Theme.BORDER};
            }}
        """)
        self.setFixedHeight(100)
        
        # Create layout
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        
        # Title label (muted, small)
        title_label = QLabel(title)
        title_font = QFont(Theme.FONT_FAMILY, 9)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
        layout.addWidget(title_label)
        
        # Value label (bold, larger)
        self.value_label = QLabel(value)
        value_font = QFont(Theme.FONT_FAMILY, 20)
        value_font.setBold(True)
        self.value_label.setFont(value_font)
        self.value_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(self.value_label)
        
        # Change indicator (with arrow)
        if change:
            self.change_label = QLabel(self._format_change(change))
            change_font = QFont(Theme.FONT_FAMILY, 11)
            change_font.setBold(True)
            self.change_label.setFont(change_font)
            
            change_color = Theme.ACCENT_GREEN if self.positive else Theme.ACCENT_RED
            self.change_label.setStyleSheet(f"color: {change_color};")
            layout.addWidget(self.change_label)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def _format_change(self, change: str) -> str:
        """Format change string with arrow indicator."""
        # Check if already has arrow
        if "↑" in change or "↓" in change:
            return change
        
        # Add arrow based on sign
        if change.startswith("-"):
            return f"↓ {change}"
        elif change.startswith("+"):
            return f"↑ {change}"
        else:
            return change
    
    def update_value(self, value: str, change: str = "", positive: bool = True):
        """Update card value and change indicator."""
        self.value_label.setText(value)
        self.positive = positive
        
        if change and hasattr(self, "change_label"):
            self.change_label.setText(self._format_change(change))
            change_color = Theme.ACCENT_GREEN if positive else Theme.ACCENT_RED
            self.change_label.setStyleSheet(f"color: {change_color};")
