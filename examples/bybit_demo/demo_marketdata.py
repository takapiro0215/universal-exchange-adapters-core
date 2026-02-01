"""
Market Data Demo (Observation Only)

This script demonstrates that adapters can fetch market surfaces.
No execution logic exists here.
"""

from adapters.bybit.adapter import BybitAdapter


def main():
    ex = BybitAdapter(profile="paper")

    print("=== Market Data Demo ===")
    ticker = ex.fetch_ticker("BTC/USDT")
    print("Ticker:", ticker)

    print("\\nObservation successful.")
    print("No execution authority exists in this demo.")


if __name__ == "__main__":
    main()
