# adapters/base.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Protocol, runtime_checkable, List, Literal, Tuple
from abc import ABC, abstractmethod


    
# -----------------------------
# Shared Types (Normalized)
# -----------------------------

Side = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]
TimeInForce = Literal["GTC", "IOC", "FOK"]


@dataclass(frozen=True)
class MarketInfo:
    """Normalized market metadata."""
    symbol: str                 # normalized, e.g. "BTC/USDT"
    base: str                   # e.g. "BTC"
    quote: str                  # e.g. "USDT"
    price_tick: float           # minimum price step
    qty_step: float             # minimum quantity step
    min_qty: float              # minimum order quantity
    min_notional: Optional[float] = None  # minimum order notional if exchange requires


@dataclass(frozen=True)
class Balance:
    asset: str
    free: float
    locked: float = 0.0


@dataclass(frozen=True)
class Position:
    """Optional: use for derivatives exchanges."""
    symbol: str
    side: Literal["long", "short", "flat"]
    qty: float
    entry_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None


@dataclass(frozen=True)
class OrderRequest:
    symbol: str                 # normalized, e.g. "BTC/USDT"
    side: Side
    order_type: OrderType
    qty: float
    price: Optional[float] = None           # required for limit
    time_in_force: TimeInForce = "GTC"
    reduce_only: bool = False               # derivatives
    client_order_id: Optional[str] = None   # idempotency


@dataclass(frozen=True)
class OrderStatus:
    order_id: str
    client_order_id: Optional[str]
    symbol: str
    side: Side
    order_type: OrderType
    qty: float
    filled_qty: float
    avg_price: Optional[float]
    status: Literal["new", "partially_filled", "filled", "canceled", "rejected", "expired"]
    raw: Optional[Dict[str, Any]] = None    # exchange raw payload (optional)


# -----------------------------
# Capabilities
# -----------------------------

@dataclass(frozen=True)
class Capabilities:
    """
    Describe what the exchange adapter can reliably do.
    Higher layers must not assume features beyond these flags.
    """
    spot: bool = True
    futures: bool = False
    margin: bool = False

    supports_reduce_only: bool = False
    supports_post_only: bool = False
    supports_oco: bool = False
    supports_client_order_id: bool = True
    # ✅ これを追加
    supports_orders: bool = False

    # Treasury-side
    supports_withdraw: bool = False
    supports_withdraw_whitelist: bool = False
    supports_ip_allowlist: bool = False

    # Operational
    has_testnet: bool = False


# -----------------------------
# Error Classification (Survivability)
# -----------------------------

class ErrorClass(str, Enum):
    """
    How the system should respond.
    - RETRY: transient issues (network, rate limit)
    - STOP: structural issues (auth, permissions, region restriction)
    - KILL: dangerous state (suspicious activity, withdrawal disabled unexpectedly)
    """
    RETRY = "retry"
    STOP = "stop"
    KILL = "kill"


class AdapterError(Exception):
    """Base exception for adapter-level errors."""
    def __init__(
        self,
        message: str,
        *,
        error_class: ErrorClass = ErrorClass.RETRY,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.error_class = error_class
        self.code = code
        self.details = details or {}


# -----------------------------
# Interfaces
# -----------------------------

@runtime_checkable
class TradingAdapter(Protocol):
    """
    Trading adapter: MUST NOT implement withdrawals.
    Normalized symbols and normalized return types only.
    """

    @property
    def name(self) -> str: ...

    def get_capabilities(self) -> Capabilities: ...

    

    # --- health / time ---
    def ping(self) -> None:
        """Raise AdapterError if unreachable."""
        ...

    def get_server_time_ms(self) -> int: ...

    # --- normalization helpers ---
    def normalize_symbol(self, symbol: str) -> str:
        """Convert exchange symbol -> normalized symbol (e.g. 'BTCUSDT' -> 'BTC/USDT')."""
        ...

    def denormalize_symbol(self, symbol: str) -> str:
        """Convert normalized symbol -> exchange symbol."""
        ...

    # --- market metadata ---
    def get_market_info(self, symbol: str) -> MarketInfo: ...

        # --- market data ---
    def get_best_bid_ask(self, symbol: str) -> Tuple[float, float]:
        """
        Return best bid and best ask for the given symbol (exchange symbol, e.g. "BTCUSDT").
        Returns: (best_bid, best_ask)
        """
        ...

    # --- account state ---
    def get_balances(self) -> List[Balance]: ...

    def get_positions(self) -> List[Position]:
        """Return empty list if not supported."""
        return []

    # --- orders ---
    def place_order(self, req: OrderRequest) -> OrderStatus: ...

    def cancel_order(self, order_id: str, *, symbol: Optional[str] = None) -> None: ...

    def get_order(self, order_id: str, *, symbol: Optional[str] = None) -> OrderStatus: ...

    def get_daily_closes(self, symbol: str, n: int = 50) -> List[float]:
            """Return daily close prices (ascending by time)."""
            ...

@runtime_checkable
class TreasuryAdapter(Protocol):
    """
    Treasury adapter: withdrawals only (stronger guard rails).
    Should use separate API keys from TradingAdapter.
    """

    @property
    def name(self) -> str: ...

    def get_capabilities(self) -> Capabilities: ...

    def ping(self) -> None: ...

    def get_server_time_ms(self) -> int: ...

    # --- withdrawal operations ---
    def get_withdrawal_rules(self, asset: str, *, network: Optional[str] = None) -> Dict[str, Any]:
        """
        Return normalized rules:
        - min/max
        - fee
        - available networks
        - whitelist requirement (if detectable)
        """
        ...

    def withdraw(
        self,
        asset: str,
        amount: float,
        address: str,
        *,
        network: Optional[str] = None,
        tag: Optional[str] = None,
        client_withdraw_id: Optional[str] = None,
    ) -> str:
        """Return withdraw_id (exchange-native)."""
        ...

    def get_withdraw_status(self, withdraw_id: str) -> Dict[str, Any]:
        """
        Return normalized status dict:
        - status (pending/processing/success/failed)
        - txid (if available)
        - raw payload (optional)
        """
        ...


# -----------------------------
# Helper: Error mapping guideline
# -----------------------------

def classify_exception(e: Exception) -> ErrorClass:
    """
    Default fallback classifier (adapter implementations should do better).
    Use in adapters only as a last resort.
    """
    msg = str(e).lower()

    # transient
    transient_markers = ["timeout", "timed out", "rate limit", "too many requests", "temporarily", "network"]
    if any(m in msg for m in transient_markers):
        return ErrorClass.RETRY

    # structural
    structural_markers = ["invalid api", "auth", "signature", "permission", "forbidden", "region", "restricted"]
    if any(m in msg for m in structural_markers):
        return ErrorClass.STOP

    # dangerous (very conservative)
    dangerous_markers = ["suspicious", "withdrawal disabled", "account frozen", "risk control"]
    if any(m in msg for m in dangerous_markers):
        return ErrorClass.KILL

    return ErrorClass.RETRY
