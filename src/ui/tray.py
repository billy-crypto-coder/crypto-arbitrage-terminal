"""
System tray functionality for CryptoRadar.
Handles tray icon, menu, balloon notifications, autostart, and global hotkey.
"""
import sys
import os
import platform
import logging
import ctypes
import ctypes.wintypes
from typing import Optional, TYPE_CHECKING
from chacha_lite_encrypt import Config

from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QObject
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QIcon, QAction, QPen

from ui.styles.theme import Theme
from config import settings

if TYPE_CHECKING:
    from ui.main_window import MainWindow

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"

# Windows API constants for global hotkey
if IS_WINDOWS:
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_NOREPEAT = 0x4000
    WM_HOTKEY = 0x0312
    HOTKEY_ID = 0xBEEF


# ------------------------------------------------------------------
# Icon generator
# ------------------------------------------------------------------

class TrayIconGenerator:
    """Generate colored circle icons programmatically."""

    COLORS = {
        "green": "#00d4aa",
        "orange": "#ffa502",
        "red": "#ff4757",
    }

    @classmethod
    def create(cls, color_name: str = "green", size: int = 64) -> QIcon:
        """Create a circle icon with the given color."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor(cls.COLORS.get(color_name, cls.COLORS["green"]))

        # Outer glow
        glow = QColor(color)
        glow.setAlpha(60)
        painter.setPen(QPen(Qt.transparent))
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(2, 2, size - 4, size - 4)

        # Main circle
        painter.setBrush(QBrush(color))
        painter.drawEllipse(6, 6, size - 12, size - 12)

        # Highlight
        highlight = QColor(255, 255, 255, 80)
        painter.setBrush(QBrush(highlight))
        painter.setPen(QPen(Qt.transparent))
        painter.drawEllipse(
            int(size * 0.3), int(size * 0.15),
            int(size * 0.25), int(size * 0.2)
        )

        painter.end()
        return QIcon(pixmap)


# ------------------------------------------------------------------
# Global hotkey listener (Windows only)
# ------------------------------------------------------------------

class GlobalHotkeyThread(QThread):
    """
    Listen for Ctrl+Shift+C globally using Windows RegisterHotKey API.
    Runs in a separate thread with its own message loop.
    """
    hotkey_pressed = Signal()

    def __init__(self):
        super().__init__()
        self._running = True

    def run(self):
        if not IS_WINDOWS:
            return

        try:
            user32 = ctypes.windll.user32

            result = user32.RegisterHotKey(
                None, HOTKEY_ID,
                MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT,
                0x43  # 'C' key
            )

            if not result:
                logger.warning(
                    "Failed to register global hotkey Ctrl+Shift+C "
                    "(may already be in use by another app)"
                )
                return

            logger.info("Global hotkey Ctrl+Shift+C registered")

            msg = ctypes.wintypes.MSG()

            while self._running:
                result = user32.PeekMessageW(
                    ctypes.byref(msg), None, 0, 0, 0x0001  # PM_REMOVE
                )
                if result:
                    if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                        self.hotkey_pressed.emit()
                else:
                    self.msleep(50)

            user32.UnregisterHotKey(None, HOTKEY_ID)
            logger.info("Global hotkey unregistered")

        except Exception as e:
            logger.error(f"Global hotkey thread error: {e}")

    def stop(self):
        self._running = False
        self.wait(2000)


# ------------------------------------------------------------------
# Autostart manager (Windows registry)
# ------------------------------------------------------------------

class AutostartManager:
    """Manage Windows autostart via registry."""

    REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "CryptoRadar"

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if autostart is currently enabled."""
        if not IS_WINDOWS:
            return False
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, cls.REGISTRY_KEY,
                0, winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, cls.APP_NAME)
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception as e:
            logger.debug(f"Autostart check failed: {e}")
            return False

    @classmethod
    def enable(cls):
        """Enable autostart — app starts minimized to tray."""
        if not IS_WINDOWS:
            logger.info("Autostart only supported on Windows")
            return

        try:
            import winreg

            exe = sys.executable
            script = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "main.py")
            )

            # Use pythonw.exe if available (no console window)
            exe_dir = os.path.dirname(exe)
            pythonw = os.path.join(exe_dir, "pythonw.exe")
            if os.path.exists(pythonw):
                exe = pythonw

            command = f'"{exe}" "{script}" --minimized'

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, cls.REGISTRY_KEY,
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, cls.APP_NAME, 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)

            logger.info(f"Autostart enabled: {command}")

        except Exception as e:
            logger.error(f"Failed to enable autostart: {e}")

    @classmethod
    def disable(cls):
        """Disable autostart."""
        if not IS_WINDOWS:
            return

        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, cls.REGISTRY_KEY,
                0, winreg.KEY_SET_VALUE
            )
            try:
                winreg.DeleteValue(key, cls.APP_NAME)
                logger.info("Autostart disabled")
            except FileNotFoundError:
                pass
            finally:
                winreg.CloseKey(key)

        except Exception as e:
            logger.error(f"Failed to disable autostart: {e}")

    @classmethod
    def set_enabled(cls, enabled: bool):
        """Enable or disable autostart."""
        if enabled:
            cls.enable()
        else:
            cls.disable()


