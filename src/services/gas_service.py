"""
Gas fee monitoring service for multiple blockchain networks
"""
import requests
import logging
from collections import deque
from typing import Dict, List, Optional
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logger = logging.getLogger(__name__)


class GasService:
    """Monitor gas fees across multiple blockchain networks."""

    NETWORKS = {
        "ethereum": {
            "name": "Ethereum",
            "symbol": "ETH",
            "icon": "Ξ",
            "rpcs": [
                "https://ethereum-rpc.publicnode.com",
                "https://1rpc.io/eth",
                "https://cloudflare-eth.com",
            ],
            "usdt_gas_cost": 65000,
            "native_transfer_gas": 21000,
            "congestion_thresholds": {"low": 15, "medium": 30},
            "decimals": 18,
        },
        "bsc": {
            "name": "BSC",
            "symbol": "BNB",
            "icon": "🟡",
            "rpcs": [
                "https://bsc-dataseed.binance.org",
                "https://bsc-rpc.publicnode.com",
                "https://bsc-dataseed1.defibit.io",
            ],
            "usdt_gas_cost": 60000,
            "native_transfer_gas": 21000,
            "congestion_thresholds": {"low": 5, "medium": 10},
            "decimals": 18,
        },
        "polygon": {
            "name": "Polygon",
            "symbol": "POL",
            "icon": "🟣",
            "rpcs": [
                "https://polygon-bor-rpc.publicnode.com",
                "https://1rpc.io/matic",
                "https://polygon.drpc.org",
            ],
            "usdt_gas_cost": 70000,
            "native_transfer_gas": 21000,
            "congestion_thresholds": {"low": 40, "medium": 100},
            "decimals": 18,
        },
        "arbitrum": {
            "name": "Arbitrum",
            "symbol": "ETH",
            "icon": "🔵",
            "rpcs": [
                "https://arb1.arbitrum.io/rpc",
                "https://arbitrum-one-rpc.publicnode.com",
                "https://1rpc.io/arb",
            ],
            "usdt_gas_cost": 50000,
            "native_transfer_gas": 21000,
            "congestion_thresholds": {"low": 0.5, "medium": 2},
            "decimals": 18,
        },
        "optimism": {
            "name": "Optimism",
            "symbol": "ETH",
            "icon": "🔴",
            "rpcs": [
                "https://optimism-rpc.publicnode.com",
                "https://1rpc.io/op",
                "https://optimism.drpc.org",
            ],
            "usdt_gas_cost": 40000,
            "native_transfer_gas": 21000,
            "congestion_thresholds": {"low": 0.2, "medium": 1},
            "decimals": 18,
        },
        "avalanche": {
            "name": "Avalanche",
            "symbol": "AVAX",
            "icon": "🔺",
            "rpcs": [
                "https://api.avax.network/ext/bc/C/rpc",
                "https://avalanche-c-chain-rpc.publicnode.com",
                "https://1rpc.io/avax/c",
            ],
            "usdt_gas_cost": 50000,
            "native_transfer_gas": 21000,
            "congestion_thresholds": {"low": 25, "medium": 75},
            "decimals": 18,
        },
        "solana": {
            "name": "Solana",
            "symbol": "SOL",
            "icon": "◎",
            "rpcs": [
                "https://api.mainnet-beta.solana.com",
                "https://solana-rpc.publicnode.com",
            ],
            "usdt_transfer_lamports": 5000,
            "native_transfer_lamports": 5000,
            "congestion_thresholds": {"low": 5000, "medium": 50000},
            "decimals": 9,
        },
        "tron": {
            "name": "TRON",
            "symbol": "TRX",
            "icon": "🔘",
            "fixed_usdt_cost": 13.4,
            "fixed_native_cost": 0.1,
            "congestion_thresholds": {"low": 0, "medium": 0},
            "decimals": 6,
        },
    }

    PRICE_KEYS = {
        "ethereum": "eth",
        "bsc": "bnb",
        "polygon": "matic",
        "arbitrum": "eth",
        "optimism": "eth",
        "avalanche": "avax",
        "solana": "sol",
        "tron": "trx",
    }

    PRICE_CACHE_DURATION = 60

    DEFAULT_PRICES = {
        "eth": 2500,
        "bnb": 600,
        "matic": 0.45,
        "avax": 25,
        "sol": 170,
        "trx": 0.27,
    }

    def __init__(self):
        self._price_cache: Dict[str, float] = {**self.DEFAULT_PRICES}
        self._price_timestamp: float = 0.0

        self._history: Dict[str, deque] = {
            nid: deque(maxlen=60) for nid in self.NETWORKS
        }
        self._last_data: Dict[str, Dict] = {nid: {} for nid in self.NETWORKS}
        self._lock = Lock()

        self._working_rpc: Dict[str, str] = {}

        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def close(self):
        """Close HTTP session."""
        self._session.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_all_gas(self) -> List[Dict]:
        self._update_prices()

        results: List[Dict] = []

        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_network = {
                executor.submit(self._fetch_gas_network, nid, cfg): nid
                for nid, cfg in self.NETWORKS.items()
            }

            for future in as_completed(future_to_network):
                network_id = future_to_network[future]
                try:
                    data = future.result()
                except Exception as e:
                    logger.error(f"Unexpected error for {network_id}: {e}")
                    data = self._make_error_result(network_id, str(e))
                results.append(data)

        with self._lock:
            for data in results:
                nid = self._network_name_to_id(data.get("network", ""))
                if nid:
                    self._history[nid].append(data)
                    self._last_data[nid] = data

        return results

    def get_history(self, network_id: str) -> List[Dict]:
        with self._lock:
            return list(self._history.get(network_id, []))

    def get_cheapest_network(self) -> Dict:
        with self._lock:
            valid = [
                d for d in self._last_data.values()
                if d
                and not d.get("stale", False)
                and d.get("usdt_transfer_usd", 0) > 0
            ]
        if not valid:
            return {}
        return min(valid, key=lambda x: x.get("usdt_transfer_usd", float("inf")))

    def get_network_status(self, network_id: str) -> Optional[Dict]:
        with self._lock:
            data = self._last_data.get(network_id, {})
            return data.copy() if data else None

    def get_all_networks(self) -> List[str]:
        return list(self.NETWORKS.keys())

    # ------------------------------------------------------------------
    # Network-specific fetchers
    # ------------------------------------------------------------------

    def _fetch_gas_network(self, network_id: str, config: Dict) -> Dict:
        now = int(time.time())
        try:
            if network_id == "solana":
                return self._fetch_solana_gas(network_id, config, now)
            elif network_id == "tron":
                return self._fetch_tron_gas(config, now)
            else:
                return self._fetch_evm_gas(network_id, config, now)
        except Exception as e:
            logger.error(f"Error fetching {network_id} gas: {e}")
            with self._lock:
                last = self._last_data.get(network_id, {})
                if last:
                    stale = last.copy()
                    stale["stale"] = True
                    stale["error"] = str(e)
                    return stale
            return self._make_error_result(network_id, str(e))

    def _fetch_evm_gas(self, network_id: str, config: Dict, now: int) -> Dict:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_gasPrice",
            "params": [],
            "id": 1,
        }

        rpcs = config.get("rpcs", [])
        gas_price_wei = self._rpc_call_multi(rpcs, payload, network_id)
        gas_price_gwei = gas_price_wei / 1e9

        price_key = self.PRICE_KEYS.get(network_id, "eth")
        with self._lock:
            native_price = self._price_cache.get(
                price_key, self.DEFAULT_PRICES.get(price_key, 1000)
            )

        usdt_gas = config["usdt_gas_cost"]
        native_gas = config["native_transfer_gas"]
        usdt_cost_usd = (gas_price_gwei * usdt_gas * native_price) / 1e9
        native_cost_usd = (gas_price_gwei * native_gas * native_price) / 1e9

        congestion = self._get_congestion_level(network_id, gas_price_gwei)
        speed = self._estimate_speed(network_id, congestion)

        return {
            "network": config["name"],
            "symbol": config["symbol"],
            "icon": config.get("icon", "?"),
            "gas_price_gwei": round(gas_price_gwei, 4),
            "gas_price_native": f"{gas_price_gwei:.2f} gwei",
            "usdt_transfer_usd": round(usdt_cost_usd, 6),
            "native_transfer_usd": round(native_cost_usd, 6),
            "speed": speed,
            "congestion": congestion,
            "timestamp": now,
            "stale": False,
        }

    def _fetch_solana_gas(self, network_id: str, config: Dict, now: int) -> Dict:
        payload = {
            "jsonrpc": "2.0",
            "method": "getRecentPrioritizationFees",
            "params": [],
            "id": 1,
        }

        total_fee_lamports = 5000
        rpcs = config.get("rpcs", [])

        for url in rpcs:
            try:
                response = self._session.post(url, json=payload, timeout=5)
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    logger.warning(f"Solana RPC {url} returned error: {result['error']}")
                    continue

                if "result" in result and result["result"]:
                    fees = [
                        item["prioritizationFee"]
                        for item in result["result"]
                        if item.get("prioritizationFee", 0) > 0
                    ]
                    if fees:
                        fees.sort()
                        median_fee = fees[len(fees) // 2]
                        total_fee_lamports = 5000 + median_fee

                # RPC worked — remember it
                self._working_rpc[network_id] = url
                break

            except Exception as e:
                logger.warning(f"Solana RPC {url} failed: {e}")
                continue

        with self._lock:
            sol_price = self._price_cache.get("sol", self.DEFAULT_PRICES["sol"])

        sol_amount = total_fee_lamports / 1e9
        cost_usd = sol_amount * sol_price

        thresholds = config["congestion_thresholds"]
        if total_fee_lamports < thresholds["low"]:
            congestion = "low"
        elif total_fee_lamports < thresholds["medium"]:
            congestion = "medium"
        else:
            congestion = "high"

        return {
            "network": config["name"],
            "symbol": config["symbol"],
            "icon": config.get("icon", "?"),
            "gas_price_gwei": round(total_fee_lamports / 1000, 2),
            "gas_price_native": f"{total_fee_lamports:,} lamports",
            "usdt_transfer_usd": round(cost_usd, 6),
            "native_transfer_usd": round(cost_usd, 6),
            "speed": "~0.4 sec",
            "congestion": congestion,
            "timestamp": now,
            "stale": False,
        }

    def _fetch_tron_gas(self, config: Dict, now: int) -> Dict:
        with self._lock:
            trx_price = self._price_cache.get("trx", self.DEFAULT_PRICES["trx"])

        usdt_cost = config["fixed_usdt_cost"] * trx_price
        native_cost = config["fixed_native_cost"] * trx_price

        return {
            "network": config["name"],
            "symbol": config["symbol"],
            "icon": config.get("icon", "?"),
            "gas_price_gwei": 0,
            "gas_price_native": f"~{config['fixed_usdt_cost']} TRX",
            "usdt_transfer_usd": round(usdt_cost, 6),
            "native_transfer_usd": round(native_cost, 6),
            "speed": "~3 sec",
            "congestion": "low",
            "timestamp": now,
            "stale": False,
        }

    # ------------------------------------------------------------------
    # RPC call with multi-endpoint fallback
    # ------------------------------------------------------------------

    def _rpc_call_multi(self, rpcs: List[str], payload: Dict, network_id: str) -> int:
        """
        Try multiple RPC endpoints in smart order.
        
        Strategy:
        1. Try last known working RPC first (cached)
        2. Then try remaining RPCs in order
        3. Remember which one worked for next time
        """
        if not rpcs:
            raise ConnectionError(f"No RPC endpoints configured for {network_id}")

        last_working = self._working_rpc.get(network_id)
        ordered_rpcs = list(rpcs)  # copy

        if last_working and last_working in ordered_rpcs:
            ordered_rpcs.remove(last_working)
            ordered_rpcs.insert(0, last_working)

        last_error = None

        for i, url in enumerate(ordered_rpcs):
            try:
                response = self._session.post(url, json=payload, timeout=5)
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    raise ValueError(f"RPC error: {result['error']}")

                if "result" not in result:
                    raise ValueError(f"No 'result' in response: {result}")

                self._working_rpc[network_id] = url

                if i > 0:
                    logger.info(
                        f"{network_id}: switched to working RPC #{i + 1}: "
                        f"{self._shorten_url(url)}"
                    )

                return int(result["result"], 16)

            except Exception as e:
                last_error = e
                logger.warning(
                    f"RPC #{i + 1} for {network_id} failed "
                    f"({self._shorten_url(url)}): {e}"
                )

        self._working_rpc.pop(network_id, None)

        raise ConnectionError(
            f"All {len(ordered_rpcs)} RPCs failed for {network_id}: {last_error}"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _shorten_url(url: str) -> str:
        """Shorten URL for logging: https://long.domain.com/path → long.domain.com"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).hostname or url
        except Exception:
            return url

    def _get_congestion_level(self, network_id: str, gas_price: float) -> str:
        config = self.NETWORKS.get(network_id)
        if not config:
            return "unknown"
        thresholds = config["congestion_thresholds"]
        low = thresholds.get("low", float("inf"))
        medium = thresholds.get("medium", float("inf"))
        if gas_price < low:
            return "low"
        elif gas_price < medium:
            return "medium"
        return "high"

    def _estimate_speed(self, network_id: str, congestion: str) -> str:
        estimates = {
            "ethereum":  ("~12 sec", "~24 sec",  "~45 sec"),
            "bsc":       ("~3 sec",  "~6 sec",   "~12 sec"),
            "polygon":   ("~2 sec",  "~4 sec",   "~8 sec"),
            "arbitrum":  ("~0.3 sec","~0.5 sec",  "~1 sec"),
            "optimism":  ("~2 sec",  "~4 sec",   "~8 sec"),
            "avalanche": ("~1 sec",  "~2 sec",   "~4 sec"),
            "solana":    ("~0.4 sec","~0.5 sec",  "~1 sec"),
            "tron":      ("~3 sec",  "~5 sec",   "~10 sec"),
        }
        speeds = estimates.get(network_id, ("~12 sec", "~24 sec", "~45 sec"))
        idx = {"low": 0, "medium": 1, "high": 2}.get(congestion, 2)
        return speeds[idx]

    def _update_prices(self):
        now = time.time()
        with self._lock:
            if now - self._price_timestamp < self.PRICE_CACHE_DURATION:
                return

        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "ethereum,binancecoin,matic-network,avalanche-2,solana,tron",
                "vs_currencies": "usd",
            }
            response = self._session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            with self._lock:
                self._price_cache["eth"] = data.get("ethereum", {}).get("usd", self.DEFAULT_PRICES["eth"])
                self._price_cache["bnb"] = data.get("binancecoin", {}).get("usd", self.DEFAULT_PRICES["bnb"])
                self._price_cache["matic"] = data.get("matic-network", {}).get("usd", self.DEFAULT_PRICES["matic"])
                self._price_cache["avax"] = data.get("avalanche-2", {}).get("usd", self.DEFAULT_PRICES["avax"])
                self._price_cache["sol"] = data.get("solana", {}).get("usd", self.DEFAULT_PRICES["sol"])
                self._price_cache["trx"] = data.get("tron", {}).get("usd", self.DEFAULT_PRICES["trx"])
                self._price_timestamp = now

            logger.debug(
                f"Prices: ETH=${self._price_cache['eth']}, "
                f"SOL=${self._price_cache['sol']}, "
                f"BNB=${self._price_cache['bnb']}"
            )

        except Exception as e:
            logger.warning(f"Failed to fetch prices: {e}")
            with self._lock:
                if self._price_timestamp == 0:
                    self._price_cache.update(self.DEFAULT_PRICES)
                self._price_timestamp = now - self.PRICE_CACHE_DURATION + 15

    def _make_error_result(self, network_id: str, error: str) -> Dict:
        config = self.NETWORKS.get(network_id, {})
        return {
            "network": config.get("name", network_id.title()),
            "symbol": config.get("symbol", "?"),
            "icon": config.get("icon", "?"),
            "gas_price_gwei": 0,
            "gas_price_native": "Error",
            "usdt_transfer_usd": 0,
            "native_transfer_usd": 0,
            "speed": "—",
            "congestion": "unknown",
            "timestamp": int(time.time()),
            "stale": True,
            "error": error,
        }

    def _network_name_to_id(self, name: str) -> Optional[str]:
        for nid, cfg in self.NETWORKS.items():
            if cfg["name"] == name:
                return nid
        return None