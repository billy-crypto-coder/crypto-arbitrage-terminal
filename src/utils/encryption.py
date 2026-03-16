"""
Encryption utilities and secure API key storage for CryptoRadar
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class APIKeyEncryption:
    """Simple encryption for API keys."""
    
    def __init__(self, key_file: Path):
        self.key_file = key_file
        self.cipher = self._load_or_create_key()
    
    def _load_or_create_key(self):
        """Load encryption key or create new one."""
        if self.key_file.exists():
            with open(self.key_file, "rb") as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            self.key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.key_file, "wb") as f:
                f.write(key)
        
        return Fernet(key)
    
    def encrypt(self, text: str) -> str:
        """Encrypt text."""
        return self.cipher.encrypt(text.encode()).decode()
    
    def decrypt(self, encrypted_text: str) -> str:
        """Decrypt text."""
        return self.cipher.decrypt(encrypted_text.encode()).decode()


class KeyManager:
    """Secure management of API keys with encryption."""
    
    # Supported exchanges
    SUPPORTED_EXCHANGES = ["binance", "bybit", "okx", "bitget", "kraken", "dydx"]
    
    def __init__(self):
        """Initialize the KeyManager."""
        self.app_data_dir = self._get_app_data_dir()
        self.key_file = self.app_data_dir / "cryptoradar_key.bin"
        self.keys_file = self.app_data_dir / "keys.enc"
        
        # Create app data directory if it doesn't exist
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption cipher
        self._cipher = self._load_or_create_cipher()
    
    @staticmethod
    def _get_app_data_dir() -> Path:
        """Get the application data directory."""
        if os.name == 'nt':  # Windows
            app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        else:  # Linux/Mac
            app_data = os.path.expanduser('~/.local/share')
        
        return Path(app_data) / 'CryptoRadar'
    
    def _load_or_create_cipher(self) -> Fernet:
        """Load encryption key or create new one."""
        if self.key_file.exists():
            try:
                with open(self.key_file, "rb") as f:
                    key = f.read()
                return Fernet(key)
            except Exception as e:
                logger.warning(f"Failed to load encryption key, creating new one: {e}")
                return self._create_new_cipher()
        else:
            return self._create_new_cipher()
    
    def _create_new_cipher(self) -> Fernet:
        """Create a new encryption cipher and save the key."""
        try:
            key = Fernet.generate_key()
            
            # Save with restricted permissions (Windows)
            self.key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.key_file, "wb") as f:
                f.write(key)
            
            # On Windows, set file permissions to be readable only by the user
            if os.name == 'nt':
                os.chmod(self.key_file, 0o600)
            
            logger.info(f"Created new encryption key at {self.key_file}")
            return Fernet(key)
        except Exception as e:
            logger.error(f"Failed to create encryption cipher: {e}")
            raise
    
    def save_api_keys(
        self,
        exchange: str,
        api_key: str,
        api_secret: str,
        passphrase: str = ""
    ) -> None:
        """
        Encrypt and save API keys for an exchange.
        
        Args:
            exchange: Exchange name (e.g., "binance", "okx")
            api_key: API key
            api_secret: API secret
            passphrase: Optional passphrase (for OKX, etc.)
        """
        if exchange.lower() not in self.SUPPORTED_EXCHANGES:
            raise ValueError(f"Unsupported exchange: {exchange}")
        
        try:
            # Load existing keys
            keys_dict = self.load_api_keys()
            
            # Update with new keys
            keys_dict[exchange.lower()] = {
                "key": api_key,
                "secret": api_secret,
                "passphrase": passphrase or ""
            }
            
            # Encrypt and save
            json_str = json.dumps(keys_dict)
            encrypted_data = self._cipher.encrypt(json_str.encode()).decode()
            
            with open(self.keys_file, "w") as f:
                f.write(encrypted_data)
            
            # Restrict file permissions
            if os.name == 'nt':
                os.chmod(self.keys_file, 0o600)
            
            logger.info(f"Saved API keys for {exchange}")
        except Exception as e:
            logger.error(f"Failed to save API keys: {e}")
            raise
    
    def load_api_keys(self) -> Dict[str, Dict]:
        """
        Load and decrypt all API keys.
        
        Returns:
            Dictionary with structure:
            {
                "binance": {"key": "...", "secret": "...", "passphrase": ""},
                "okx": {"key": "...", "secret": "...", "passphrase": "..."},
                ...
            }
            Returns empty dict if file doesn't exist.
        """
        if not self.keys_file.exists():
            logger.debug("Keys file not found, returning empty dict")
            return {}
        
        try:
            with open(self.keys_file, "r") as f:
                encrypted_data = f.read()
            
            # Decrypt
            decrypted_data = self._cipher.decrypt(encrypted_data.encode()).decode()
            keys_dict = json.loads(decrypted_data)
            
            logger.debug(f"Loaded keys for exchanges: {list(keys_dict.keys())}")
            return keys_dict
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse keys JSON: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load API keys: {e}")
            return {}
    
    def get_api_keys(self, exchange: str) -> Optional[Dict]:
        """
        Get API keys for a specific exchange.
        
        Args:
            exchange: Exchange name
            
        Returns:
            Dictionary with "key", "secret", "passphrase" or None if not found
        """
        all_keys = self.load_api_keys()
        return all_keys.get(exchange.lower())
    
    def delete_api_keys(self, exchange: str) -> None:
        """
        Delete API keys for a specific exchange.
        
        Args:
            exchange: Exchange name
        """
        try:
            keys_dict = self.load_api_keys()
            
            if exchange.lower() in keys_dict:
                del keys_dict[exchange.lower()]
                
                # If no more keys, delete the file
                if not keys_dict:
                    self.keys_file.unlink(missing_ok=True)
                    logger.info(f"Deleted all keys (file removed)")
                else:
                    # Re-save without the deleted exchange
                    json_str = json.dumps(keys_dict)
                    encrypted_data = self._cipher.encrypt(json_str.encode()).decode()
                    
                    with open(self.keys_file, "w") as f:
                        f.write(encrypted_data)
                    
                    logger.info(f"Deleted API keys for {exchange}")
            else:
                logger.warning(f"No keys found for {exchange}")
        except Exception as e:
            logger.error(f"Failed to delete API keys: {e}")
            raise
    
    def has_api_keys(self, exchange: str) -> bool:
        """Check if API keys exist for an exchange."""
        return exchange.lower() in self.load_api_keys()
    
    def list_configured_exchanges(self) -> list:
        """Get list of exchanges with configured API keys."""
        return list(self.load_api_keys().keys())
    
    def test_connection(
        self,
        exchange: str,
        api_key: str,
        api_secret: str,
        passphrase: str = ""
    ) -> Tuple[bool, str]:
        """
        Test connection to an exchange with the provided credentials.
        
        Args:
            exchange: Exchange name
            api_key: API key
            api_secret: API secret
            passphrase: Optional passphrase
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            import ccxt
        except ImportError:
            return False, "ccxt library not installed"
        
        try:
            # Get exchange class
            exchange_class = getattr(ccxt, exchange.lower(), None)
            if not exchange_class:
                return False, f"Unknown exchange: {exchange}"
            
            # Create exchange instance with credentials
            exchange_instance = exchange_class({
                'apiKey': api_key,
                'secret': api_secret,
                'passphrase': passphrase if passphrase else None,
                'enableRateLimit': True,
                'timeout': 5000,
            })
            
            # Try a read-only API call
            try:
                balance = exchange_instance.fetch_balance()
                if balance:
                    return True, f"✓ Connected to {exchange}"
            except ccxt.AuthenticationError:
                return False, "✗ Authentication failed - Invalid API credentials"
            except ccxt.NetworkError as e:
                return False, f"✗ Network error: {str(e)}"
            except Exception as e:
                # Some exchanges don't return balance without proper permissions
                # Try fetch_status instead
                try:
                    status = exchange_instance.fetch_status()
                    return True, f"✓ Connected to {exchange}"
                except ccxt.AuthenticationError:
                    return False, "✗ Authentication failed - Invalid API credentials"
                except Exception:
                    return False, f"✗ Error: {str(e)}"
        
        except ModuleNotFoundError:
            return False, "ccxt library not installed"
        except Exception as e:
            return False, f"✗ Error: {str(e)}"
