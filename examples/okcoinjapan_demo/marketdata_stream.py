"""
OKCoin Japan MarketData Demo (NO-EXEC)
Public proof layer only.

Uses OKX public books endpoint as a stable "OKCoin-style" proof path.
If you have a Japan-specific endpoint, swap it here later.
"""

import time
import requests

# OKX public endpoint (common/compatible proof path)
OKX_BOOKS = "https://www.okx.com/api/v5/market/books"


def fetch_orderbook(inst_id="BTC-USDT", sz="5"):
    r = requests.get(OKX_BOOKS, params={"instId": inst_id, "sz": sz}, timeout=10)
    r.raise_for_status()
    return r.json()


def main():
    print("UEH OKCoin Japan MarketData Demo (NO-EXEC)")

    while True:
        j = fetch_orderbook()
        data = j["data"][0]
        bids = data["bids"]
        asks = data["asks"]

        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        print(f"[OKCoin/OKX-style] mid={mid:.2f} spread={spread:.4f}")
        time.sleep(2)


if __name__ == "__main__":
    main()
