"""
Bitget MarketData Demo (NO-EXEC)
Minimal ticker-only proof.
"""

import time
import requests

BITGET_TICKER = "https://api.bitget.com/api/v2/spot/market/tickers"


def fetch_ticker():
    r = requests.get(BITGET_TICKER, timeout=10)
    r.raise_for_status()
    return r.json()


def main():
    print("UEH Bitget MarketData Demo (NO-EXEC)")

    while True:
        j = fetch_ticker()

        # Bitget returns list of tickers; select BTCUSDT if present
        data = j.get("data", [])
        btc = next((x for x in data if x.get("symbol") == "BTCUSDT"), None)

        if btc:
            last = btc.get("lastPr")
            print(f"[Bitget] BTCUSDT last={last}")
        else:
            print("[Bitget] BTCUSDT not found in ticker response")

        time.sleep(2)


if __name__ == "__main__":
    main()
