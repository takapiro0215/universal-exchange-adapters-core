# utils/order_bybit.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional


def place_limit_order(
    *,
    symbol: str,
    side: str,
    qty: Any,
    price: Any,
    base_url: Optional[str] = None,
    category: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Public-core stub (dry-run friendly).
    Accepts loose kwargs so tools/order_smoke_test.py can call it without
    providing base_url/category explicitly.
    """
    base_url = base_url or os.environ.get("BYBIT_BASE_URL", "https://api-demo.bybit.com")
    category = category or os.environ.get("BYBIT_CATEGORY", "linear")

    return {
        "dry_run": True,
        "base_url": base_url,
        "path": "/v5/order/create",
        "body": {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": "Limit",
            "qty": str(qty),
            "price": str(price),
            "timeInForce": kwargs.get("timeInForce", "GTC"),
            "reduceOnly": bool(kwargs.get("reduceOnly", False)),
            "orderLinkId": kwargs.get("orderLinkId", f"core-dry-{int(time.time()*1000)}"),
        },
    }


def cancel_order(
    *,
    symbol: str,
    orderLinkId: str,
    base_url: Optional[str] = None,
    category: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Public-core stub cancel.
    """
    base_url = base_url or os.environ.get("BYBIT_BASE_URL", "https://api-demo.bybit.com")
    category = category or os.environ.get("BYBIT_CATEGORY", "linear")

    return {
        "dry_run": True,
        "base_url": base_url,
        "path": "/v5/order/cancel",
        "body": {
            "category": category,
            "symbol": symbol,
            "orderLinkId": orderLinkId,
        },
    }
