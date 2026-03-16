"""
CryptoRadar configuration and constants
"""
from pathlib import Path
import os
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Data directory
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# Database
DB_PATH = DATA_DIR / "cryptoradar.db"

# Assets
ASSETS_DIR = PROJECT_ROOT / "assets"
ICON_PATH = ASSETS_DIR / "icon.png"

# Dark theme colors
DARK_BG = "#0f0f14"
DARK_SECONDARY = "#1a1a23"
ACCENT_GREEN = "#00d084"
ACCENT_RED = "#ff4757"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#a8aac5"

# Window defaults
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800
WINDOW_MIN_WIDTH = 1024
WINDOW_MIN_HEIGHT = 600

# API defaults
REQUEST_TIMEOUT = 30
EXCHANGE_RATE_UPDATE_INTERVAL = 5000  # milliseconds

# Supported exchanges (ccxt)
SUPPORTED_EXCHANGES = [
    "binance",
    "coinbase",
    "kraken",
    "bybit",
    "okx",
]


class Settings:
    """Singleton settings manager for CryptoRadar."""
    
    _instance = None
    
    # Default settings
    DEFAULTS = {
        "general": {
            "display_currency": "USD",
            "auto_refresh_interval": "60",  # seconds
            "start_with_windows": False,
            "minimize_to_tray": True,
            "clipboard_guard_enabled": True,
        },
        "notifications": {
            "enable_sound": True,
            "enable_windows_notifications": True,
        },
    }
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize settings."""
        if self._initialized:
            return
        
        self._initialized = True
        self.app_data_dir = self._get_app_data_dir()
        self.settings_file = self.app_data_dir / "settings.json"
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Load settings from file
        self.data = self._load_settings()
    
    @staticmethod
    def _get_app_data_dir() -> Path:
        """Get application data directory."""
        if os.name == 'nt':  # Windows
            app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
            #here payload 
        else:  # Linux/Mac
            app_data = os.path.expanduser('~/.local/share')
        
        return Path(app_data) / 'CryptoRadar'
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from file or use defaults."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    loaded_data = json.load(f)
                
                # Merge with defaults (in case new keys were added)
                merged_data = self.DEFAULTS.copy()
                for key in merged_data:
                    if key in loaded_data:
                        merged_data[key].update(loaded_data[key])
                
                logger.info(f"Loaded settings from {self.settings_file}")
                return merged_data
            except Exception as e:
                logger.warning(f"Failed to load settings: {e}, using defaults")
                return self.DEFAULTS.copy()
        
        logger.info("No settings file found, using defaults")
        return self.DEFAULTS.copy()
    
    def save(self) -> None:
        """Save settings to file."""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.data, f, indent=2)
            logger.info(f"Saved settings to {self.settings_file}")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.data.get(section, {}).get(key, default)
    
    def set(self, section: str, key: str, value: Any) -> None:
        """Set a setting value."""
        if section not in self.data:
            self.data[section] = {}
        self.data[section][key] = value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire section."""
        return self.data.get(section, {})
    
    def reset_to_defaults(self) -> None:
        """Reset to default settings."""
        self.data = self.DEFAULTS.copy()
        self.save()
        logger.info("Reset settings to defaults")

# Global settings instance
settings = Settings()
