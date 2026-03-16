"""
Alert engine service for CryptoRadar
Monitors market data and triggers alerts based on user-defined conditions.
"""
import logging
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime
from threading import Lock

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QSystemTrayIcon

from database import Database

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    """Alert type enumeration"""
    SPREAD = "spread"           # Spread between exchanges exceeds threshold
    GAS = "gas"                 # Gas price below/above threshold
    FUNDING = "funding"         # Funding rate exceeds threshold
    PRICE = "price"             # Coin price above/below threshold
    WHALE = "whale"             # Large transaction detected (placeholder)


class AlertService(QObject):
    """Service for managing and triggering alerts based on market conditions."""
    
    # Qt signal: emitted when an alert is triggered
    alert_triggered = Signal(dict)
    
    def __init__(self, tray_icon: Optional[QSystemTrayIcon] = None):
        """
        Initialize AlertService.
        
        Args:
            tray_icon: Optional QSystemTrayIcon for desktop notifications
        """
        super().__init__()
        
        self.db = Database()
        self.tray_icon = tray_icon
        self._monitoring = False
        self._lock = Lock()
        
        # Timer for periodic monitoring
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._monitor_tick)
        
        # Cache alert state to avoid duplicate checks
        self._alert_cache: Dict[int, Dict] = {}
        
        logger.info("AlertService initialized")
    
    # ====================================================================
    # CRUD Operations
    # ====================================================================
    
    def add_alert(self, alert_dict: Dict[str, Any]) -> int:
        """
        Add a new alert configuration.
        
        Args:
            alert_dict: Dictionary with alert data
                - alert_type: AlertType (spread, gas, funding, price, whale)
                - coin: Optional coin name
                - network: Optional network name (for gas alerts)
                - condition_op: 'gt' (greater than) or 'lt' (less than)
                - threshold: Threshold value
                - exchange1: Optional first exchange
                - exchange2: Optional second exchange
                - enabled: 1 (enabled) or 0 (disabled) [default: 1]
                - cooldown_seconds: Cooldown between alert triggers [default: 300]
                
        Returns:
            Alert ID of the newly created alert
        """
        try:
            # Ensure alert_type is string
            if isinstance(alert_dict.get('alert_type'), AlertType):
                alert_dict['alert_type'] = alert_dict['alert_type'].value
            
            alert_id = self.db.add_alert(alert_dict)
            self._alert_cache[alert_id] = alert_dict
            logger.info(f"Added alert {alert_id}: {alert_dict['alert_type']}")
            return alert_id
            
        except Exception as e:
            logger.error(f"Failed to add alert: {e}")
            raise
    
    def get_alerts(self) -> List[Dict]:
        """
        Get all alerts.
        
        Returns:
            List of alert dictionaries
        """
        try:
            alerts = self.db.get_alerts()
            return alerts
        except Exception as e:
            logger.error(f"Failed to get alerts: {e}")
            return []
    
    def update_alert(self, alert_id: int, data: Dict[str, Any]) -> bool:
        """
        Update an alert configuration.
        
        Args:
            alert_id: Alert ID to update
            data: Fields to update
            
        Returns:
            True if successful
        """
        try:
            result = self.db.update_alert(alert_id, data)
            if result:
                self._alert_cache.pop(alert_id, None)  # Invalidate cache
            return result
        except Exception as e:
            logger.error(f"Failed to update alert {alert_id}: {e}")
            return False
    
    def delete_alert(self, alert_id: int) -> bool:
        """
        Delete an alert configuration.
        
        Args:
            alert_id: Alert ID to delete
            
        Returns:
            True if successful
        """
        try:
            result = self.db.delete_alert(alert_id)
            if result:
                self._alert_cache.pop(alert_id, None)
            return result
        except Exception as e:
            logger.error(f"Failed to delete alert {alert_id}: {e}")
            return False
    
    def toggle_alert(self, alert_id: int, enabled: bool) -> bool:
        """
        Enable or disable an alert.
        
        Args:
            alert_id: Alert ID to toggle
            enabled: True to enable, False to disable
            
        Returns:
            True if successful
        """
        return self.update_alert(alert_id, {"enabled": 1 if enabled else 0})
    
    # ====================================================================
    # Alert Checking
    # ====================================================================
    
    def check_alerts(self, current_data: Dict[str, Any]) -> List[Dict]:
        """
        Check all enabled alerts against current market data.
        
        Args:
            current_data: Dictionary containing current market data:
                - spreads: Dict[str, float] - spread percentages by coin
                - gas_prices: Dict[str, float] - gas fees by network
                - funding_rates: Dict[str, float] - funding rates by symbol
                - prices: Dict[str, float] - coin prices in USD
                
        Returns:
            List of triggered alerts
        """
        triggered_alerts = []
        
        with self._lock:
            try:
                alerts = self.get_alerts()
                
                for alert in alerts:
                    # Skip disabled alerts
                    if not alert.get('enabled', 1):
                        continue
                    
                    # Check if alert conditions met
                    if self._evaluate_alert(alert, current_data):
                        # Check cooldown
                        if self._is_on_cooldown(alert):
                            logger.debug(
                                f"Alert {alert['id']} on cooldown, skipping trigger"
                            )
                            continue
                        
                        # Trigger the alert
                        triggered = self._trigger_alert(alert)
                        triggered_alerts.append(triggered)
                
                return triggered_alerts
                
            except Exception as e:
                logger.error(f"Error checking alerts: {e}")
                return []
    
    def _evaluate_alert(self, alert: Dict, current_data: Dict) -> bool:
        """
        Evaluate if an alert's condition is met.
        
        Args:
            alert: Alert configuration
            current_data: Current market data
            
        Returns:
            True if condition is met
        """
        try:
            alert_type = alert['alert_type']
            condition_op = alert['condition_op']
            threshold = alert['threshold']
            
            if alert_type == AlertType.SPREAD.value:
                # Check if spread exceeds threshold
                coin = alert.get('coin')
                if not coin:
                    return False
                
                spreads = current_data.get('spreads', {})
                current_value = spreads.get(coin, 0)
                
            elif alert_type == AlertType.GAS.value:
                # Check gas price against threshold
                network = alert.get('network')
                if not network:
                    return False
                
                gas_prices = current_data.get('gas_prices', {})
                current_value = gas_prices.get(network, 0)
                
            elif alert_type == AlertType.FUNDING.value:
                # Check funding rate against threshold
                coin = alert.get('coin')
                if not coin:
                    return False
                
                funding_rates = current_data.get('funding_rates', {})
                current_value = funding_rates.get(coin, 0)
                
            elif alert_type == AlertType.PRICE.value:
                # Check price against threshold
                coin = alert.get('coin')
                if not coin:
                    return False
                
                prices = current_data.get('prices', {})
                current_value = prices.get(coin, 0)
                
            elif alert_type == AlertType.WHALE.value:
                # Placeholder for whale detection
                return False
                
            else:
                logger.warning(f"Unknown alert type: {alert_type}")
                return False
            
            # Evaluate condition
            if condition_op == 'gt':
                return current_value > threshold
            elif condition_op == 'lt':
                return current_value < threshold
            else:
                logger.warning(f"Unknown condition operator: {condition_op}")
                return False
                
        except Exception as e:
            logger.error(f"Error evaluating alert {alert.get('id')}: {e}")
            return False
    
    def _is_on_cooldown(self, alert: Dict) -> bool:
        """
        Check if an alert is on cooldown.
        
        Args:
            alert: Alert configuration
            
        Returns:
            True if alert is on cooldown
        """
        try:
            last_triggered = alert.get('last_triggered')
            if not last_triggered:
                return False
            
            cooldown_seconds = alert.get('cooldown_seconds', 300)
            last_time = datetime.fromisoformat(last_triggered)
            elapsed = (datetime.now() - last_time).total_seconds()
            
            return elapsed < cooldown_seconds
            
        except Exception as e:
            logger.error(f"Error checking cooldown: {e}")
            return False
    
    def _trigger_alert(self, alert: Dict) -> Dict:
        """
        Trigger an alert and update its state.
        
        Args:
            alert: Alert configuration
            
        Returns:
            Triggered alert information dict
        """
        try:
            alert_id = alert['id']
            alert_type = alert['alert_type']
            
            # Update alert state
            now = datetime.now().isoformat()
            trigger_count = alert.get('trigger_count', 0) + 1
            
            update_data = {
                'last_triggered': now,
                'trigger_count': trigger_count
            }
            
            self.db.update_alert(alert_id, update_data)
            
            # Create triggered alert info
            triggered_info = {
                **alert,
                'triggered_at': now,
                'message': self._create_alert_message(alert)
            }
            
            # Log to alerts_log table
            self.db.add_alert_log(
                alert_type=alert_type,
                message=triggered_info['message'],
                data_dict=triggered_info
            )
            
            # Emit Qt signal
            self.alert_triggered.emit(triggered_info)
            
            # Show system notification
            self._show_notification(triggered_info)
            
            logger.warning(f"Alert triggered: {triggered_info['message']}")
            
            return triggered_info
            
        except Exception as e:
            logger.error(f"Error triggering alert: {e}")
            return {}
    
    def _create_alert_message(self, alert: Dict) -> str:
        """
        Create a human-readable message for an alert.
        
        Args:
            alert: Alert configuration
            
        Returns:
            Message string
        """
        try:
            alert_type = alert['alert_type']
            threshold = alert['threshold']
            condition_op = alert.get('condition_op', 'gt')
            op_text = 'above' if condition_op == 'gt' else 'below'
            
            if alert_type == AlertType.SPREAD.value:
                coin = alert.get('coin', 'Unknown')
                return f"🔄 Spread Alert: {coin} spread {op_text} {threshold}%"
                
            elif alert_type == AlertType.GAS.value:
                network = alert.get('network', 'Unknown')
                return f"⛽ Gas Alert: {network} gas {op_text} ${threshold}"
                
            elif alert_type == AlertType.FUNDING.value:
                coin = alert.get('coin', 'Unknown')
                return f"📊 Funding Alert: {coin} funding rate {op_text} {threshold}%"
                
            elif alert_type == AlertType.PRICE.value:
                coin = alert.get('coin', 'Unknown')
                return f"💰 Price Alert: {coin} price {op_text} ${threshold}"
                
            elif alert_type == AlertType.WHALE.value:
                return f"🐋 Whale Alert: Large transaction detected"
                
            else:
                return f"Alert triggered (type: {alert_type})"
                
        except Exception as e:
            logger.error(f"Error creating alert message: {e}")
            return "Alert triggered"
    
    def _show_notification(self, alert_info: Dict):
        """
        Show system notification for triggered alert.
        
        Args:
            alert_info: Triggered alert information
        """
        try:
            if not self.tray_icon:
                logger.debug("No tray icon available for notifications")
                return
            
            title = "CryptoRadar Alert"
            message = alert_info.get('message', 'Alert triggered')
            
            # Show notification via system tray
            # QSystemTrayIcon.showMessage(title, body, icon, duration_ms)
            # Duration in milliseconds; 0 = system dependent (usually 10 seconds)
            self.tray_icon.showMessage(
                title=title,
                msg=message,
                msecs=10000  # 10 seconds
            )
            
            logger.debug(f"Notification shown: {title} - {message}")
            
        except Exception as e:
            logger.error(f"Error showing notification: {e}")
    
    # ====================================================================
    # Monitoring
    # ====================================================================
    
    def start_monitoring(self, interval_seconds: int = 10,
                        exchange_service=None, gas_service=None,
                        funding_service=None):
        """
        Start periodic alert monitoring.
        
        Args:
            interval_seconds: Check interval in seconds [default: 10]
            exchange_service: ExchangeService instance for price data
            gas_service: GasService instance for gas data
            funding_service: FundingService instance for funding rate data
        """
        try:
            self.exchange_service = exchange_service
            self.gas_service = gas_service
            self.funding_service = funding_service
            
            self.monitor_interval = interval_seconds * 1000  # Convert to ms
            self.monitor_timer.start(self.monitor_interval)
            self._monitoring = True
            
            logger.info(f"Alert monitoring started (interval: {interval_seconds}s)")
            
        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
    
    def stop_monitoring(self):
        """Stop periodic alert monitoring."""
        try:
            self.monitor_timer.stop()
            self._monitoring = False
            logger.info("Alert monitoring stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop monitoring: {e}")
    
    def _monitor_tick(self):
        """
        Called on each monitoring interval.
        Collects current market data and checks alerts.
        """
        try:
            # Collect current market data
            current_data = {
                'spreads': self._get_current_spreads(),
                'gas_prices': self._get_current_gas_prices(),
                'funding_rates': self._get_current_funding_rates(),
                'prices': self._get_current_prices(),
                'timestamp': datetime.now().isoformat()
            }
            
            # Check alerts
            self.check_alerts(current_data)
            
        except Exception as e:
            logger.error(f"Error in monitoring tick: {e}")
    
    def _get_current_spreads(self) -> Dict[str, float]:
        """Get current spread data from exchange service."""
        try:
            if hasattr(self, 'exchange_service') and self.exchange_service:
                # TODO: Implement spread calculation logic
                # This would fetch prices from multiple exchanges and calculate diffs
                return {}
            return {}
        except Exception as e:
            logger.error(f"Error getting spreads: {e}")
            return {}
    
    def _get_current_gas_prices(self) -> Dict[str, float]:
        """Get current gas prices from gas service."""
        try:
            if hasattr(self, 'gas_service') and self.gas_service:
                # TODO: Implement gas price fetching
                # This would call gas_service.get_gas_prices()
                return {}
            return {}
        except Exception as e:
            logger.error(f"Error getting gas prices: {e}")
            return {}
    
    def _get_current_funding_rates(self) -> Dict[str, float]:
        """Get current funding rates from funding service."""
        try:
            if hasattr(self, 'funding_service') and self.funding_service:
                # Get funding rates from service
                rates = self.funding_service.fetch_all_funding_rates()
                result = {}
                for rate_data in rates:
                    coin = rate_data.get('symbol', '').split('/')[0]
                    if coin:
                        # Use max rate across exchanges for alerting
                        rate = max([r['rate'] for r in rate_data.get('rates', [])], default=0)
                        result[coin] = rate * 100  # Convert to percentage
                return result
            return {}
        except Exception as e:
            logger.error(f"Error getting funding rates: {e}")
            return {}
    
    def _get_current_prices(self) -> Dict[str, float]:
        """Get current coin prices."""
        try:
            # TODO: Implement price fetching from exchange service or external API
            return {}
        except Exception as e:
            logger.error(f"Error getting prices: {e}")
            return {}
    
    def is_monitoring(self) -> bool:
        """Check if monitoring is active."""
        return self._monitoring

