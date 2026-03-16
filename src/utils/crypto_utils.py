"""
Crypto utilities - address validation, fee data, and profit calculations
"""
import re
from typing import Optional, Dict, Any

# Exchange trading and withdrawal fees
EXCHANGE_FEES = {
    "binance": {
        "maker": 0.1,
        "taker": 0.1,
        "withdraw": {
            "BTC": {"fee": 0.0005, "network": "BTC"},
            "ETH": {"fee": 0.005, "network": "ERC20"},
            "SOL": {"fee": 0.01, "network": "SOL"},
            "XRP": {"fee": 0.25, "network": "XRP"},
            "DOGE": {"fee": 1.0, "network": "DOGE"},
            "ADA": {"fee": 0.5, "network": "ADA"},
            "AVAX": {"fee": 0.01, "network": "AVAX"},
            "MATIC": {"fee": 0.1, "network": "POLYGON"},
            "DOT": {"fee": 0.1, "network": "DOT"},
            "LINK": {"fee": 0.05, "network": "ERC20"},
            "UNI": {"fee": 0.04, "network": "ERC20"},
            "ATOM": {"fee": 0.01, "network": "ATOM"},
            "ARB": {"fee": 0.1, "network": "ARBITRUM"},
            "OP": {"fee": 0.1, "network": "OPTIMISM"},
            "PEPE": {"fee": 50000000, "network": "ERC20"},
            "WLD": {"fee": 2.0, "network": "ERC20"},
            "USDT": {
                "ERC20": 3.0,
                "TRC20": 1.0,
                "BEP20": 0.3,
                "SOL": 1.0,
            },
        }
    },
    "bybit": {
        "maker": 0.1,
        "taker": 0.1,
        "withdraw": {
            "BTC": {"fee": 0.0005, "network": "BTC"},
            "ETH": {"fee": 0.006, "network": "ERC20"},
            "SOL": {"fee": 0.015, "network": "SOL"},
            "XRP": {"fee": 0.25, "network": "XRP"},
            "DOGE": {"fee": 1.0, "network": "DOGE"},
            "ADA": {"fee": 0.5, "network": "ADA"},
            "AVAX": {"fee": 0.015, "network": "AVAX"},
            "MATIC": {"fee": 0.15, "network": "POLYGON"},
            "DOT": {"fee": 0.1, "network": "DOT"},
            "LINK": {"fee": 0.06, "network": "ERC20"},
            "UNI": {"fee": 0.05, "network": "ERC20"},
            "ATOM": {"fee": 0.02, "network": "ATOM"},
            "ARB": {"fee": 0.15, "network": "ARBITRUM"},
            "OP": {"fee": 0.15, "network": "OPTIMISM"},
            "PEPE": {"fee": 100000000, "network": "ERC20"},
            "WLD": {"fee": 2.5, "network": "ERC20"},
            "USDT": {
                "ERC20": 4.0,
                "TRC20": 1.0,
                "BEP20": 0.3,
                "SOL": 1.25,
            },
        }
    },
    "okx": {
        "maker": 0.08,
        "taker": 0.1,
        "withdraw": {
            "BTC": {"fee": 0.0004, "network": "BTC"},
            "ETH": {"fee": 0.004, "network": "ERC20"},
            "SOL": {"fee": 0.008, "network": "SOL"},
            "XRP": {"fee": 0.15, "network": "XRP"},
            "DOGE": {"fee": 0.8, "network": "DOGE"},
            "ADA": {"fee": 0.4, "network": "ADA"},
            "AVAX": {"fee": 0.008, "network": "AVAX"},
            "MATIC": {"fee": 0.08, "network": "POLYGON"},
            "DOT": {"fee": 0.08, "network": "DOT"},
            "LINK": {"fee": 0.03, "network": "ERC20"},
            "UNI": {"fee": 0.03, "network": "ERC20"},
            "ATOM": {"fee": 0.008, "network": "ATOM"},
            "ARB": {"fee": 0.08, "network": "ARBITRUM"},
            "OP": {"fee": 0.08, "network": "OPTIMISM"},
            "PEPE": {"fee": 40000000, "network": "ERC20"},
            "WLD": {"fee": 1.5, "network": "ERC20"},
            "USDT": {
                "ERC20": 2.0,
                "TRC20": 0.6,
                "BEP20": 0.2,
                "SOL": 0.8,
            },
        }
    },
    "kucoin": {
        "maker": 0.1,
        "taker": 0.1,
        "withdraw": {
            "BTC": {"fee": 0.0006, "network": "BTC"},
            "ETH": {"fee": 0.008, "network": "ERC20"},
            "SOL": {"fee": 0.02, "network": "SOL"},
            "XRP": {"fee": 0.3, "network": "XRP"},
            "DOGE": {"fee": 1.2, "network": "DOGE"},
            "ADA": {"fee": 0.6, "network": "ADA"},
            "AVAX": {"fee": 0.02, "network": "AVAX"},
            "MATIC": {"fee": 0.2, "network": "POLYGON"},
            "DOT": {"fee": 0.12, "network": "DOT"},
            "LINK": {"fee": 0.08, "network": "ERC20"},
            "UNI": {"fee": 0.07, "network": "ERC20"},
            "ATOM": {"fee": 0.03, "network": "ATOM"},
            "ARB": {"fee": 0.2, "network": "ARBITRUM"},
            "OP": {"fee": 0.2, "network": "OPTIMISM"},
            "PEPE": {"fee": 150000000, "network": "ERC20"},
            "WLD": {"fee": 3.0, "network": "ERC20"},
            "USDT": {
                "ERC20": 5.0,
                "TRC20": 1.5,
                "BEP20": 0.5,
                "SOL": 1.5,
            },
        }
    },
    "kraken": {
        "maker": 0.16,
        "taker": 0.26,
        "withdraw": {
            "BTC": {"fee": 0.0008, "network": "BTC"},
            "ETH": {"fee": 0.01, "network": "ERC20"},
            "SOL": {"fee": 0.025, "network": "SOL"},
            "XRP": {"fee": 0.3, "network": "XRP"},
            "DOGE": {"fee": 1.0, "network": "DOGE"},
            "ADA": {"fee": 0.5, "network": "ADA"},
            "AVAX": {"fee": 0.025, "network": "AVAX"},
            "MATIC": {"fee": 0.25, "network": "POLYGON"},
            "DOT": {"fee": 0.15, "network": "DOT"},
            "LINK": {"fee": 0.1, "network": "ERC20"},
            "UNI": {"fee": 0.09, "network": "ERC20"},
            "ATOM": {"fee": 0.05, "network": "ATOM"},
            "ARB": {"fee": 0.25, "network": "ARBITRUM"},
            "OP": {"fee": 0.25, "network": "OPTIMISM"},
            "PEPE": {"fee": 200000000, "network": "ERC20"},
            "WLD": {"fee": 4.0, "network": "ERC20"},
            "USDT": {
                "ERC20": 6.0,
                "TRC20": 2.0,
                "BEP20": 1.0,
                "SOL": 2.0,
            },
        }
    },
    "gateio": {
        "maker": 0.15,
        "taker": 0.15,
        "withdraw": {
            "BTC": {"fee": 0.0005, "network": "BTC"},
            "ETH": {"fee": 0.005, "network": "ERC20"},
            "SOL": {"fee": 0.01, "network": "SOL"},
            "XRP": {"fee": 0.2, "network": "XRP"},
            "DOGE": {"fee": 0.9, "network": "DOGE"},
            "ADA": {"fee": 0.45, "network": "ADA"},
            "AVAX": {"fee": 0.01, "network": "AVAX"},
            "MATIC": {"fee": 0.12, "network": "POLYGON"},
            "DOT": {"fee": 0.09, "network": "DOT"},
            "LINK": {"fee": 0.04, "network": "ERC20"},
            "UNI": {"fee": 0.04, "network": "ERC20"},
            "ATOM": {"fee": 0.009, "network": "ATOM"},
            "ARB": {"fee": 0.12, "network": "ARBITRUM"},
            "OP": {"fee": 0.12, "network": "OPTIMISM"},
            "PEPE": {"fee": 60000000, "network": "ERC20"},
            "WLD": {"fee": 1.8, "network": "ERC20"},
            "USDT": {
                "ERC20": 3.5,
                "TRC20": 0.9,
                "BEP20": 0.28,
                "SOL": 0.9,
            },
        }
    },
    "mexc": {
        "maker": 0.1,
        "taker": 0.1,
        "withdraw": {
            "BTC": {"fee": 0.0005, "network": "BTC"},
            "ETH": {"fee": 0.005, "network": "ERC20"},
            "SOL": {"fee": 0.01, "network": "SOL"},
            "XRP": {"fee": 0.25, "network": "XRP"},
            "DOGE": {"fee": 1.0, "network": "DOGE"},
            "ADA": {"fee": 0.5, "network": "ADA"},
            "AVAX": {"fee": 0.01, "network": "AVAX"},
            "MATIC": {"fee": 0.1, "network": "POLYGON"},
            "DOT": {"fee": 0.1, "network": "DOT"},
            "LINK": {"fee": 0.05, "network": "ERC20"},
            "UNI": {"fee": 0.04, "network": "ERC20"},
            "ATOM": {"fee": 0.01, "network": "ATOM"},
            "ARB": {"fee": 0.1, "network": "ARBITRUM"},
            "OP": {"fee": 0.1, "network": "OPTIMISM"},
            "PEPE": {"fee": 50000000, "network": "ERC20"},
            "WLD": {"fee": 2.0, "network": "ERC20"},
            "USDT": {
                "ERC20": 3.0,
                "TRC20": 1.0,
                "BEP20": 0.3,
                "SOL": 1.0,
            },
        }
    },
    "htx": {
        "maker": 0.2,
        "taker": 0.2,
        "withdraw": {
            "BTC": {"fee": 0.0005, "network": "BTC"},
            "ETH": {"fee": 0.005, "network": "ERC20"},
            "SOL": {"fee": 0.01, "network": "SOL"},
            "XRP": {"fee": 0.25, "network": "XRP"},
            "DOGE": {"fee": 1.0, "network": "DOGE"},
            "ADA": {"fee": 0.5, "network": "ADA"},
            "AVAX": {"fee": 0.01, "network": "AVAX"},
            "MATIC": {"fee": 0.1, "network": "POLYGON"},
            "DOT": {"fee": 0.1, "network": "DOT"},
            "LINK": {"fee": 0.05, "network": "ERC20"},
            "UNI": {"fee": 0.04, "network": "ERC20"},
            "ATOM": {"fee": 0.01, "network": "ATOM"},
            "ARB": {"fee": 0.1, "network": "ARBITRUM"},
            "OP": {"fee": 0.1, "network": "OPTIMISM"},
            "PEPE": {"fee": 50000000, "network": "ERC20"},
            "WLD": {"fee": 2.0, "network": "ERC20"},
            "USDT": {
                "ERC20": 3.0,
                "TRC20": 1.0,
                "BEP20": 0.3,
                "SOL": 1.0,
            },
        }
    },
    "coinbase": {
        "maker": 0.4,
        "taker": 0.6,
        "withdraw": {
            "BTC": {"fee": 0.0, "network": "BTC"},
            "ETH": {"fee": 0.0, "network": "ERC20"},
            "SOL": {"fee": 0.0, "network": "SOL"},
            "XRP": {"fee": 0.0, "network": "XRP"},
            "DOGE": {"fee": 0.0, "network": "DOGE"},
            "ADA": {"fee": 0.0, "network": "ADA"},
            "AVAX": {"fee": 0.0, "network": "AVAX"},
            "MATIC": {"fee": 0.0, "network": "POLYGON"},
            "DOT": {"fee": 0.0, "network": "DOT"},
            "LINK": {"fee": 0.0, "network": "ERC20"},
            "UNI": {"fee": 0.0, "network": "ERC20"},
            "ATOM": {"fee": 0.0, "network": "ATOM"},
            "ARB": {"fee": 0.0, "network": "ARBITRUM"},
            "OP": {"fee": 0.0, "network": "OPTIMISM"},
            "PEPE": {"fee": 0.0, "network": "ERC20"},
            "WLD": {"fee": 0.0, "network": "ERC20"},
            "USDT": {
                "ERC20": 0.0,
                "TRC20": 0.0,
                "BEP20": 0.0,
                "SOL": 0.0,
            },
        }
    },
    "bitget": {
        "maker": 0.1,
        "taker": 0.1,
        "withdraw": {
            "BTC": {"fee": 0.0005, "network": "BTC"},
            "ETH": {"fee": 0.005, "network": "ERC20"},
            "SOL": {"fee": 0.01, "network": "SOL"},
            "XRP": {"fee": 0.25, "network": "XRP"},
            "DOGE": {"fee": 1.0, "network": "DOGE"},
            "ADA": {"fee": 0.5, "network": "ADA"},
            "AVAX": {"fee": 0.01, "network": "AVAX"},
            "MATIC": {"fee": 0.1, "network": "POLYGON"},
            "DOT": {"fee": 0.1, "network": "DOT"},
            "LINK": {"fee": 0.05, "network": "ERC20"},
            "UNI": {"fee": 0.04, "network": "ERC20"},
            "ATOM": {"fee": 0.01, "network": "ATOM"},
            "ARB": {"fee": 0.1, "network": "ARBITRUM"},
            "OP": {"fee": 0.1, "network": "OPTIMISM"},
            "PEPE": {"fee": 50000000, "network": "ERC20"},
            "WLD": {"fee": 2.0, "network": "ERC20"},
            "USDT": {
                "ERC20": 3.0,
                "TRC20": 1.0,
                "BEP20": 0.3,
                "SOL": 1.0,
            },
        }
    },
}


