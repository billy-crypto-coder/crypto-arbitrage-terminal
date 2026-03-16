"""
Direct HTTP API exchange service for CryptoRadar - Using requests library.
Bypasses CCXT to avoid configuration issues - uses direct API calls.
"""
import requests
import time
from typing import Optional, List, Dict, Any
import logging
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API endpoints for each exchange
EXCHANGE_APIS = {
    "binance": {
        "base": "https://api.binance.com",
        "endpoint": "/api/v3/ticker/24hr?symbol={symbol_upper}"
    },
    "kraken": {
        "base": "https://api.kraken.com",
        "endpoint": "/0/public/Ticker?pair={symbol_kraken}"
    },
    "coinbase": {
        "base": "https://api.coinbase.com",
        "endpoint": "/v2/prices/{symbol_cb}/spot"
    },
    "okx": {
        "base": "https://www.okx.com",
        "endpoint": "/api/v5/market/ticker?instId={symbol_okx}"
    },
    "bybit": {
        "base": "https://api.bybit.com",
        "endpoint": "/v5/market/tickers?category=spot&symbol={symbol_upper}"
    },
    "kucoin": {
        "base": "https://api.kucoin.com",
        "endpoint": "/api/v1/market/stats?symbol={symbol}"
    },
    "gateio": {
        "base": "https://api.gateio.ws",
        "endpoint": "/api/v4/spot/tickers?currency_pair={symbol_gate}"
    },
    "mexc": {
        "base": "https://api.mexc.com",
        "endpoint": "/api/v1/market/ticker?symbol={symbol_gate}"
    },
    "htx": {
        "base": "https://api.huobi.pro",
        "endpoint": "/market/detail?symbol={symbol_lower}"
    },
    "bitget": {
        "base": "https://api.bitget.com",
        "endpoint": "/api/v2/spot/market/tickers?symbol={symbol_upper}"
    }
}


