"""
Risk Scan Demo (NO EXECUTION)
Checks spread + liquidity only.
"""

from marketdata_stream import fetch_orderbook

def scan(symbol="BTC_JPY"):
    ob = fetch_orderbook(symbol)

    best_bid = ob["bids"][0]["price"]
    best_ask = ob["asks"][0]["price"]

    spread = best_ask - best_bid

    return {
        "symbol": symbol,
        "spread": spread,
        "status": "OK" if spread < 500 else "WIDE",
        "execution": "DISABLED"
    }

if __name__ == "__main__":
    print(scan())
