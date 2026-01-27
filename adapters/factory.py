# adapters/factory.py
from __future__ import annotations

import os
from typing import Optional

from adapters.base import TradingAdapter


def get_trading_adapter(exchange: Optional[str] = None, profile: str = "paper") -> TradingAdapter:
    """
    Public-core factory (minimal).
    - No secrets required.
    - Uses env/base_url defaults.
    """
    ex = (exchange or os.environ.get("EXCHANGE", "bybit")).strip().lower()
    prof = (profile or os.environ.get("PROFILE", "paper")).strip().lower()
    dry_run = (prof != "live")

    if ex == "bybit":
        from adapters.bybit.trading import BybitTradingAdapter, BybitTradingConfig

        base_url = os.environ.get("BYBIT_BASE_URL", "https://api-demo.bybit.com").strip()
        category = os.environ.get("BYBIT_CATEGORY", "linear").strip()

        return BybitTradingAdapter(
            BybitTradingConfig(dry_run=bool(dry_run), base_url=base_url, category=category)
        )

    if ex == "mexc":
        from adapters.mexc.trading import MexcTradingAdapter, MexcTradingConfig

        base_url = os.environ.get("MEXC_BASE_URL")
        if isinstance(base_url, str) and base_url.strip():
            os.environ["MEXC_BASE_URL"] = base_url.strip()

        return MexcTradingAdapter(MexcTradingConfig())

    raise RuntimeError(f"unknown exchange: {ex}")