class ExchangeService:
    """Service for fetching crypto ticker data using direct HTTP requests."""
    
    # Supported exchanges
    SUPPORTED_EXCHANGES = [
        "binance", "bybit", "okx", "kucoin", "kraken", "gateio",
        "mexc", "htx", "coinbase", "bitget"
    ]
    
    # Supported cryptos (all paired with USDT)
    SUPPORTED_CRYPTOS = [
        "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "MATIC",
        "DOT", "LINK", "UNI", "ATOM", "ARB", "OP", "PEPE", "WLD"
    ]
    
    # Cache TTL in seconds
    CACHE_TTL = 3
    
    def __init__(self, exchanges: List[str] = None):
        """
        Initialize exchange service.
        
        Args:
            exchanges: List of exchange IDs to use (defaults to all supported)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Use provided exchanges or default to supported
        self.exchanges = exchanges or self.SUPPORTED_EXCHANGES
        
        for exchange_id in self.exchanges:
            if exchange_id not in self.SUPPORTED_EXCHANGES:
                logger.warning(f"Exchange '{exchange_id}' not in supported list, skipping")
            else:
                logger.info(f"Initialized {exchange_id}")
    
    def fetch_ticker(self, exchange_id: str, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch ticker data from a specific exchange using direct API.
        
        Args:
            exchange_id: Exchange identifier (e.g., "binance")
            symbol: Trading pair (e.g., "BTC/USDT")
        
        Returns:
            Dict with ticker data or None on error
        """
        # Check cache first
        cache_key = f"{exchange_id}:{symbol}"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.CACHE_TTL:
                return cached_data
        
        if exchange_id not in EXCHANGE_APIS:
            logger.warning(f"Exchange '{exchange_id}' not supported")
            return None
        
        try:
            api_config = EXCHANGE_APIS[exchange_id]
            base, quote = symbol.split('/')
            
            # Build URL with formatted symbols
            symbol_upper = f"{base}{quote}"
            symbol_lower = f"{base.lower()}{quote.lower()}"
            symbol_kraken = f"{base}USD" if quote == "USDT" else f"{base}{quote}"
            symbol_cb = f"{base.lower()}-{quote.lower()}"
            symbol_okx = f"{base}-{quote}"
            symbol_gate = f"{base}_{quote}"
            
            endpoint = api_config["endpoint"].format(
                symbol=symbol,
                symbol_upper=symbol_upper,
                symbol_lower=symbol_lower,
                symbol_kraken=symbol_kraken,
                symbol_cb=symbol_cb,
                symbol_okx=symbol_okx,
                symbol_gate=symbol_gate
            )
            
            url = api_config["base"] + endpoint
            
            logger.debug(f"Fetching {symbol} from {exchange_id}")
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Error fetching {symbol} from {exchange_id}: HTTP {response.status_code}")
                return None
            
            data = response.json()
            
            # Parse response based on exchange format
            result = self._parse_response(exchange_id, symbol, data)
            
            if result:
                # Cache result
                self.cache[cache_key] = (result, time.time())
                logger.debug(f"{exchange_id}: Got price ask={result['ask']:.8f}")
            
            return result
        
        except requests.Timeout:
            logger.error(f"Timeout fetching {symbol} from {exchange_id}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {symbol} from {exchange_id}: {type(e).__name__}: {str(e)[:200]}")
            return None
    
    def _parse_response(self, exchange: str, symbol: str, data: Any) -> Optional[Dict[str, Any]]:
        """
        Parse exchange-specific API response.
        
        Args:
            exchange: Exchange ID
            symbol: Original symbol (BTC/USDT)
            data: API response data
            
        Returns:
            Standardized ticker dict or None
        """
        try:
            if exchange == "binance":
                return {
                    "exchange": exchange,
                    "symbol": symbol,
                    "bid": float(data.get("bidPrice", 0)),
                    "ask": float(data.get("askPrice", 0)),
                    "last": float(data.get("lastPrice", 0)),
                    "volume_24h_usd": float(data.get("quoteAssetVolume", 0)),
                    "timestamp": int(data.get("time", time.time() * 1000))
                }
            elif exchange == "kraken":
                # Kraken returns data in a different format
                ticker_keys = list(data.get("result", {}).keys())
                if not ticker_keys:
                    return None
                ticker = data["result"][ticker_keys[0]]
                return {
                    "exchange": exchange,
                    "symbol": symbol,
                    "bid": float(ticker[0][0]) if ticker[0] else 0,
                    "ask": float(ticker[1][0]) if ticker[1] else 0,
                    "last": float(ticker[7][0]) if len(ticker) > 7 and ticker[7] else 0,
                    "volume_24h_usd": 0,
                    "timestamp": int(time.time() * 1000)
                }
            elif exchange == "coinbase":
                # Coinbase price endpoint returns simple format
                if "data" in data:
                    price = float(data["data"].get("amount", 0))
                    return {
                        "exchange": exchange,
                        "symbol": symbol,
                        "bid": price * 0.9999,
                        "ask": price * 1.0001,
                        "last": price,
                        "volume_24h_usd": 0,
                        "timestamp": int(time.time() * 1000)
                    }
            elif exchange == "okx":
                if "data" in data and len(data["data"]) > 0:
                    ticker = data["data"][0]
                    return {
                        "exchange": exchange,
                        "symbol": symbol,
                        "bid": float(ticker.get("bidPx", 0)),
                        "ask": float(ticker.get("askPx", 0)),
                        "last": float(ticker.get("last", 0)),
                        "volume_24h_usd": float(ticker.get("vol24h", 0)),
                        "timestamp": int(ticker.get("ts", time.time() * 1000))
                    }
            elif exchange == "bybit":
                if "result" in data and "list" in data["result"] and len(data["result"]["list"]) > 0:
                    ticker = data["result"]["list"][0]
                    return {
                        "exchange": exchange,
                        "symbol": symbol,
                        "bid": float(ticker.get("bid1Price", 0)),
                        "ask": float(ticker.get("ask1Price", 0)),
                        "last": float(ticker.get("lastPrice", 0)),
                        "volume_24h_usd": float(ticker.get("turnover24h", 0)),
                        "timestamp": int(ticker.get("time", time.time() * 1000))
                    }
            elif exchange == "kucoin":
                if "data" in data:
                    ticker = data["data"]
                    return {
                        "exchange": exchange,
                        "symbol": symbol,
                        "bid": float(ticker.get("buy", 0)),
                        "ask": float(ticker.get("sell", 0)),
                        "last": float(ticker.get("last", 0)),
                        "volume_24h_usd": float(ticker.get("volValue", 0)),
                        "timestamp": int(ticker.get("time", time.time() * 1000))
                    }
            elif exchange == "gateio":
                if isinstance(data, list) and len(data) > 0:
                    ticker = data[0]
                    return {
                        "exchange": exchange,
                        "symbol": symbol,
                        "bid": float(ticker.get("highest_bid", 0)),
                        "ask": float(ticker.get("lowest_ask", 0)),
                        "last": float(ticker.get("last", 0)),
                        "volume_24h_usd": float(ticker.get("quote_volume", 0)),
                        "timestamp": int(time.time() * 1000)
                    }
            elif exchange == "mexc":
                if "data" in data and len(data["data"]) > 0:
                    ticker = data["data"][0]
                    return {
                        "exchange": exchange,
                        "symbol": symbol,
                        "bid": float(ticker.get("b", 0)),
                        "ask": float(ticker.get("a", 0)),
                        "last": float(ticker.get("p", 0)),
                        "volume_24h_usd": float(ticker.get("q", 0)),
                        "timestamp": int(ticker.get("t", time.time() * 1000))
                    }
            elif exchange == "htx":
                if "tick" in data:
                    ticker = data["tick"]
                    return {
                        "exchange": exchange,
                        "symbol": symbol,
                        "bid": float(ticker.get("bid", [0])[0]) if ticker.get("bid") else 0,
                        "ask": float(ticker.get("ask", [0])[0]) if ticker.get("ask") else 0,
                        "last": float(ticker.get("close", 0)),
                        "volume_24h_usd": float(ticker.get("vol", 0)),
                        "timestamp": int(ticker.get("time", time.time() * 1000))
                    }
            elif exchange == "bitget":
                if "data" in data and len(data["data"]) > 0:
                    ticker = data["data"][0]
                    return {
                        "exchange": exchange,
                        "symbol": symbol,
                        "bid": float(ticker.get("bidPx", 0)),
                        "ask": float(ticker.get("askPx", 0)),
                        "last": float(ticker.get("lastPr", 0)),
                        "volume_24h_usd": float(ticker.get("quoteVolume", 0)),
                        "timestamp": int(time.time() * 1000)
                    }
            
            return None
        except Exception as e:
            logger.debug(f"Error parsing {exchange} response: {e}")
            return None
    
    def fetch_all_tickers(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Fetch ticker from all configured exchanges.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
        
        Returns:
            List of ticker dicts sorted by ask price (ascending)
        """
        tickers = []
        
        # Fetch from each exchange
        for exchange_id in self.exchanges:
            result = self.fetch_ticker(exchange_id, symbol)
            if isinstance(result, dict) and result is not None:
                # Filter out zero prices (parsing errors)
                if result.get("ask", 0) > 0 and result.get("bid", 0) > 0:
                    tickers.append(result)
                    logger.debug(f"{exchange_id}: Success")
                else:
                    logger.debug(f"{exchange_id}: Zero price returned")
            else:
                logger.debug(f"{exchange_id}: No data returned")
        
        logger.info(f"fetch_all_tickers({symbol}): Got {len(tickers)} valid tickers out of {len(self.exchanges)} exchanges")
        
        # Sort by ask price ascending
        tickers.sort(key=lambda x: x.get("ask", float("inf")))
        
        return tickers
    
    def get_best_spread(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Find the best buying and selling opportunities across exchanges.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
        
        Returns:
            Dict with best spread info or None
        """
        tickers = self.fetch_all_tickers(symbol)
        
        if len(tickers) < 2:
            logger.warning(f"Not enough ticker data for {symbol} to calculate spread")
            return None
        
        # First ticker has lowest ask (best buy)
        best_buy = tickers[0]
        # Last ticker has highest bid (best sell)
        best_sell = tickers[-1]
        
        best_ask = best_buy.get("ask", 0)
        best_bid = best_sell.get("bid", 0)
        
        if best_ask <= 0:
            return None
        
        spread_pct = ((best_bid - best_ask) / best_ask) * 100
        
        return {
            "buy_exchange": best_buy.get("exchange"),
            "buy_price": best_ask,
            "sell_exchange": best_sell.get("exchange"),
            "sell_price": best_bid,
            "spread_pct": round(spread_pct, 3),
            "tickers": tickers
        }
    
    def fetch_all_tickers_sync(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Fetch ticker from all exchanges (already synchronous).
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
        
        Returns:
            List of ticker dicts sorted by ask price
        """
        return self.fetch_all_tickers(symbol)
    
    def get_best_spread_sync(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get best spread (already synchronous).
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
        
        Returns:
            Dict with best spread info or None
        """
        return self.get_best_spread(symbol)
    
    def close(self):
        """Close the session."""
        self.session.close()
        logger.info("All exchanges closed")
    
    def close_sync(self):
        """Synchronous close (already synchronous)."""
        self.close()
    
    def __del__(self):
        """Cleanup on object deletion."""
        try:
            self.close()
        except:
            pass
