"""
Binance Japan MarketData Demo (NO-EXEC)
Public proof layer only.
"""

import time
import requests

BINANCE_DEPTH_ENDPOINT = "https://api.binance.com/api/v3/depth"

def fetch_orderbook(symbol="BTCUSDT", limit=5):
    r = requests.get(
        BINANCE_DEPTH_ENDPOINT,
        params={"symbol": symbol, "limit": limit},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()

def main():
    print("UEH Binance Japan MarketData Demo (NO-EXEC)")
    while True:
        ob = fetch_orderbook()
        best_bid = float(ob["bids"][0][0])
        best_ask = float(ob["asks"][0][0])
        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        print(f"[Binance] mid={mid:.2f} spread={spread:.4f}")
        time.sleep(2)

if __name__ == "__main__":
    main()
