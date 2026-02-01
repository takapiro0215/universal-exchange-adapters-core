"""
NO-EXEC Order Intent Demo

Prints an order intent, but does not submit anything.
Execution is intentionally excluded from Public Core demos.
"""


def main():
    print("=== NO-EXEC Order Intent Demo ===")

    intent = {
        "symbol": "BTC/USDT",
        "side": "buy",
        "type": "market",
        "qty": 0.001,
        "mode": "NO-EXEC",
    }

    print("Order Intent:")
    print(intent)

    print("\\nNo order was submitted.")
    print("This repository does not distribute execution authority.")


if __name__ == "__main__":
    main()
