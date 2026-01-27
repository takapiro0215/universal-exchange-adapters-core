# tools/risk_scan.py
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import statistics as st
from pathlib import Path
from typing import Any, Dict, Tuple, Optional
import requests
from adapters.base import TradingAdapter 

# =========================
# Paths (repo / runtime)
# =========================
# tools/ 配下に置く前提：tools/risk_scan.py -> 親の親が repo root
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LOCALAPPDATA = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
OUTDIR = Path(LOCALAPPDATA) / "UnivBot" / "bybit" / "logs"
WATCH = REPO_ROOT / "config" / "public" / "watchlist.json"

S = requests.Session()

def get_outdir(exchange: str) -> Path:
    ex = (exchange or "bybit").strip().lower()
    return Path(LOCALAPPDATA) / "UnivBot" / ex / "logs"


# =========================
# Tunables (env override)
# =========================
def _env_float(name: str, default: float) -> float:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return float(default)
    try:
        return float(v)
    except ValueError:
        return float(default)


PANIC_RET       = _env_float("RISK_PANIC_RET", 0.020)    # BTC日変動の絶対値(比率) 2.0%以上で panic
CAUTION_RET     = _env_float("RISK_CAUTION_RET", 0.012)  # 1.2%以上で caution
PANIC_BB        = _env_float("RISK_PANIC_BB", 22.0)      # BB幅(%) 22以上で panic
CAUTION_BB      = _env_float("RISK_CAUTION_BB", 16.0)    # 16以上で caution
PANIC_BREADTH   = _env_float("RISK_PANIC_BREADTH", 0.40) # OS銘柄比率 40%以上で panic
CAUTION_BREADTH = _env_float("RISK_CAUTION_BREADTH", 0.25)

SIZE_NORMAL  = _env_float("RISK_SIZE_NORMAL", 1.0)
SIZE_CAUTION = _env_float("RISK_SIZE_CAUTION", 0.5)
SIZE_PANIC   = _env_float("RISK_SIZE_PANIC", 0.0)


# =========================
# Helpers
# =========================


def btc_metrics(adapter: TradingAdapter) -> Tuple[float, float]:
    bid, ask = adapter.get_best_bid_ask("BTCUSDT")

    mid = (bid + ask) / 2.0
    if mid <= 0:
        raise RuntimeError(f"bad mid computed: bid={bid}, ask={ask}")

    bb_width_pct = (ask - bid) / mid * 100.0

    # --- daily close return (restore abs_ret) ---
        # --- daily close return (abs_ret) ---
    abs_ret = 0.0
    try:
        closes = adapter.get_daily_closes("BTCUSDT", n=2)
        if len(closes) >= 2:
            prev_close = closes[-2]
            abs_ret = abs(mid - prev_close) / prev_close * 100.0

            try:
                    closes = adapter.get_daily_closes("BTCUSDT", n=2)
            except Exception as e:
                    abs_ret = 0.0

    except Exception:
        abs_ret = 0.0 

    return abs_ret, bb_width_pct


def _safe_load_json(path: Path, encoding: str = "utf-8") -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding=encoding))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None
    except Exception:
        return None


def breadth_oversold() -> Tuple[int, int]:
    """
    watchlist の focus/whitelist を対象に、logs/signals_{SYM}.json の 1h 指標から
    rsi<30 かつ pb<0 を oversold として breadth を数える。
    """
    wl = _safe_load_json(WATCH, encoding="utf-8-sig")
    if not wl:
        return 0, 0

    cats = wl.get("categories", {}) if isinstance(wl, dict) else {}
    focus = cats.get("focus", []) if isinstance(cats, dict) else []
    whitelist = cats.get("whitelist", []) if isinstance(cats, dict) else []
    symbols = sorted(set(map(lambda s: str(s).upper(), list(focus) + list(whitelist))))

    n_os = 0
    total = 0

    for sym in symbols:
        p = OUTDIR / "order_smoke_state.json"


        d = _safe_load_json(p, encoding="utf-8")
        if not d or not isinstance(d, dict):
            continue

        tf1h = d.get("1h")
        if not isinstance(tf1h, dict):
            continue

        rsi = tf1h.get("rsi14")
        bb = tf1h.get("bb") or {}
        pb = bb.get("percent_b") if isinstance(bb, dict) else None

        if rsi is None or pb is None:
            continue

        total += 1
        try:
            if float(rsi) < 30.0 and float(pb) < 0.0:
                n_os += 1
        except Exception:
            continue

    return n_os, total




