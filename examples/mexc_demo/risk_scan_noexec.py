"""
Risk Scan Demo (NO EXECUTION)
Spread + liquidity check only.
"""

from marketdata_stream import fetch_orderbook


def scan(symbol="BTCUSDT"):
    ob = fetch_orderbook(symbol, limit=5)

    best_bid = float(ob["bids"][0][0])
    best_ask = float(ob["asks"][0][0])
    spread = best_ask - best_bid

    bid_liq = sum(float(x[1]) for x in ob["bids"])
    ask_liq = sum(float(x[1]) for x in ob["asks"])

    status = "OK"
    if spread > 5:
        status = "WIDE"
    if bid_liq < 1 or ask_liq < 1:
        status = "THIN"

    return {
        "exchange": "MEXC",
        "symbol": symbol,
        "spread": spread,
        "bid_liquidity": bid_liq,
        "ask_liquidity": ask_liq,
        "status": status,
        "execution": "DISABLED"
    }


if __name__ == "__main__":
    print(scan())
