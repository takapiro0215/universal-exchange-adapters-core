# tools/order_smoke_test.py
# SAFE VERSION (standard)
# - Uses utils/order_bybit (Guard latch + DRY_RUN + mainnet safety)
# - RAW direct API version is tools/order_smoke_test_raw.py (diagnostics only)

from __future__ import annotations

import os
import time
import json
import argparse
import requests
from pathlib import Path
from typing import Any, Dict, Tuple, Optional, List

from adapters.factory import get_trading_adapter
from utils.auth_loader_bybit import load_bybit_api_keys
from utils.order_bybit import place_limit_order, cancel_order

S = requests.Session()
JsonDict = Dict[str, Any]


# =========================
# Log directory (same as risk_scan.py)
# =========================
LOCALAPPDATA = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
OUTDIR = Path(LOCALAPPDATA) / "UnivBot" / "bybit" / "logs"


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def j(resp: requests.Response) -> Tuple[int, JsonDict]:
    try:
        data = resp.json()
    except Exception:
        return resp.status_code, {"raw": resp.text}
    if isinstance(data, dict):
        return resp.status_code, data
    return resp.status_code, {"raw_json": data}


def get_instruments_meta(base: str, symbol: str):
    r = S.get(
        f"{base}/v5/market/instruments-info",
        params={"category": "linear", "symbol": symbol},
        timeout=10,
    )
    sc, js = j(r)
    lst = (js.get("result") or {}).get("list") or []
    if not lst:
        raise RuntimeError(f"no instruments-info: {sc} {js}")
    it = lst[0]
    pf = it.get("priceFilter") or {}
    lf = it.get("lotSizeFilter") or {}
    tick = float(pf.get("tickSize", "0.01"))
    qty_step = float(lf.get("qtyStep", "0.001"))
    min_qty = float(lf.get("minOrderQty", "0.001"))
    return tick, qty_step, min_qty


def get_bid_ask(base: str, symbol: str):
    r = S.get(
        f"{base}/v5/market/tickers",
        params={"category": "linear", "symbol": symbol},
        timeout=10,
    )
    sc, js = j(r)
    ob = (js.get("result") or {}).get("list") or []
    if not ob:
        raise RuntimeError(f"no tickers: {sc} {js}")
    bid = float(ob[0]["bid1Price"])
    ask = float(ob[0]["ask1Price"])
    return bid, ask


def round_to_step(x: float, step: float) -> float:
    return round(round(x / step) * step, 10)


def clip_qty(qty: float, step: float, min_qty: float) -> float:
    q = max(min_qty, round_to_step(qty, step))
    return q


def _err_record(kind: str, op: str, e: BaseException, code: Optional[int] = None, message: Optional[str] = None) -> Dict[str, Any]:
    msg = message if message is not None else repr(e)
    rec: Dict[str, Any] = {
        "kind": kind,
        "op": op,
        "message": msg,
    }
    if code is not None:
        rec["code"] = code
    return rec

def get_outdir(exchange: str) -> Path:
    ex = (exchange or "bybit").strip().lower()
    localapp = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(localapp) / "UnivBot" / ex / "logs"