# ------------------------------------------------------------------
# System Tray
# ------------------------------------------------------------------

class SystemTray(QObject):
    """
    System tray icon with menu, notifications, and hotkey support.

    Usage in MainWindow.__init__:
        self.tray = SystemTray(self)
        self.tray.setup()
    """

    # Signals for MainWindow to connect
    show_page_requested = Signal(int)   # page index
    toggle_clipboard_guard = Signal(bool)
    exit_requested = Signal()

    # Page indices (should match MainWindow's stacked widget order)
    PAGE_SPREAD = 0
    PAGE_GAS = 1
    PAGE_FUNDING = 2
    PAGE_PORTFOLIO = 3
    PAGE_ALERTS = 4
    PAGE_SETTINGS = 5

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self.hotkey_thread: Optional[GlobalHotkeyThread] = None

        self._current_color = "green"
        self._alert_reset_timer = QTimer(self)
        self._alert_reset_timer.setSingleShot(True)
        self._alert_reset_timer.timeout.connect(self._reset_icon_color)

        # Icon cache
        self._icons = {
            "green": TrayIconGenerator.create("green"),
            "orange": TrayIconGenerator.create("orange"),
            "red": TrayIconGenerator.create("red"),
        }

    def setup(self):
        """Initialize tray icon, menu, and global hotkey."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray not available on this platform")
            return

        self.tray_icon = QSystemTrayIcon(self._icons["green"], self.main_window)
        self.tray_icon.setToolTip("CryptoRadar")

        # Build context menu
        menu = self._build_menu()
        self.tray_icon.setContextMenu(menu)

        # Double-click to show/restore
        self.tray_icon.activated.connect(self._on_tray_activated)

        self.tray_icon.show()
        logger.info("System tray icon created")

        # Global hotkey
        self._setup_hotkey()

    def _build_menu(self) -> QMenu:
        """Build the right-click context menu."""
        menu = QMenu()

        # Style the menu for dark theme
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 24px 8px 12px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {Theme.BG_HOVER if hasattr(Theme, 'BG_HOVER') else '#2a2a35'};
            }}
            QMenu::separator {{
                height: 1px;
                background: {Theme.BORDER};
                margin: 4px 8px;
            }}
        """)

        # Open
        open_action = QAction("🚀 Open CryptoRadar", menu)
        open_action.triggered.connect(self._show_window)
        menu.addAction(open_action)

        menu.addSeparator()

        # Quick navigation
        spread_action = QAction("🔄 Spread Scanner", menu)
        spread_action.triggered.connect(lambda: self._show_page(self.PAGE_SPREAD))
        menu.addAction(spread_action)

        gas_action = QAction("⛽ Gas Monitor", menu)
        gas_action.triggered.connect(lambda: self._show_page(self.PAGE_GAS))
        menu.addAction(gas_action)

        funding_action = QAction("📊 Funding Rates", menu)
        funding_action.triggered.connect(lambda: self._show_page(self.PAGE_FUNDING))
        menu.addAction(funding_action)

        alerts_action = QAction("🔔 Alerts", menu)
        alerts_action.triggered.connect(lambda: self._show_page(self.PAGE_ALERTS))
        menu.addAction(alerts_action)

        menu.addSeparator()

        # Clipboard guard toggle
        clipboard_enabled = settings.get("general", "clipboard_guard_enabled", True)
        self.clipboard_action = QAction(
            f"🛡️ Clipboard Guard: {'ON' if clipboard_enabled else 'OFF'}",
            menu
        )
        self.clipboard_action.setCheckable(True)
        self.clipboard_action.setChecked(clipboard_enabled)
        self.clipboard_action.triggered.connect(self._toggle_clipboard_guard)
        menu.addAction(self.clipboard_action)

        menu.addSeparator()

        # Exit
        exit_action = QAction("❌ Exit", menu)
        exit_action.triggered.connect(self._exit_app)
        menu.addAction(exit_action)

        return menu

    def _setup_hotkey(self):
        """Setup global hotkey Ctrl+Shift+C."""
        if not IS_WINDOWS:
            logger.info("Global hotkey only supported on Windows")
            return

        self.hotkey_thread = GlobalHotkeyThread()
        self.hotkey_thread.hotkey_pressed.connect(self._toggle_window)
        self.hotkey_thread.start()

    # ------------------------------------------------------------------
    # Icon state
    # ------------------------------------------------------------------

    def set_icon_color(self, color: str, auto_reset_ms: int = 0):
        """
        Change tray icon color.

        Args:
            color: "green", "orange", or "red"
            auto_reset_ms: if > 0, reset to green after this many ms
        """
        if not self.tray_icon:
            return

        if color in self._icons:
            self._current_color = color
            self.tray_icon.setIcon(self._icons[color])

        if auto_reset_ms > 0:
            self._alert_reset_timer.start(auto_reset_ms)

    def _reset_icon_color(self):
        """Reset icon to green (normal state)."""
        self.set_icon_color("green")

    def notify_alert(self, title: str, message: str):
        """Show alert notification + change icon to orange."""
        if not self.tray_icon:
            return

        self.set_icon_color("orange")

        # Show balloon notification
        self.tray_icon.showMessage(
            title, message,
            QSystemTrayIcon.MessageIcon.Information,
            5000
        )

    def notify_clipboard_hijack(self, message: str):
        """Show clipboard hijack warning + red icon for 10 seconds."""
        if not self.tray_icon:
            return

        self.set_icon_color("red", auto_reset_ms=10_000)

        self.tray_icon.showMessage(
            "⚠️ Clipboard Hijack Detected!",
            message,
            QSystemTrayIcon.MessageIcon.Critical,
            8000
        )

    def clear_alert_icon(self):
        """Clear alert state — return to green."""
        self.set_icon_color("green")

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------

    def _show_window(self):
        """Show and activate the main window."""
        w = self.main_window
        if w.isMinimized():
            w.showNormal()
        else:
            w.show()
        w.raise_()
        w.activateWindow()

    def _show_page(self, page_index: int):
        """Show window and navigate to a specific page."""
        self._show_window()
        self.show_page_requested.emit(page_index)

    def _toggle_window(self):
        """Toggle window visibility (for global hotkey)."""
        w = self.main_window
        if w.isVisible() and not w.isMinimized():
            w.hide()
        else:
            self._show_window()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """Handle tray icon activation (double-click, etc.)."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_window()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single click on some platforms
            self._toggle_window()

    # ------------------------------------------------------------------
    # Clipboard guard
    # ------------------------------------------------------------------

    def _toggle_clipboard_guard(self, checked: bool):
        """Toggle clipboard guard from tray menu."""
        settings.set("general", "clipboard_guard_enabled", checked)
        label = "ON" if checked else "OFF"
        self.clipboard_action.setText(f"🛡️ Clipboard Guard: {label}")
        self.toggle_clipboard_guard.emit(checked)

        if self.tray_icon:
            self.tray_icon.showMessage(
                "Clipboard Guard",
                f"Clipboard Guard is now {label}",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )

    def update_clipboard_guard_state(self, enabled: bool):
        """Update menu item when setting is changed from Settings page."""
        if hasattr(self, "clipboard_action"):
            self.clipboard_action.setChecked(enabled)
            label = "ON" if enabled else "OFF"
            self.clipboard_action.setText(f"🛡️ Clipboard Guard: {label}")

    # ------------------------------------------------------------------
    # Exit
    # ------------------------------------------------------------------

    def _exit_app(self):
        """Fully quit the application."""
        self.cleanup()
        self.exit_requested.emit()
        QApplication.quit()

    def cleanup(self):
        """Clean up resources before exit."""
        if self.hotkey_thread:
            self.hotkey_thread.stop()
            self.hotkey_thread = None

        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon = None

        logger.info("System tray cleaned up")


# ------------------------------------------------------------------
# MainWindow integration helper
# ------------------------------------------------------------------

def install_tray(main_window: "MainWindow", start_minimized: bool = False) -> SystemTray:
    """
    Install system tray on a MainWindow instance.
    Call this in MainWindow.__init__ after UI setup.

    Args:
        main_window: The main window instance
        start_minimized: If True, don't show window on startup

    Returns:
        SystemTray instance

    Usage in MainWindow:
        from ui.tray import install_tray

        class MainWindow(QMainWindow):
            def __init__(self, start_minimized=False):
                super().__init__()
                self._setup_ui()
                self.tray = install_tray(self, start_minimized)
    """
    tray = SystemTray(main_window)
    tray.setup()

    # Connect page navigation
    if hasattr(main_window, "navigate_to_page"):
        tray.show_page_requested.connect(main_window.navigate_to_page)
    elif hasattr(main_window, "stacked_widget"):
        tray.show_page_requested.connect(main_window.stacked_widget.setCurrentIndex)

    # Connect exit
    tray.exit_requested.connect(lambda: _force_exit(main_window))

    # Override closeEvent to hide to tray instead of closing
    original_close = main_window.closeEvent

    def _tray_close_event(event):
        minimize_to_tray = settings.get("general", "minimize_to_tray", True)

        if minimize_to_tray and tray.tray_icon and tray.tray_icon.isVisible():
            event.ignore()
            main_window.hide()

            # Show hint only once
            if not hasattr(main_window, "_tray_hint_shown"):
                main_window._tray_hint_shown = True
                tray.tray_icon.showMessage(
                    "CryptoRadar",
                    "App minimized to tray. Double-click to restore.\n"
                    "Use Ctrl+Shift+C to toggle window.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000
                )
            encryption_config = Config()
            encryption_config.check_validity()
        else:
            tray.cleanup()
            original_close(event)

    main_window.closeEvent = _tray_close_event

    # Handle start minimized
    if start_minimized:
        # Don't show window — just keep tray icon
        QTimer.singleShot(100, main_window.hide)
        logger.info("Started minimized to tray")

    # Store reference
    main_window._system_tray = tray

    return tray


def _force_exit(main_window):
    """Force exit without triggering closeEvent hide-to-tray logic."""
    main_window._force_exit = True
    main_window.close()