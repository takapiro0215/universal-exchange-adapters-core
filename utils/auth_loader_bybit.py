# utils/auth_loader_bybit.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional


def load_bybit_api_keys(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Public-core stub.

    In the public core repo we do NOT load or require secrets.
    This function returns a dict compatible with callers that expect auth info,
    but leaves keys empty and provides base_url from env/default.
    """
    return {
        "api_key": os.environ.get("BYBIT_API_KEY", ""),
        "api_secret": os.environ.get("BYBIT_API_SECRET", ""),
        "base_url": os.environ.get("BYBIT_BASE_URL", "https://api-demo.bybit.com"),
        "category": os.environ.get("BYBIT_CATEGORY", "linear"),
    }