def main(exchange: str, symbol: str, times: int, qty: float, skew: int, live: bool):
    ex = (exchange or "").strip().lower()

    # live=False なら DRY_RUN=1 を強制（ネット送信なし）
    if not live:
        os.environ["UNIVBOT_DRY_RUN"] = "1"

    dry = os.environ.get("UNIVBOT_DRY_RUN", "0").strip()
    dry_run = (dry == "1")

    # --- Build smoke state (always write at end) ---
    started_ms = int(time.time() * 1000)
    smoke_state: Dict[str, Any] = {
        "ts": started_ms,
        "exchange": ex,
        "symbol": symbol,
        "profile": os.environ.get("BYBIT_PROFILE", ""),
        "dry_run": dry_run,
        "live": bool(live),
        "summary": {"total": 0, "ok": 0, "ng": 0},
        "errors": [],  # list[{kind, code?, message, op}]
        "notes": [],
    }

    def _bump(ok: bool) -> None:
        smoke_state["summary"]["total"] += 1
        if ok:
            smoke_state["summary"]["ok"] += 1
        else:
            smoke_state["summary"]["ng"] += 1

    def _add_note(s: str) -> None:
        if isinstance(smoke_state.get("notes"), list):
            smoke_state["notes"].append(s)

    def _add_error(rec: Dict[str, Any]) -> None:
        if isinstance(smoke_state.get("errors"), list):
            smoke_state["errors"].append(rec)

    outdir = get_outdir(ex)
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / "order_smoke_state.json"




    try:
        # --- Common: construct adapter (read-only path always available) ---
        adapter = get_trading_adapter(ex)
        adapter.ping()
        caps = adapter.get_capabilities()

        mi = adapter.get_market_info(symbol)


        print(f"[env] exchange={adapter.name} DRY_RUN={dry} symbol={symbol}")
        print("[capabilities]", caps)
        print("[market_info]", mi)

        _add_note(f"adapter={adapter.name}")
        _add_note(f"caps={getattr(caps, '__dict__', str(caps))}")
        _add_note(f"market_info={mi}")

        # If adapter doesn't support orders yet, stop here (this is correct / intentional).
        if not getattr(caps, "supports_client_order_id", True):
            pass

        # Order placement support gate:
        # For now: bybit path remains the only executable order smoke.
        if ex != "bybit":
            print("[skip] order smoke not supported for this exchange yet (read-only smoke finished).")
            _add_note("order_smoke_skipped_non_bybit")
            # skipped is not a failure, but we also don't want to claim 'ok'
            return

        # --- Bybit-specific SAFE order smoke (existing path) ---
        auth_opt = load_bybit_api_keys()
        if auth_opt is None or not isinstance(auth_opt, dict):
            raise RuntimeError("bybit auth config load failed (auth is None or not dict)")
        base = auth_opt.get("base_url")
        if not isinstance(base, str) or not base:
            raise RuntimeError("base_url not found in api config")

        tick, qty_step, min_qty = get_instruments_meta(base, symbol)
        bid, ask = get_bid_ask(base, symbol)
        q = clip_qty(qty, qty_step, min_qty)

        print(
            f"[bybit] base={base} symbol={symbol} "
            f"bid/ask {bid:.2f} {ask:.2f} tick {tick} qty_step {qty_step} min_qty {min_qty} -> use_qty {q}"
        )
        _add_note(f"bybit_base={base}")
        _add_note(f"tick={tick} qty_step={qty_step} min_qty={min_qty} use_qty={q}")
        _add_note(f"bid={bid} ask={ask} skew={skew}")

        def do_create_and_cancel(side: str, px: float, link: str) -> bool:
            """
            1 test unit = (create + cancel). If any fails -> False.
            """
            # create
            try:
                res = place_limit_order(
                    symbol=symbol,
                    side=side,
                    qty=q,
                    price=px,
                    timeInForce="GTC",
                    reduceOnly=False,
                    orderLinkId=link,
                )
                print(f"create {side} {px} ->", res)
            except Exception as e:
                _add_error(_err_record("EXCEPTION", "place_limit_order", e))
                return False

            # live のときだけ少し待つ（約定/反映）
            if live:
                time.sleep(1.1)

            # cancel
            try:
                oid = res.get("orderId") if isinstance(res, dict) else None
                cres = cancel_order(symbol=symbol, orderId=oid, orderLinkId=(None if oid else link))
                print("cancel ->", cres)
            except Exception as e:
                _add_error(_err_record("EXCEPTION", "cancel_order", e))
                return False

            return True

        for i in range(times):
            sell_px = round_to_step(ask + skew * tick, tick)
            buy_px = round_to_step(bid - skew * tick, tick)

            # sell test
            ok1 = do_create_and_cancel("Sell", sell_px, f"safe-sell-{int(time.time()*1000)}-{i}")
            _bump(ok1)

            # buy test
            ok2 = do_create_and_cancel("Buy", buy_px, f"safe-buy-{int(time.time()*1000)}-{i}")
            _bump(ok2)

            # If any failed, stop early (SAFE)
            if not ok1 or not ok2:
                print("[SAFE_SMOKE] stopped early due to failure.")
                break

        print("[done] SAFE smoke finished (bybit safe path).")

    except Exception as e:
        # Record top-level failure too
        _add_error(_err_record("FATAL", "main", e))
        raise

    finally:
        finished_ms = int(time.time() * 1000)
        smoke_state["finished_ts"] = finished_ms
        smoke_state["elapsed_ms"] = finished_ms - started_ms

        # Always write the state so risk_scan can ingest it.
        _write_json(out_path, smoke_state)
        print(f"[smoke_state] wrote -> {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default="bybit", help="exchange name (bybit/mexc/...)")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--times", type=int, default=1)
    ap.add_argument("--qty", type=float, default=0.001)
    ap.add_argument("--skew", type=int, default=10, help="tickの何個分だけ離して指値を置くか")
    ap.add_argument("--live", action="store_true", help="実際にdemoへ発注/キャンセルする（DRY_RUNを無効化）")
    a = ap.parse_args()
    main(a.exchange, a.symbol, a.times, a.qty, a.skew, live=a.live)
