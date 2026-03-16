"""
Funding rates service — fetches perpetual futures funding rates.
Resilient: multiple endpoints per exchange, auto-retry, smart fallback.
"""
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import logging
from typing import Dict, List, Optional, Tuple
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class FundingService:
    """Service for fetching perpetual futures funding rates from multiple exchanges."""

    SYMBOLS = [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
        "ADA/USDT", "AVAX/USDT", "LINK/USDT", "ARB/USDT", "OP/USDT",
        "PEPE/USDT", "WLD/USDT",
    ]

    EXCHANGES = ("binance", "bybit", "okx", "bitget")

    EXCHANGE_MIRRORS = {
        "binance": [
            "https://fapi.binance.com",
            "https://fapi1.binance.com",
            "https://fapi2.binance.com",
            "https://fapi3.binance.com",
            "https://fapi4.binance.com",
        ],
        "bybit": [
            "https://api.bybit.com",
            "https://api.bytick.com",
        ],
        "okx": [
            "https://www.okx.com",
            "https://aws.okx.com",            # AWS mirror
        ],
        "bitget": [
            "https://api.bitget.com",
        ],
    }

    TIMEOUT: Tuple[int, int] = (8, 20)

    def __init__(self):
        self._session = self._create_session()

        self._cache_data: List[Dict] = []
        self._cache_timestamp: float = 0
        self._cache_timeout: int = 30
        self._lock = Lock()

        self._working_mirrors: Dict[str, str] = {}

        self._to_exchange: Dict[str, Dict[str, str]] = {}
        self._from_exchange: Dict[str, Dict[str, str]] = {}

        for ex in self.EXCHANGES:
            fwd, rev = {}, {}
            for sym in self.SYMBOLS:
                base, quote = sym.split("/")
                if ex == "okx":
                    ex_sym = f"{base}-{quote}-SWAP"
                else:
                    ex_sym = f"{base}{quote}"
                fwd[sym] = ex_sym
                rev[ex_sym] = sym
            self._to_exchange[ex] = fwd
            self._from_exchange[ex] = rev

    @staticmethod
    def _create_session() -> requests.Session:
        """Create a resilient requests session with retry + connection pooling."""
        session = requests.Session()

        # Retry: 2 attempts with 0.5s → 1s backoff on connection errors
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20,
        )

        session.mount("https://", adapter)
        session.mount("http://", adapter)

        session.headers.update({
            "Accept": "application/json",
            "User-Agent": "CryptoRadar/1.0",
        })

        # Proxy support via environment variable
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if proxy:
            session.proxies = {"https": proxy, "http": proxy}
            logger.info(f"Using proxy: {proxy}")

        return session

    def close(self):
        """Close HTTP session."""
        self._session.close()

    # ------------------------------------------------------------------
    # HTTP helper — try all mirrors
    # ------------------------------------------------------------------

    def _get(self, exchange: str, path: str, params: dict = None) -> requests.Response:
        """
        Make GET request to exchange API, trying all mirror endpoints.
        Remembers which mirror worked last time → tries it first next time.
        """
        mirrors = list(self.EXCHANGE_MIRRORS.get(exchange, []))
        if not mirrors:
            raise ConnectionError(f"No endpoints configured for {exchange}")

        # Put last working mirror first
        last_good = self._working_mirrors.get(exchange)
        if last_good and last_good in mirrors:
            mirrors.remove(last_good)
            mirrors.insert(0, last_good)

        last_error = None

        for i, base_url in enumerate(mirrors):
            url = f"{base_url}{path}"
            try:
                response = self._session.get(
                    url,
                    params=params,
                    timeout=self.TIMEOUT,
                )
                response.raise_for_status()

                self._working_mirrors[exchange] = base_url

                if i > 0:
                    logger.info(
                        f"{exchange}: switched to mirror #{i + 1} "
                        f"({self._short_host(base_url)})"
                    )

                return response

            except Exception as e:
                last_error = e
                host = self._short_host(base_url)
                logger.debug(f"{exchange} mirror {host} failed: {e}")

        # Все зеркала упали
        self._working_mirrors.pop(exchange, None)
        raise ConnectionError(
            f"All {len(mirrors)} mirrors failed for {exchange}: {last_error}"
        )

    @staticmethod
    def _short_host(url: str) -> str:
        """Extract hostname for logging."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).hostname or url
        except Exception:
            return url

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_all_funding_rates(self) -> List[Dict]:
        """Fetch funding rates for all symbols from all exchanges."""
        now = time.time()

        with self._lock:
            if self._cache_data and (now - self._cache_timestamp) < self._cache_timeout:
                return list(self._cache_data)

        logger.info("Fetching fresh funding rates from all exchanges...")

        exchange_results: Dict[str, Dict[str, Dict]] = {}

        fetch_methods = {
            "binance": self._fetch_binance,
            "bybit":   self._fetch_bybit,
            "okx":     self._fetch_okx,
            "bitget":  self._fetch_bitget,
        }

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(fn): eid
                for eid, fn in fetch_methods.items()
            }
            for future in as_completed(futures):
                eid = futures[future]
                try:
                    exchange_results[eid] = future.result()
                    count = len(exchange_results[eid])
                    logger.info(f"{eid}: got {count} funding rates")
                except Exception as e:
                    logger.error(f"{eid} fetch failed completely: {e}")
                    exchange_results[eid] = {}

        result = self._merge_results(exchange_results)

        total_rates = sum(len(er) for er in exchange_results.values())
        if total_rates > 0:
            with self._lock:
                self._cache_data = result
                self._cache_timestamp = now
            logger.info(
                f"Cached {len(result)} symbols with {total_rates} total rate entries "
                f"from {sum(1 for v in exchange_results.values() if v)}/{len(fetch_methods)} exchanges"
            )
        else:
            logger.warning("No data from any exchange, returning stale cache if available")
            with self._lock:
                if self._cache_data:
                    return list(self._cache_data)

        return result

    def get_funding_arbitrage(self) -> List[Dict]:
        """Find funding arbitrage opportunities (rate diff > 0.02%)."""
        all_data = self.fetch_all_funding_rates()
        opportunities = []

        for sym_data in all_data:
            rates = sym_data.get("rates", {})
            if len(rates) < 2:
                continue

            rate_items = [(ex, rd["rate"]) for ex, rd in rates.items()]
            min_item = min(rate_items, key=lambda x: x[1])
            max_item = max(rate_items, key=lambda x: x[1])
            diff = max_item[1] - min_item[1]

            if abs(diff) > 0.0002:
                annualized = diff * 3 * 365 * 100
                opportunities.append({
                    "symbol": sym_data["symbol"],
                    "long_exchange": min_item[0],
                    "short_exchange": max_item[0],
                    "diff_pct": diff * 100,
                    "annualized_profit_pct": annualized,
                })

        opportunities.sort(key=lambda x: abs(x["annualized_profit_pct"]), reverse=True)
        return opportunities

    def get_anomalies(self) -> List[Dict]:
        """Get symbols with anomalous funding rates (> 0.05%)."""
        all_data = self.fetch_all_funding_rates()
        anomalies = [d for d in all_data if d.get("is_anomaly", False)]
        anomalies.sort(key=lambda x: x.get("max_rate", 0), reverse=True)
        return anomalies

    def get_symbol_rates(self, symbol: str) -> Optional[Dict]:
        """Get funding rates for a specific symbol."""
        for sym_data in self.fetch_all_funding_rates():
            if sym_data["symbol"] == symbol:
                return sym_data
        return None

    # ------------------------------------------------------------------
    # Exchange fetchers — batch API calls
    # ------------------------------------------------------------------

    def _fetch_binance(self) -> Dict[str, Dict]:
        """Binance: /fapi/v1/premiumIndex — all perpetual contracts in 1 call."""
        result = {}
        try:
            resp = self._get("binance", "/fapi/v1/premiumIndex")
            lookup = self._from_exchange["binance"]

            for item in resp.json():
                ex_sym = item.get("symbol", "")
                std_sym = lookup.get(ex_sym)
                if not std_sym:
                    continue

                rate = float(item.get("lastFundingRate", 0))
                next_time = int(item.get("nextFundingTime", 0))

                result[std_sym] = self._make_rate_entry(rate, next_time)

        except Exception as e:
            logger.warning(f"Binance funding fetch failed: {e}")

        return result

    def _fetch_bybit(self) -> Dict[str, Dict]:
        """Bybit: /v5/market/tickers — all linear tickers in 1 call."""
        result = {}
        try:
            resp = self._get("bybit", "/v5/market/tickers", params={"category": "linear"})
            data = resp.json()

            if data.get("retCode") != 0:
                logger.warning(f"Bybit API error: {data.get('retMsg')}")
                return result

            lookup = self._from_exchange["bybit"]

            for item in data.get("result", {}).get("list", []):
                ex_sym = item.get("symbol", "")
                std_sym = lookup.get(ex_sym)
                if not std_sym:
                    continue

                rate = float(item.get("fundingRate", 0))
                next_time = int(item.get("nextFundingTime", 0) or 0)
                oi_val = float(item.get("openInterestValue", 0) or 0)

                result[std_sym] = self._make_rate_entry(rate, next_time, oi_val)

        except Exception as e:
            logger.warning(f"Bybit funding fetch failed: {e}")

        return result

    def _fetch_okx(self) -> Dict[str, Dict]:
        """OKX: funding rates per-symbol + batch OI."""
        result = {}

        for symbol in self.SYMBOLS:
            try:
                inst_id = self._to_exchange["okx"][symbol]
                resp = self._get(
                    "okx",
                    "/api/v5/public/funding-rate",
                    params={"instId": inst_id},
                )
                data = resp.json()

                if data.get("code") != "0":
                    continue

                items = data.get("data", [])
                if not items:
                    continue

                item = items[0]
                rate = float(item.get("fundingRate", 0))
                next_time = int(item.get("nextFundingTime", 0) or 0)

                result[symbol] = self._make_rate_entry(rate, next_time)
                time.sleep(0.05)

            except Exception as e:
                logger.debug(f"OKX {symbol} funding failed: {e}")

        # Batch OI
        try:
            resp = self._get(
                "okx",
                "/api/v5/public/open-interest",
                params={"instType": "SWAP"},
            )
            data = resp.json()

            if data.get("code") == "0":
                lookup = self._from_exchange["okx"]
                for item in data.get("data", []):
                    inst_id = item.get("instId", "")
                    std_sym = lookup.get(inst_id)
                    if std_sym and std_sym in result:
                        result[std_sym]["open_interest"] = float(item.get("oiCcy", 0) or 0)
        except Exception as e:
            logger.debug(f"OKX batch OI failed: {e}")

        return result

    def _fetch_bitget(self) -> Dict[str, Dict]:
        """Bitget V2: /api/v2/mix/market/tickers — all USDT futures in 1 call."""
        result = {}
        try:
            resp = self._get(
                "bitget",
                "/api/v2/mix/market/tickers",
                params={"productType": "USDT-FUTURES"},
            )
            data = resp.json()

            if data.get("code") != "00000":
                logger.warning(f"Bitget API error: {data.get('msg')}")
                return result

            lookup = self._from_exchange["bitget"]

            for item in data.get("data", []):
                ex_sym = item.get("symbol", "")
                std_sym = lookup.get(ex_sym)
                if not std_sym:
                    continue

                rate = float(item.get("fundingRate", 0) or 0)
                next_time = int(item.get("nextFundingTime", 0) or 0)

                last_price = float(item.get("lastPr", 0) or 0)
                holding = float(item.get("holdingAmount", 0) or 0)
                oi_usd = holding * last_price

                result[std_sym] = self._make_rate_entry(rate, next_time, oi_usd)

        except Exception as e:
            logger.warning(f"Bitget funding fetch failed: {e}")

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_rate_entry(rate: float, next_funding_time: int,
                         open_interest: float = 0) -> Dict:
        return {
            "rate": rate,
            "rate_pct": f"{rate * 100:+.4f}%",
            "annualized": rate * 3 * 365 * 100,
            "next_funding_time": next_funding_time,
            "open_interest": open_interest,
        }

    def _merge_results(self, exchange_results: Dict[str, Dict[str, Dict]]) -> List[Dict]:
        """Merge per-exchange results into per-symbol rows."""
        result = []

        for symbol in self.SYMBOLS:
            sym_data = {
                "symbol": symbol,
                "rates": {},
                "max_rate": 0.0,
                "max_rate_exchange": "",
                "max_diff": 0.0,
                "is_anomaly": False,
            }

            for eid, edata in exchange_results.items():
                if symbol in edata:
                    sym_data["rates"][eid] = edata[symbol]

            rates = sym_data["rates"]
            if rates:
                rate_vals = [entry["rate"] for entry in rates.values()]
                abs_vals = [abs(v) for v in rate_vals]

                max_idx = abs_vals.index(max(abs_vals))
                sym_data["max_rate"] = abs_vals[max_idx]
                sym_data["max_rate_exchange"] = list(rates.keys())[max_idx]

                if len(rate_vals) > 1:
                    sym_data["max_diff"] = max(rate_vals) - min(rate_vals)

                sym_data["is_anomaly"] = sym_data["max_rate"] > 0.0005

            result.append(sym_data)

        return result