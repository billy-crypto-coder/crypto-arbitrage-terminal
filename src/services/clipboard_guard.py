"""
Clipboard protection service
"""
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer


class ClipboardGuard:
    """Protects sensitive data by clearing clipboard after timeout."""
    
    def __init__(self, timeout_ms: int = 5000):
        self.timeout_ms = timeout_ms
        self.timer = QTimer()
    
    def copy_sensitive_data(self, data: str):
        """Copy data to clipboard and set auto-clear timer."""
        clipboard = QApplication.clipboard()
        clipboard.setText(data)
        
        # Set timer to clear clipboard
        self.timer.singleShot(self.timeout_ms, self._clear_clipboard)
    
    def _clear_clipboard(self):
        """Clear clipboard contents."""
        clipboard = QApplication.clipboard()
        clipboard.clear()
