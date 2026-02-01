# Bybit Demo (Survivability-First)

This demo shows the public core in action.

It is intentionally designed to be:

- observable
- non-profitable
- non-executable

This is not a trading system.
This is survivability scaffolding.

---

## Contents

- demo_marketdata.py
  Fetches basic market data (observation only)

- demo_risk_scan.py
  Runs survivability risk scan (PROCEED / HALT)

- demo_noexec_order_intent.py
  Prints an order intent without execution (NO-EXEC)

---

## Run

```powershell
PYTHONPATH=. python examples/bybit_demo/demo_marketdata.py
PYTHONPATH=. python examples/bybit_demo/demo_risk_scan.py
PYTHONPATH=. python examples/bybit_demo/demo_noexec_order_intent.py
```

---

## Invariant

When uncertain: stop and snapshot.
