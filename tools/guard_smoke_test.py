# tools/guard_smoke_test.py
import os, json, time, inspect
from pathlib import Path

# ここは固定でOK（必要なら変更）
DEFAULT_SYMBOL = os.environ.get("GUARD_SMOKE_SYMBOL", "BTCUSDT")
DEFAULT_QTY = float(os.environ.get("GUARD_SMOKE_QTY", "0.001"))
DEFAULT_PRICE = float(os.environ.get("GUARD_SMOKE_PRICE", "87500"))



def write_guard_state(paused: bool, reason: str = "") -> Path:
    p = Path(os.environ.get("GUARD_STATE_PATH", "out/guard_state.json"))
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "paused": bool(paused),
        "pause_reason": reason,
        "paused_at": int(time.time()) if paused else ""
    }
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p

def pick_order_func(mod):
    # reduceOnly を引数に持つ関数を自動検出して使う
    candidates = []
    for name, obj in vars(mod).items():
        if not callable(obj) or name.startswith("_"):
            continue
        try:
            sig = inspect.signature(obj)
        except Exception:
            continue
        params = sig.parameters
        if "reduceOnly" in params or "reduce_only" in params:
            candidates.append((name, obj, sig))
    if not candidates:
        raise RuntimeError("order_bybit内に reduceOnly 引数を持つ関数が見つかりません。")
    # 一番それっぽいものを優先（引数が多い=メイン関数の可能性が高い）
    candidates.sort(key=lambda x: len(x[2].parameters), reverse=True)
    return candidates[0]

def build_kwargs(sig, reduce_only: bool):
    params = sig.parameters
    kw = {}

    # よくある必須系を自動で埋める（存在するものだけ）
    if "symbol" in params: kw["symbol"] = DEFAULT_SYMBOL
    if "side" in params: kw["side"] = "Buy"
    if "qty" in params: kw["qty"] = DEFAULT_QTY
    if "quantity" in params: kw["quantity"] = DEFAULT_QTY
        # limit order の必須 price
    if "price" in params:
        kw["price"] = DEFAULT_PRICE


    # order type
    if "orderType" in params: kw["orderType"] = "Market"
    if "order_type" in params: kw["order_type"] = "Market"

    # Bybit v5でよくある category
    if "category" in params: kw["category"] = "linear"

    # reduceOnly
    if "reduceOnly" in params: kw["reduceOnly"] = bool(reduce_only)
    if "reduce_only" in params: kw["reduce_only"] = bool(reduce_only)

    # timeInForceが必要なら適当に
    if "timeInForce" in params and "timeInForce" not in kw: kw["timeInForce"] = "IOC"
    if "time_in_force" in params and "time_in_force" not in kw: kw["time_in_force"] = "IOC"

    return kw

def main():
    # 事故防止：ここで必ずDRY_RUNを強制（APIに投げない前提）
    os.environ["UNIVBOT_DRY_RUN"] = os.environ.get("UNIVBOT_DRY_RUN", "1")

    import utils.order_bybit as ob

    name, fn, sig = pick_order_func(ob)
    print(f"[guard_smoke] using: {name}{sig}")
    print(f"[guard_smoke] GUARD_STATE_PATH={os.environ.get('GUARD_STATE_PATH', 'out/guard_state.json')}")
    print(f"[guard_smoke] DRY_RUN={os.environ.get('UNIVBOT_DRY_RUN')} symbol={DEFAULT_SYMBOL} qty={DEFAULT_QTY}")

    # 1) paused=true で新規（reduceOnly=False）が止まるか
    p = write_guard_state(True, "manual_test")
    print(f"[guard_smoke] wrote {p} paused=true")
    try:
        kw = build_kwargs(sig, reduce_only=False)
        print("[guard_smoke] try NEW ENTRY (reduceOnly=False)...")
        out = fn(**kw)
        print("[guard_smoke] UNEXPECTED: new entry passed. return=", out)
    except Exception as e:
        print("[guard_smoke] OK: new entry blocked ->", repr(e))

    # 2) paused=true でも決済（reduceOnly=True）が通るか
    try:
        kw = build_kwargs(sig, reduce_only=True)
        print("[guard_smoke] try REDUCE ONLY (reduceOnly=True)...")
        out = fn(**kw)
        print("[guard_smoke] OK: reduceOnly passed. return=", out)
    except Exception as e:
        print("[guard_smoke] NOTE: reduceOnly failed ->", repr(e))

    # 3) paused=false で新規が通るか（DRY_RUNで通るはず）
    p = write_guard_state(False, "")
    print(f"[guard_smoke] wrote {p} paused=false")
    try:
        kw = build_kwargs(sig, reduce_only=False)
        print("[guard_smoke] try NEW ENTRY with paused=false...")
        out = fn(**kw)
        print("[guard_smoke] OK: new entry passed. return=", out)
    except Exception as e:
        print("[guard_smoke] NOTE: new entry failed even when unpaused ->", repr(e))

def smoke_adapter_shapes():
    # MEXC adapter skeleton should be importable and type-compatible
    from adapters.mexc.trading import MexcTradingAdapter    

    a = MexcTradingAdapter()
    a.ping()

    mi = a.get_market_info("BTCUSDT")
    bals = a.get_balances()

    print("[ok] mexc adapter skeleton")
    print(" market_info:", mi)
    print(" balances:", bals)
    print(" best_bid_ask:", a.get_best_bid_ask("BTCUSDT"))


if __name__ == "__main__":
    # existing smoke calls...
    smoke_adapter_shapes()
