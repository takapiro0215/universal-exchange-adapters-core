"""
Risk Scan Demo (NO EXECUTION)
Spread check only (ticker-based).
"""

from marketdata_stream import fetch_ticker


def scan():
    t = fetch_ticker()
    bid = float(t["bid"])
    ask = float(t["ask"])
    spread = ask - bid

    status = "OK"
    if spread > 2000:  # conservative default for JPY products
        status = "WIDE"

    return {
        "exchange": "Coincheck",
        "market": "BTC_JPY",
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "status": status,
        "execution": "DISABLED",
    }


if __name__ == "__main__":
    print(scan())
