"""
bitFlyer MarketData Adapter Skeleton (NO-EXEC)
Public demo only.
"""

import time
import requests

BITFLYER_ENDPOINT = "https://api.bitflyer.com/v1/board"

def fetch_orderbook(symbol="BTC_JPY"):
    r = requests.get(BITFLYER_ENDPOINT, params={"product_code": symbol})
    r.raise_for_status()
    return r.json()

def main():
    print("UEH bitFlyer MarketData Demo (NO-EXEC)")

    while True:
        data = fetch_orderbook()
        mid = (data["bids"][0]["price"] + data["asks"][0]["price"]) / 2

        print(f"[bitFlyer] mid={mid} bids={len(data['bids'])} asks={len(data['asks'])}")

        time.sleep(2)

if __name__ == "__main__":
    main()
