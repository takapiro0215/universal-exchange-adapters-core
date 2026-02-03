"""
Risk Scan Demo (NO EXECUTION)
Ticker presence check only.
"""

from marketdata_stream import fetch_ticker


def scan():
    j = fetch_ticker()
    data = j.get("data", [])

    btc = next((x for x in data if x.get("symbol") == "BTCUSDT"), None)

    status = "OK" if btc else "MISSING"

    return {
        "exchange": "Bitget",
        "proof": "ticker-only",
        "status": status,
        "execution": "DISABLED",
    }


if __name__ == "__main__":
    print(scan())
