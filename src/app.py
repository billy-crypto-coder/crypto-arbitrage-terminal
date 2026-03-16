"""
app.py — CryptoRadar QApplication and window setup
"""
import sys
import logging

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.styles.theme import Theme
from ui.main_window import MainWindow
from ui.tray import install_tray
from database import Database

logger = logging.getLogger(__name__)


class CryptoRadarApp:
    """CryptoRadar application manager."""

    def __init__(self, start_minimized: bool = False):
        self.start_minimized = start_minimized

        # Prevent duplicate QApplication
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)

        # Don't quit when last window is hidden (tray keeps running)
        self.app.setQuitOnLastWindowClosed(False)

        self.app.setStyle("Fusion")
        self.app.setStyleSheet(Theme.get_stylesheet())
        self.app.setApplicationName("CryptoRadar")
        self.app.setApplicationDisplayName("CryptoRadar")

        # Database
        self.db = Database()
        logger.info("Database initialized")

        # Main window
        self.window = MainWindow()

        # System tray
        self.tray = install_tray(self.window, start_minimized=self.start_minimized)

    def run(self) -> int:
        """Run the application event loop."""
        if not self.start_minimized:
            self.window.show()
        else:
            logger.info("Started minimized to system tray")

        return self.app.exec()