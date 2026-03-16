"""
Database module for CryptoRadar - SQLite database management
"""
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager for CryptoRadar trades and alerts (Singleton)"""
    
    _instance: Optional['Database'] = None
    _lock = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize database connection and create tables if needed"""
        if hasattr(self, '_initialized'):
            return
        
        # Determine app data directory
        if Path.home().name == 'Smoky':  # Windows
            app_data = Path.home() / 'AppData' / 'Roaming' / 'CryptoRadar'
        else:  # Linux
            app_data = Path.home() / '.config' / 'CryptoRadar'
        
        app_data.mkdir(parents=True, exist_ok=True)
        
        self.db_path = app_data / 'cryptoradar.db'
        self.conn = None
        self._connect()
        self._create_tables()
        self._initialized = True
        logger.info(f"Database initialized at {self.db_path}")
    
    def _connect(self):
        """Establish database connection"""
        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")
            logger.info("Database connection established")
        except sqlite3.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def _create_tables(self):
        """Create tables if they don't exist"""
        cursor = self.conn.cursor()
        
        try:
            # Trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT DEFAULT (datetime('now')),
                    trade_date TEXT NOT NULL,
                    trade_type TEXT NOT NULL,
                    coin TEXT NOT NULL,
                    buy_exchange TEXT NOT NULL,
                    sell_exchange TEXT,
                    buy_price REAL NOT NULL,
                    sell_price REAL,
                    amount REAL NOT NULL,
                    amount_usdt REAL,
                    gross_profit REAL DEFAULT 0,
                    total_fees REAL DEFAULT 0,
                    net_profit REAL DEFAULT 0,
                    notes TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]'
                )
            """)
            
            # Alerts configuration table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    coin TEXT,
                    network TEXT,
                    condition_op TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    exchange1 TEXT,
                    exchange2 TEXT,
                    enabled INTEGER DEFAULT 1,
                    cooldown_seconds INTEGER DEFAULT 300,
                    created_at TEXT DEFAULT (datetime('now')),
                    last_triggered TEXT,
                    trigger_count INTEGER DEFAULT 0
                )
            """)
            
            # Alerts log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT (datetime('now')),
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    data TEXT DEFAULT '{}'
                )
            """)
            
            self.conn.commit()
            logger.info("Database tables created/verified")
        except sqlite3.Error as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    # ====================================================================
    # Trade methods
    # ====================================================================
    
    def add_trade(self, trade_dict: Dict[str, Any]) -> int:
        """
        Add a new trade to the database.
        
        Args:
            trade_dict: Dictionary with trade data
            
        Returns:
            Trade ID of the inserted trade
        """
        cursor = self.conn.cursor()
        
        try:
            # Ensure tags is JSON string
            if 'tags' in trade_dict and isinstance(trade_dict['tags'], list):
                trade_dict['tags'] = json.dumps(trade_dict['tags'])
            elif 'tags' not in trade_dict:
                trade_dict['tags'] = '[]'
            
            # Build insert query
            columns = ', '.join(trade_dict.keys())
            placeholders = ', '.join(['?' for _ in trade_dict])
            values = tuple(trade_dict.values())
            
            query = f"INSERT INTO trades ({columns}) VALUES ({placeholders})"
            cursor.execute(query, values)
            self.conn.commit()
            
            trade_id = cursor.lastrowid
            logger.info(f"Added trade with ID {trade_id}")
            return trade_id
            
        except sqlite3.Error as e:
            logger.error(f"Failed to add trade: {e}")
            self.conn.rollback()
            raise
    
    def get_trades(self, limit: int = 50, offset: int = 0, coin: Optional[str] = None,
                   trade_type: Optional[str] = None, date_from: Optional[str] = None,
                   date_to: Optional[str] = None) -> List[Dict]:
        """
        Retrieve trades with optional filtering.
        
        Args:
            limit: Maximum number of trades to return
            offset: Number of trades to skip
            coin: Filter by coin (e.g., 'BTC')
            trade_type: Filter by trade type
            date_from: Filter trades from this date (ISO 8601)
            date_to: Filter trades until this date (ISO 8601)
            
        Returns:
            List of trade dictionaries
        """
        cursor = self.conn.cursor()
        
        try:
            query = "SELECT * FROM trades WHERE 1=1"
            params = []
            
            if coin:
                query += " AND coin = ?"
                params.append(coin)
            
            if trade_type:
                query += " AND trade_type = ?"
                params.append(trade_type)
            
            if date_from:
                query += " AND trade_date >= ?"
                params.append(date_from)
            
            if date_to:
                query += " AND trade_date <= ?"
                params.append(date_to)
            
            query += " ORDER BY trade_date DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert rows to dictionaries
            trades = []
            for row in rows:
                trade = dict(row)
                # Parse tags JSON
                if 'tags' in trade and isinstance(trade['tags'], str):
                    try:
                        trade['tags'] = json.loads(trade['tags'])
                    except json.JSONDecodeError:
                        trade['tags'] = []
                trades.append(trade)
            
            return trades
            
        except sqlite3.Error as e:
            logger.error(f"Failed to get trades: {e}")
            raise
    
    def update_trade(self, trade_id: int, trade_dict: Dict[str, Any]) -> bool:
        """
        Update a trade.
        
        Args:
            trade_id: ID of the trade to update
            trade_dict: Dictionary with updated data
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        
        try:
            # Ensure tags is JSON string
            if 'tags' in trade_dict and isinstance(trade_dict['tags'], list):
                trade_dict['tags'] = json.dumps(trade_dict['tags'])
            
            # Build update query
            set_clause = ', '.join([f"{key} = ?" for key in trade_dict.keys()])
            values = list(trade_dict.values())
            values.append(trade_id)
            
            query = f"UPDATE trades SET {set_clause} WHERE id = ?"
            cursor.execute(query, values)
            self.conn.commit()
            
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Updated trade ID {trade_id}")
            else:
                logger.warning(f"Trade ID {trade_id} not found")
            
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Failed to update trade: {e}")
            self.conn.rollback()
            raise
    
    def delete_trade(self, trade_id: int) -> bool:
        """
        Delete a trade.
        
        Args:
            trade_id: ID of the trade to delete
            
        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
            self.conn.commit()
            
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Deleted trade ID {trade_id}")
            else:
                logger.warning(f"Trade ID {trade_id} not found")
            
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Failed to delete trade: {e}")
            self.conn.rollback()
            raise
    
    def get_trade_stats(self, date_from: Optional[str] = None,
                       date_to: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate trade statistics.
        
        Args:
            date_from: Filter from this date (ISO 8601)
            date_to: Filter until this date (ISO 8601)
            
        Returns:
            Dictionary with trade statistics
        """
        cursor = self.conn.cursor()
        
        try:
            # Build base query
            where_clause = "WHERE 1=1"
            params = []
            
            if date_from:
                where_clause += " AND trade_date >= ?"
                params.append(date_from)
            
            if date_to:
                where_clause += " AND trade_date <= ?"
                params.append(date_to)
            
            # Total trades and profit stats
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(net_profit) as total_net_profit,
                    SUM(CASE WHEN net_profit > 0 THEN 1 ELSE 0 END) as win_count,
                    SUM(CASE WHEN net_profit < 0 THEN 1 ELSE 0 END) as loss_count,
                    AVG(net_profit) as avg_profit,
                    MAX(net_profit) as best_trade,
                    MIN(net_profit) as worst_trade
                FROM trades
                {where_clause}
            """, params)
            
            row = cursor.fetchone()
            stats = dict(row) if row else {}
            
            # Calculate win rate
            total = stats.get('total_trades', 0) or 0
            wins = stats.get('win_count', 0) or 0
            stats['win_rate'] = (wins / total * 100) if total > 0 else 0
            
            # Profit by day
            cursor.execute(f"""
                SELECT trade_date, SUM(net_profit) as profit
                FROM trades
                {where_clause}
                GROUP BY trade_date
                ORDER BY trade_date DESC
            """, params)
            stats['profit_by_day'] = [(row[0], row[1]) for row in cursor.fetchall()]
            
            # Profit by coin
            cursor.execute(f"""
                SELECT coin, SUM(net_profit) as profit
                FROM trades
                {where_clause}
                GROUP BY coin
                ORDER BY profit DESC
            """, params)
            stats['profit_by_coin'] = [(row[0], row[1]) for row in cursor.fetchall()]
            
            # Profit by exchange (combining buy and sell)
            cursor.execute(f"""
                SELECT buy_exchange, SUM(net_profit) as profit
                FROM trades
                {where_clause}
                GROUP BY buy_exchange
                ORDER BY profit DESC
            """, params)
            stats['profit_by_exchange'] = [(row[0], row[1]) for row in cursor.fetchall()]
            
            logger.info(f"Calculated trade stats: {total} trades, ${stats.get('total_net_profit', 0):.2f} profit")
            return stats
            
        except sqlite3.Error as e:
            logger.error(f"Failed to calculate stats: {e}")
            raise
    
    # ====================================================================
    # Alert log methods
    # ====================================================================
    
    def add_alert_log(self, alert_type: str, message: str, data_dict: Optional[Dict] = None):
        """
        Log an alert.
        
        Args:
            alert_type: Type of alert (e.g., 'anomaly', 'error', 'info')
            message: Alert message
            data_dict: Optional dictionary with additional data
        """
        cursor = self.conn.cursor()
        
        try:
            data_json = json.dumps(data_dict) if data_dict else '{}'
            
            cursor.execute("""
                INSERT INTO alerts_log (alert_type, message, data)
                VALUES (?, ?, ?)
            """, (alert_type, message, data_json))
            
            self.conn.commit()
            logger.debug(f"Logged alert: {alert_type} - {message}")
            
        except sqlite3.Error as e:
            logger.error(f"Failed to log alert: {e}")
            self.conn.rollback()
            raise
    
    def get_alert_logs(self, limit: int = 100) -> List[Dict]:
        """
        Retrieve recent alert logs.
        
        Args:
            limit: Maximum number of logs to return
            
        Returns:
            List of alert log dictionaries
        """
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM alerts_log
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            
            # Convert rows to dictionaries and parse data JSON
            logs = []
            for row in rows:
                log = dict(row)
                if 'data' in log and isinstance(log['data'], str):
                    try:
                        log['data'] = json.loads(log['data'])
                    except json.JSONDecodeError:
                        log['data'] = {}
                logs.append(log)
            
            return logs
            
        except sqlite3.Error as e:
            logger.error(f"Failed to get alert logs: {e}")
            raise
    
    # ====================================================================
    # Alert configuration methods
    # ====================================================================
    
    def add_alert(self, alert_dict: Dict[str, Any]) -> int:
        """
        Add a new alert configuration.
        
        Args:
            alert_dict: Dictionary with alert configuration data
            
        Returns:
            Alert ID of the inserted alert
        """
        cursor = self.conn.cursor()
        
        try:
            columns = ', '.join(alert_dict.keys())
            placeholders = ', '.join(['?' for _ in alert_dict])
            values = tuple(alert_dict.values())
            
            query = f"INSERT INTO alerts ({columns}) VALUES ({placeholders})"
            cursor.execute(query, values)
            self.conn.commit()
            
            alert_id = cursor.lastrowid
            logger.info(f"Added alert with ID {alert_id}")
            return alert_id
            
        except sqlite3.Error as e:
            logger.error(f"Failed to add alert: {e}")
            self.conn.rollback()
            raise
    
    def get_alerts(self) -> List[Dict]:
        """
        Retrieve all alerts.
        
        Returns:
            List of alert dictionaries
        """
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM alerts ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            logger.error(f"Failed to get alerts: {e}")
            raise
    
    def update_alert(self, alert_id: int, alert_dict: Dict[str, Any]) -> bool:
        """
        Update an alert configuration.
        
        Args:
            alert_id: Alert ID to update
            alert_dict: Dictionary with fields to update
            
        Returns:
            True if update successful
        """
        cursor = self.conn.cursor()
        
        try:
            set_clause = ', '.join([f"{k} = ?" for k in alert_dict.keys()])
            values = list(alert_dict.values()) + [alert_id]
            
            query = f"UPDATE alerts SET {set_clause} WHERE id = ?"
            cursor.execute(query, values)
            self.conn.commit()
            
            logger.info(f"Updated alert {alert_id}")
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            logger.error(f"Failed to update alert: {e}")
            self.conn.rollback()
            raise
    
    def delete_alert(self, alert_id: int) -> bool:
        """
        Delete an alert configuration.
        
        Args:
            alert_id: Alert ID to delete
            
        Returns:
            True if delete successful
        """
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
            self.conn.commit()
            
            logger.info(f"Deleted alert {alert_id}")
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            logger.error(f"Failed to delete alert: {e}")
            self.conn.rollback()
            raise
    
    # ====================================================================
    # Utility methods
    # ====================================================================
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.close()
        except:
            pass
