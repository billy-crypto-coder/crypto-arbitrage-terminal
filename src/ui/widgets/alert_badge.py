"""
Alert notification badge widget
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class AlertBadge(QWidget):
    """Alert notification badge."""
    
    def __init__(self, alert_text: str, severity: str = "info"):
        super().__init__()
        self.severity = severity
        self.setup_ui(alert_text)
    
    def setup_ui(self, alert_text: str):
        """Setup badge UI."""
        layout = QVBoxLayout()
        
        label = QLabel(alert_text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(10)
        label.setFont(font)
        
        colors = {
            "info": "#00d084",
            "warning": "#ffa502",
            "error": "#ff4757"
        }
        color = colors.get(self.severity, "#00d084")
        
        label.setStyleSheet(f"color: {color};")
        layout.addWidget(label)
        
        self.setLayout(layout)
        self.setStyleSheet("background-color: #1a1a23; border-radius: 4px; padding: 8px;")