def validate_ethereum_address(address: str) -> bool:
    """Validate Ethereum address format."""
    return bool(re.match(r"^0x[a-fA-F0-9]{40}$", address))


def validate_bitcoin_address(address: str) -> bool:
    """Validate Bitcoin address format."""
    return bool(re.match(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$", address))


def format_address(address: str, show_chars: int = 8) -> str:
    """Format address for display (e.g., 0x1234...5678)."""
    if len(address) <= show_chars * 2:
        return address
    return f"{address[:show_chars]}...{address[-show_chars:]}"


def get_trading_fee(exchange: str, side: str = "taker") -> float:
    """
    Get trading fee percentage for an exchange.
    
    Args:
        exchange: Exchange ID (e.g., "binance")
        side: "maker" or "taker" (default "taker")
    
    Returns:
        Fee percentage (e.g., 0.1 for 0.1%)
    """
    if exchange not in EXCHANGE_FEES:
        return 0.25  # Default conservative estimate
    
    fee_key = "maker" if side.lower() == "maker" else "taker"
    return EXCHANGE_FEES[exchange].get(fee_key, 0.1)


def get_withdraw_fee(exchange: str, coin: str, network: str = None) -> float:
    """
    Get withdrawal fee for a coin from an exchange.
    
    Args:
        exchange: Exchange ID
        coin: Cryptocurrency (e.g., "BTC", "ETH")
        network: Network name (optional, uses cheapest if not specified)
    
    Returns:
        Withdrawal fee in coin units
    """
    if exchange not in EXCHANGE_FEES:
        return 0.0
    
    exchange_data = EXCHANGE_FEES[exchange].get("withdraw", {})
    coin_data = exchange_data.get(coin)
    
    if coin_data is None:
        return 0.0
    
    # Check if this is a single network coin (has "fee" key)
    if isinstance(coin_data, dict) and "fee" in coin_data:
        return coin_data.get("fee", 0.0)
    
    # Otherwise it's multi-network (like USDT)
    if isinstance(coin_data, dict):
        if network:
            return coin_data.get(network, 0.0)
        else:
            # Return cheapest network option
            fees = [v for v in coin_data.values() if isinstance(v, (int, float))]
            return min(fees) if fees else 0.0
    
    return 0.0


def get_cheapest_transfer_network(coin: str, exchange: str) -> str:
    """
    Get the cheapest network for withdrawing a coin from an exchange.
    
    Args:
        coin: Cryptocurrency
        exchange: Exchange ID
    
    Returns:
        Network name with lowest fee
    """
    if exchange not in EXCHANGE_FEES:
        return ""
    
    exchange_data = EXCHANGE_FEES[exchange].get("withdraw", {})
    coin_data = exchange_data.get(coin)
    
    if coin_data is None:
        return ""
    
    # If has "network" key, it's single network coin
    if isinstance(coin_data, dict) and "network" in coin_data:
        return coin_data["network"]
    
    # Otherwise find network with minimum fee (for multi-network like USDT)
    if isinstance(coin_data, dict):
        # Filter only numeric values (fees, not other keys)
        fee_items = [(k, v) for k, v in coin_data.items() if isinstance(v, (int, float))]
        if fee_items:
            min_network = min(fee_items, key=lambda x: x[1])
            return min_network[0]
    
    return ""


def calculate_net_profit(
    buy_exchange: str,
    sell_exchange: str,
    coin: str,
    amount_usdt: float,
    buy_price: float,
    sell_price: float
) -> Dict[str, Any]:
    """
    Calculate net profit after accounting for trading fees and withdrawal fees.
    
    Args:
        buy_exchange: Exchange to buy on
        sell_exchange: Exchange to sell on
        coin: Cryptocurrency symbol
        amount_usdt: Investment amount in USDT
        buy_price: Purchase price per coin
        sell_price: Sale price per coin
    
    Returns:
        Dict with profit breakdown:
        {
            "gross_profit": float,      # Before fees
            "buy_fee": float,           # Fee paid on purchase (USDT equivalent)
            "sell_fee": float,          # Fee paid on sale (USDT equivalent)
            "withdraw_fee": float,      # Network withdrawal fee (USDT equivalent)
            "net_profit": float,        # After all fees
            "net_profit_pct": float,    # Net profit percentage
            "is_profitable": bool       # Whether trade is profitable
        }
    """
    # Calculate coin amount purchased
    buy_trading_fee_pct = get_trading_fee(buy_exchange, "taker")
    coin_amount = amount_usdt / (buy_price * (1 + buy_trading_fee_pct / 100))
    
    # Calculate fees
    buy_fee_usdt = amount_usdt * (buy_trading_fee_pct / 100)
    
    sell_trading_fee_pct = get_trading_fee(sell_exchange, "taker")
    gross_sale_price = coin_amount * sell_price
    sell_fee_usdt = gross_sale_price * (sell_trading_fee_pct / 100)
    
    # Withdrawal fee
    withdraw_fee_coin = get_withdraw_fee(buy_exchange, coin)
    withdraw_fee_usdt = withdraw_fee_coin * sell_price
    
    # Calculate profits
    net_sale_price = gross_sale_price - sell_fee_usdt - withdraw_fee_usdt
    gross_profit = gross_sale_price - amount_usdt
    net_profit = net_sale_price - amount_usdt
    net_profit_pct = (net_profit / amount_usdt * 100) if amount_usdt > 0 else 0
    
    return {
        "gross_profit": round(gross_profit, 2),
        "buy_fee": round(buy_fee_usdt, 2),
        "sell_fee": round(sell_fee_usdt, 2),
        "withdraw_fee": round(withdraw_fee_usdt, 2),
        "net_profit": round(net_profit, 2),
        "net_profit_pct": round(net_profit_pct, 3),
        "is_profitable": net_profit > 0
    }