# =========================
# Smoke ingest & gate (NEW)
# =========================
def load_order_smoke_state() -> Optional[Dict[str, Any]]:
    p = OUTDIR / "order_smoke_state.json"
    d = _safe_load_json(p, encoding="utf-8")
    return d if isinstance(d, dict) else None


def classify_smoke_gate(smoke: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    # ★ここ重要：Optionalを確実に潰す
    if smoke is None:
        return {
            "action": "STOP",
            "allow_orders": False,
            "reason": "no_smoke_result",
            "retry_after_sec": 0,
        }
    
    # ---- TTL: smoke freshness gate ----
    ttl_sec = int(os.environ.get("RISK_SMOKE_TTL_SEC", "300"))  # default 5min
    now_ms = int(time.time() * 1000)
    ts = smoke.get("ts") if isinstance(smoke, dict) else 0
    ts_ms = int(ts) if isinstance(ts, (int, float, str)) and str(ts).strip() != "" else 0

    if ts_ms <= 0 or (now_ms - ts_ms) > ttl_sec * 1000:
        return {
            "action": "STOP",
            "allow_orders": False,
            "reason": f"smoke_stale(ttl={ttl_sec}s)",
            "retry_after_sec": 0,
        }

    summary_obj = smoke.get("summary")
    summary: Dict[str, Any] = summary_obj if isinstance(summary_obj, dict) else {}

    total = int(summary.get("total") or 0)
    ok = int(summary.get("ok") or 0)
    ng = int(summary.get("ng") or max(total - ok, 0))

    errors = smoke.get("errors") or []
    if not isinstance(errors, list):
        errors = []

    # KILL: 認証/署名/契約系（人間介入）
    kill_markers = ["invalid api key", "signature", "timestamp", "unauthorized", "permission"]
    for e in errors:
        e = e or {}
        msg = str(e.get("message") or "").lower()
        code = e.get("code")
        if any(k in msg for k in kill_markers) or code in (401, 403):
            return {
                "action": "KILL",
                "allow_orders": False,
                "reason": f"auth_or_contract_error:{code}:{msg[:120]}",
                "retry_after_sec": 0,
            }

    # RETRY: 一時障害（レート制限/5xx/timeout）
    retry_markers = ["timeout", "rate limit", "too many requests", "temporarily", "overloaded"]
    for e in errors:
        e = e or {}
        msg = str(e.get("message") or "").lower()
        code = e.get("code")
        if any(k in msg for k in retry_markers) or code in (429, 500, 502, 503, 504):
            return {
                "action": "RETRY",
                "allow_orders": False,
                "reason": f"transient_error:{code}:{msg[:120]}",
                "retry_after_sec": 60,
            }

    # STOP: 環境ブロック（close-only / insufficient 等）
    stop_markers = ["insufficient", "balance", "margin", "close-only", "close only", "reduce only", "maintenance"]
    for e in errors:
        e = e or {}
        msg = str(e.get("message") or "").lower()
        if any(k in msg for k in stop_markers):
            return {
                "action": "STOP",
                "allow_orders": False,
                "reason": f"environment_block:{msg[:120]}",
                "retry_after_sec": 0,
            }

    # NG があれば STOP（最小ルール）
    if total > 0 and ng > 0:
        return {
            "action": "STOP",
            "allow_orders": False,
            "reason": f"smoke_failed:{ok}/{total}",
            "retry_after_sec": 0,
        }

    return {
        "action": "PROCEED",
        "allow_orders": True,
        "reason": "smoke_ok",
        "retry_after_sec": 0,
    }


# =========================
# Main
# =========================
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=os.environ.get("BYBIT_PROFILE", "paper"))
    ap.add_argument("--exchange", default=os.environ.get("UNIVBOT_EXCHANGE", "bybit"))
    ap.add_argument(
        "--config",
        default=os.environ.get(
            "BYBIT_CONFIG",
            str(REPO_ROOT / "config" / "private" / "bybit_api_config.json")
        ),
    )
    args = ap.parse_args()

    ex = (args.exchange or "bybit").strip().lower()

    global OUTDIR
    OUTDIR = get_outdir(ex)
    OUTDIR.mkdir(parents=True, exist_ok=True)

    # env 経由で auth ローダに渡す
    os.environ["BYBIT_PROFILE"] = str(args.profile)
    os.environ["BYBIT_CONFIG"] = str(args.config)

    # utils から base_url を取得
    from utils.auth_loader_bybit import load_bybit_api_keys

    os.environ["BYBIT_CONFIG"] = args.config

    from typing import Any, Dict

    auth_opt = load_bybit_api_keys()

    if auth_opt is None:
        raise RuntimeError("bybit auth config load failed (auth is None)")
    if not isinstance(auth_opt, dict):
        raise RuntimeError(f"bybit auth config load failed (auth type={type(auth_opt)})")

    auth: Dict[str, Any] = auth_opt  # ← ここで Pylance 的に dict と確定する

    base_url = auth.get("base_url")
    if not isinstance(base_url, str) or not base_url:
        raise RuntimeError("base_url not found in api config")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTDIR / "risk_state.json"

        # base_url は auth から取れている前提
    if ex == "mexc":
        from adapters.mexc.trading import MexcTradingAdapter
        # MexcTradingAdapter は env の MEXC_BASE_URL を見る実装だったので合わせる
        os.environ["MEXC_BASE_URL"] = "https://api.mexc.com"
        adapter = MexcTradingAdapter()
    else:
        from adapters.bybit.trading import BybitTradingAdapter
        # BybitTradingAdapter は env の BYBIT_BASE_URL を見る実装だったので合わせる
        os.environ["BYBIT_BASE_URL"] = str(base_url)
        adapter = BybitTradingAdapter()

    abs_ret, bb_width_pct = btc_metrics(adapter)

    n_os, tot = breadth_oversold()

    breadth_ratio = (n_os / tot) if tot else 0.0

    # regime 判定
    if (abs_ret >= PANIC_RET) or (bb_width_pct >= PANIC_BB) or (breadth_ratio >= PANIC_BREADTH):
        market = "panic"
        size_mult = SIZE_PANIC
    elif (abs_ret >= CAUTION_RET) or (bb_width_pct >= CAUTION_BB) or (breadth_ratio >= CAUTION_BREADTH):
        market = "caution"
        size_mult = SIZE_CAUTION
    else:
        market = "normal"
        size_mult = SIZE_NORMAL

    # ---- NEW: order smoke の結果を取り込んで exec gate を決める
    smoke = load_order_smoke_state()
    exec_gate = classify_smoke_gate(smoke)

    rs = {
        "ts": int(time.time() * 1000),
        # abs_ret は比率なので「pct」という名前は誤解を生むが、既存互換のためキー名は維持
        "btc_abs_daily_ret_pct": round(abs_ret, 6),
        "btc_bb_width_pct": bb_width_pct,
        "breadth_oversold": n_os,
        "breadth_total": tot,
        "breadth_ratio": round(breadth_ratio, 4),
        "market": market,
        "size_mult": size_mult,
        "exec_gate": exec_gate,
        "smoke": smoke,


        # ---- NEW: 実行可否ゲート（STOP/KILL/RETRY/PROCEED）
        "exec_gate": exec_gate,

        # ---- NEW: スモーク原文（不要なら消してOK。summaryだけにしても良い）
        "smoke": smoke,
    }

    out_path = OUTDIR / "risk_state.json"
    out_path.write_text(json.dumps(rs, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[risk]", rs)


if __name__ == "__main__":
    main()
