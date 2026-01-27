# adapters/bybit/trading.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from adapters.base import (
    Balance,
    Capabilities,
    MarketInfo,
    OrderRequest,
    OrderStatus,
    TradingAdapter,
)


@dataclass
class BybitTradingConfig:
    dry_run: bool = True
    base_url: str = "https://api-demo.bybit.com"
    category: str = "linear"  # "linear" | "spot" | "inverse" etc.


class BybitTradingAdapter(TradingAdapter):
    """
    Read-only + dry-run capable adapter for Bybit v5 public endpoints.
    - Market data: executable (public)
    - Orders: dry-run returns payload; live raises NotImplementedError (for now)
    """

    def __init__(self, config: Optional[BybitTradingConfig] = None):
        self.config = config or BybitTradingConfig()
        self.base_url = (
            os.environ.get("BYBIT_BASE_URL", self.config.base_url).rstrip("/")
        )
        # allow env override for category too
        self.config.category = os.environ.get("BYBIT_CATEGORY", self.config.category)
        self._instrument_cache: Dict[str, MarketInfo] = {}

    # -------------------------
    # HTTP helpers
    # -------------------------
    def _get_json(self, path: str, *, timeout: float = 10.0) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        req = Request(url, headers={"User-Agent": "UnivBot/1.0"})
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except HTTPError as e:
            raise RuntimeError(f"bybit http error: {e.code} {e.reason} url={url}") from e
        except URLError as e:
            raise RuntimeError(f"bybit network error: {e.reason} url={url}") from e
        except Exception as e:
            raise RuntimeError(f"bybit request failed: {e!r} url={url}") from e

        try:
            data = json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"bybit invalid json: {raw[:200]} url={url}") from e

        # Bybit normally returns dict
        return data if isinstance(data, dict) else {"raw": data}

    # -------------------------
    # TradingAdapter interface
    # -------------------------
    @property
    def name(self) -> str:
        return "bybit"


    def get_capabilities(self) -> Capabilities:
        # keep conservative defaults (matches earlier smoke output)
        return Capabilities(
            spot=True,
            futures=True,
            margin=False,
            supports_reduce_only=True,
            supports_post_only=True,
            supports_oco=False,
            supports_client_order_id=True,
            supports_orders=True,
            supports_withdraw=False,
            supports_withdraw_whitelist=False,
            supports_ip_allowlist=False,
            has_testnet=True,
        )

    def ping(self) -> None:
        # public endpoint
        _ = self.get_server_time_ms()

    def get_server_time_ms(self) -> int:
        timeout = float(os.environ.get("BYBIT_HTTP_TIMEOUT", "10"))
        j = self._get_json("/v5/market/time", timeout=timeout)
        # Prefer result.timeSecond if present; fallback to top-level "time"
        result = j.get("result") or {}
        t = result.get("timeSecond")
        if isinstance(t, (int, float)):
            return int(t) * 1000
        if isinstance(t, str) and t.strip().isdigit():
            return int(t.strip()) * 1000

        t2 = j.get("time")
        if isinstance(t2, (int, float)):
            return int(t2)
        if isinstance(t2, str) and t2.strip().isdigit():
            return int(t2.strip())
        return 0

    def normalize_symbol(self, symbol: str) -> str:
        # Bybit expects e.g. "BTCUSDT"
        s = str(symbol).upper().replace("/", "").replace("-", "").strip()
        return s

    def denormalize_symbol(self, symbol: str) -> str:
        # for UI/logging only (BTCUSDT -> BTC/USDT)
        s = self.normalize_symbol(symbol)
        if s.endswith("USDT") and len(s) > 4:
            return f"{s[:-4]}/USDT"
        return s

    def get_best_bid_ask(self, symbol: str) -> Tuple[float, float]:
        sym = self.normalize_symbol(symbol)
        params = {"category": self.config.category, "symbol": sym, "limit": 1}
        qs = urlencode(params)

        timeout = float(os.environ.get("BYBIT_HTTP_TIMEOUT", "10"))
        j = self._get_json(f"/v5/market/orderbook?{qs}", timeout=timeout)

        result = j.get("result") or {}
        bids = result.get("b") or []
        asks = result.get("a") or []
        if not bids or not asks:
            raise RuntimeError(f"bybit orderbook empty for {sym}: {j}")

        # bids/asks: [["price","size"], ...] (strings)
        return float(bids[0][0]), float(asks[0][0])

    def get_daily_closes(self, symbol: str, n: int = 50) -> List[float]:
        sym = self.normalize_symbol(symbol)
        params = {"category": self.config.category, "symbol": sym, "interval": "D", "limit": n}
        qs = urlencode(params)

        timeout = float(os.environ.get("BYBIT_HTTP_TIMEOUT", "10"))
        j = self._get_json(f"/v5/market/kline?{qs}", timeout=timeout)

        arr = (j.get("result") or {}).get("list") or []
        if not arr:
            raise RuntimeError(f"no kline returned for {sym}: {j}")

        # Each entry: [timestamp(ms), open, high, low, close, volume, turnover]
        arr.sort(key=lambda x: int(x[0]) if x and x[0] is not None else 0)
        return [float(e[4]) for e in arr]

    def get_market_info(self, symbol: str) -> MarketInfo:
        sym = self.normalize_symbol(symbol)

        # cache first
        if sym in self._instrument_cache:
            return self._instrument_cache[sym]

        params = {"category": self.config.category, "symbol": sym}
        qs = urlencode(params)

        timeout = float(os.environ.get("BYBIT_HTTP_TIMEOUT", "10"))
        j = self._get_json(f"/v5/market/instruments-info?{qs}", timeout=timeout)

        result = j.get("result") or {}
        items = result.get("list") or []
        if not items:
            raise RuntimeError(f"bybit instruments-info empty for {sym}: {j}")

        info = items[0]
        price_filter = info.get("priceFilter") or {}
        lot_filter = info.get("lotSizeFilter") or {}

        tick = float(price_filter.get("tickSize") or 0.0)
        step = float(lot_filter.get("qtyStep") or 0.0)
        min_qty = float(lot_filter.get("minOrderQty") or 0.0)

        base = sym[:-4] if sym.endswith("USDT") and len(sym) > 4 else sym
        quote = "USDT" if sym.endswith("USDT") else ""

        mi = MarketInfo(
            symbol=sym,
            base=base,
            quote=quote,
            price_tick=tick,
            qty_step=step,
            min_qty=min_qty,
            min_notional=None,
        )
        self._instrument_cache[sym] = mi
        return mi

    def get_balances(self) -> List[Balance]:
        # public-only adapter for now
        return []

    # -------------------------
    # Orders (dry-run only for now)
    # -------------------------
    def place_order(self, req: OrderRequest) -> OrderStatus:
        # Build a Bybit v5 create payload (safe minimal)
        body: Dict[str, Any] = {
            "category": self.config.category,
            "symbol": self.normalize_symbol(req.symbol),
            "side": req.side,
            "orderType": req.order_type,
            "qty": str(req.qty),
        }
        if req.price is not None:
            body["price"] = str(req.price)
        if req.time_in_force is not None:
            body["timeInForce"] = req.time_in_force
        if req.reduce_only is not None:
            body["reduceOnly"] = bool(req.reduce_only)
        if req.client_order_id is not None:
            body["orderLinkId"] = str(req.client_order_id)

        if self.config.dry_run:
            payload = {"dry_run": True, "path": "/v5/order/create", "body": body}
            return cast(OrderStatus, payload)

        raise NotImplementedError("live order placement not implemented yet")

    def cancel_order(self, order_id: str, *, symbol: Optional[str] = None) -> None:
        body: Dict[str, Any] = {
            "category": self.config.category,
            "symbol": self.normalize_symbol(symbol or BTC_SYMBOL_FALLBACK()),
            # prefer orderLinkId for safety if caller passes client id; else use orderId
        }
        # heuristics: if looks like our client ids (safe-buy-...), use orderLinkId
        if isinstance(order_id, str) and ("safe-" in order_id or "orderLinkId" in order_id):
            body["orderLinkId"] = order_id
        else:
            body["orderId"] = order_id

        if self.config.dry_run:
            _ = {"dry_run": True, "path": "/v5/order/cancel", "body": body}
            return None

        raise NotImplementedError("live order cancel not implemented yet")

    def get_order(self, order_id: str, *, symbol: Optional[str] = None) -> OrderStatus:
        if self.config.dry_run:
            payload = {
                "dry_run": True,
                "path": "/v5/order/realtime",
                "query": {
                    "category": self.config.category,
                    "symbol": self.normalize_symbol(symbol or BTC_SYMBOL_FALLBACK()),
                    "orderId": order_id,
                },
            }
            return cast(OrderStatus, payload)
        raise NotImplementedError("live get_order not implemented yet")


def BTC_SYMBOL_FALLBACK() -> str:
    # used only when cancel/get_order called without symbol
    return "BTCUSDT"
