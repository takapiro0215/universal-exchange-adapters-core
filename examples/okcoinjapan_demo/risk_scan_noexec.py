"""
Risk Scan Demo (NO EXECUTION)
Spread + liquidity check only.
"""

from marketdata_stream import fetch_orderbook


def scan(inst_id="BTC-USDT"):
    j = fetch_orderbook(inst_id=inst_id, sz="5")
    data = j["data"][0]
    bids = data["bids"]
    asks = data["asks"]

    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    spread = best_ask - best_bid

    bid_liq = sum(float(x[1]) for x in bids)
    ask_liq = sum(float(x[1]) for x in asks)

    status = "OK"
    if spread > 5:
        status = "WIDE"
    if bid_liq < 1 or ask_liq < 1:
        status = "THIN"

    return {
        "exchange": "OKCoin Japan (OKX-style proof)",
        "instrument": inst_id,
        "spread": spread,
        "bid_liquidity": bid_liq,
        "ask_liquidity": ask_liq,
        "status": status,
        "execution": "DISABLED",
    }


if __name__ == "__main__":
    print(scan())
