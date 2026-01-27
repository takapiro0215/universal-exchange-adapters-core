"""
MEXC Trading Adapter (skeleton)

- Demonstrates how adapters/base.py is used
- No real API calls yet
- Type signatures must match TradingAdapter exactly
"""

from __future__ import annotations
import os
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from dataclasses import dataclass
from typing import Optional, List, Tuple
from typing import Optional, List, Tuple, Dict, Any
from urllib.parse import urlencode

from adapters.base import (
    TradingAdapter,
    Balance,
    MarketInfo,
    Capabilities,
    OrderRequest,
    OrderStatus,
)

@dataclass
class MexcTradingConfig:
    dry_run: bool = True


class MexcTradingAdapter(TradingAdapter):
    """
    Skeleton implementation.

    This class is intentionally read-only and non-executable for now.
    Order methods exist but raise NotImplementedError until real integration begins.
    """

    def get_best_bid_ask(self, symbol: str) -> tuple[float, float]:
        params = {"symbol": symbol}
        qs = urlencode(params)

        timeout = float(os.environ.get("MEXC_HTTP_TIMEOUT", "10"))
        data = self._get_json(f"/api/v3/ticker/bookTicker?{qs}", timeout=timeout)

        bid = data.get("bidPrice")
        ask = data.get("askPrice")
        if bid is None or ask is None:
            raise RuntimeError(f"MEXC bookTicker missing fields for {symbol}: {data}")

        return float(bid), float(ask)

    def get_daily_closes(self, symbol: str, n: int = 50) -> list[float]:
        sym = symbol.upper()
        timeout = float(os.environ.get("MEXC_HTTP_TIMEOUT", "10"))

        qs = urlencode({"symbol": sym, "interval": "1d", "limit": n})
        data = self._get_json(f"/api/v3/klines?{qs}", timeout=timeout)

        # _get_json() が list を {"raw": ...} に包む仕様なので解包
        if isinstance(data, dict) and "raw" in data:
            data = data["raw"]

        if not isinstance(data, list) or not data:
            raise RuntimeError(f"no klines returned: {data!r}")

        data.sort(key=lambda x: int(x[0]))  # [0]=openTime
        return [float(e[4]) for e in data]  # [4]=close


    def __init__(self, config: Optional[MexcTradingConfig] = None):
        self.config = config or MexcTradingConfig()
        # Spot v3 base endpoint (env override 可)
        self.base_url = os.environ.get("MEXC_BASE_URL", "https://api.mexc.com").rstrip("/")
        self._exchange_info_cache: Optional[Dict[str, Any]] = None


    def _get_json(self, path: str, *, timeout: float = 10.0) -> dict:
        url = f"{self.base_url}{path}"
        req = Request(url, headers={"User-Agent": "UnivBot/1.0"})
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except HTTPError as e:
            raise RuntimeError(f"mexc http error: {e.code} {e.reason} url={url}") from e
        except URLError as e:
            raise RuntimeError(f"mexc network error: {e.reason} url={url}") from e
        except Exception as e:
            raise RuntimeError(f"mexc request failed: {e!r} url={url}") from e

        try:
            data = json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"mexc invalid json: {raw[:200]} url={url}") from e

        return data if isinstance(data, dict) else {"raw": data}

    def _get_exchange_info(self) -> Dict[str, Any]:
        # Spot v3 exchange info: symbols & filters (public)
        if isinstance(self._exchange_info_cache, dict):
            return self._exchange_info_cache

        timeout = float(os.environ.get("MEXC_HTTP_TIMEOUT", "10"))
        js = self._get_json("/api/v3/exchangeInfo", timeout=timeout)
        if not isinstance(js, dict):
            raise RuntimeError(f"mexc bad exchangeInfo type: {type(js)}")
        self._exchange_info_cache = js
        return js
    


    # ---- identity ----
    @property
    def name(self) -> str:
        return "mexc"

    def get_capabilities(self) -> Capabilities:
        # Conservative defaults for skeleton.
        # Adjust once MEXC endpoints are implemented and verified.
        return Capabilities(
            spot=True,
            futures=False,
            margin=False,
            supports_reduce_only=False,
            supports_post_only=False,
            supports_oco=False,
            supports_client_order_id=True,
            supports_withdraw=False,
            supports_withdraw_whitelist=False,
            supports_ip_allowlist=False,
            has_testnet=False,
            # ✅ 追加
            supports_orders=False,
        )

    # ---- health / time ----
    def ping(self) -> None:
        # base expects None. If it doesn't raise, it's "OK".
        return None

    def get_server_time_ms(self) -> int:
        # Spot v3 time: GET /api/v3/time -> {"serverTime": 1645539742000}
        timeout = float(os.environ.get("MEXC_HTTP_TIMEOUT", "10"))
        js = self._get_json("/api/v3/time", timeout=timeout)
        st = js.get("serverTime")
        if st is None:
            raise RuntimeError(f"mexc missing serverTime: {js}")
        try:
            return int(st)
        except Exception as e:
            raise RuntimeError(f"mexc bad serverTime: {st!r}") from e

    # ---- helpers ----
    @staticmethod
    def _split_symbol(symbol: str) -> Tuple[str, str]:
        # Accept either "BTCUSDT" or already normalized "BTC/USDT"
        if "/" in symbol:
            base, quote = symbol.split("/", 1)
            return base, quote

        quotes = ["USDT", "USDC", "BTC", "ETH", "BUSD", "EUR", "USD", "JPY"]
        for q in quotes:
            if symbol.endswith(q) and len(symbol) > len(q):
                return symbol[:-len(q)], q
        return symbol, ""

    def normalize_symbol(self, symbol: str) -> str:
        base, quote = self._split_symbol(symbol)
        return f"{base}/{quote}" if quote else base

    def denormalize_symbol(self, symbol: str) -> str:
        base, quote = self._split_symbol(symbol)
        return f"{base}{quote}" if quote else base

    # ---- market metadata ----
    def get_market_info(self, symbol: str) -> MarketInfo:
        base, quote = self._split_symbol(symbol)
        exch_symbol = self.denormalize_symbol(symbol)

        # defaults (safe)
        price_tick = 0.0
        qty_step = 0.0
        min_qty = 0.0
        min_notional: Optional[float] = None

        try:
            info = self._get_exchange_info()
            syms = info.get("symbols")
            if isinstance(syms, list):
                rec = next((s for s in syms if isinstance(s, dict) and s.get("symbol") == exch_symbol), None)
            else:
                rec = None

            if isinstance(rec, dict):
                # MEXC exchangeInfo usually contains filter list similar to Binance-style
                filters = rec.get("filters")
                if isinstance(filters, list):
                    for f in filters:
                        if not isinstance(f, dict):
                            continue
                        ftype = f.get("filterType")

                        if ftype in ("PRICE_FILTER", "PRICE"):
                            # tickSize
                            ts = f.get("tickSize") or f.get("priceTick") or f.get("minPrice")
                            if ts is not None:
                                price_tick = float(ts)

                        elif ftype in ("LOT_SIZE", "LOT"):
                            # stepSize / minQty
                            ss = f.get("stepSize") or f.get("qtyStep") or f.get("quantityStep")
                            mq = f.get("minQty") or f.get("minQuantity")
                            if ss is not None:
                                qty_step = float(ss)
                            if mq is not None:
                                min_qty = float(mq)

                        elif ftype in ("MIN_NOTIONAL", "NOTIONAL"):
                            mn = f.get("minNotional") or f.get("notional") or f.get("minQuoteAmount")
                            if mn is not None:
                                min_notional = float(mn)

                # ---- MEXC-specific fields (confirmed by exchangeInfo payload) ----
                # price tick: quotePrecision (int) -> 10^-quotePrecision
                if price_tick == 0.0:
                    qp = rec.get("quotePrecision")
                    if isinstance(qp, int) and qp >= 0:
                        price_tick = 10 ** (-qp)
                    elif isinstance(qp, str) and qp.isdigit():
                        price_tick = 10 ** (-int(qp))

                # qty step: baseSizePrecision (string decimal like "0.000001")
                if qty_step == 0.0:
                    bsp = rec.get("baseSizePrecision")
                    if bsp is not None:
                        try:
                            qty_step = float(bsp)
                        except Exception:
                            pass

                # min qty: MEXC exchangeInfo doesn't include it in this record (often elsewhere).
                # Keep 0.0 unless we find a field.
                if min_qty == 0.0:
                    for k in ("minQty", "minQuantity", "minAmount", "baseMinQty", "baseMinQuantity"):
                        v = rec.get(k)
                        if v is not None:
                            try:
                                min_qty = float(v)
                                break
                            except Exception:
                                pass

                # min_notional: not explicitly present as a standard field here.
                # quoteAmountPrecision is a precision ("1"), not a notional value, so we DON'T map it.
                if min_notional is None:
                    for k in ("minNotional", "minQuoteAmount", "minQuoteQty", "quoteMinAmount"):
                        v = rec.get(k)
                        if v is not None:
                            try:
                                min_notional = float(v)
                                break
                            except Exception:
                                pass

        except Exception:
            # keep safe defaults on any error (read-only runner should never crash)
            pass

        return MarketInfo(
            symbol=exch_symbol,
            base=base,
            quote=quote,
            price_tick=price_tick,
            qty_step=qty_step,
            min_qty=min_qty,
            min_notional=min_notional,
        )

    # ---- account state ----
    def get_balances(self) -> List[Balance]:
        # Skeleton: no API calls yet.
        return []

    # ---- orders (not implemented in skeleton) ----
    def place_order(self, req: OrderRequest) -> OrderStatus:
        raise NotImplementedError("Skeleton: place_order is not implemented yet.")

    def cancel_order(self, order_id: str, *, symbol: Optional[str] = None) -> None:
        raise NotImplementedError("Skeleton: cancel_order is not implemented yet.")

    def get_order(self, order_id: str, *, symbol: Optional[str] = None) -> OrderStatus:
        raise NotImplementedError("Skeleton: get_order is not implemented yet.")
