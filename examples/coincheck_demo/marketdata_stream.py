"""
Coincheck MarketData Demo (NO-EXEC)
Public proof layer only.

Uses Coincheck public ticker endpoint.
"""

import time
import requests

COINCHECK_TICKER = "https://coincheck.com/api/ticker"


def fetch_ticker():
    r = requests.get(COINCHECK_TICKER, timeout=10)
    r.raise_for_status()
    return r.json()


def main():
    print("UEH Coincheck MarketData Demo (NO-EXEC)")

    while True:
        t = fetch_ticker()

        # Coincheck ticker keys: last, bid, ask, high, low, volume, timestamp
        bid = float(t["bid"])
        ask = float(t["ask"])
        last = float(t["last"])
        spread = ask - bid

        print(f"[Coincheck] last={last:.0f} bid={bid:.0f} ask={ask:.0f} spread={spread:.0f}")
        time.sleep(2)


if __name__ == "__main__":
    main()
