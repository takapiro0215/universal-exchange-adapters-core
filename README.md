# Universal Exchange Adapters (WIP)

I am not a professional trader.
I am not a professional software engineer either.

This project exists because I **did not want to get wiped out**.

After real operational failures (exchange shutdowns, API changes, regional restrictions),
I learned that **survivability matters more than profits**.

This repository provides an **exchange-agnostic adapter architecture**
so your trading system can survive exchange changes **without being rewritten**.

> Japanese documentation is intentionally omitted. Please translate if needed.

---

## Philosophy

- You don’t need to win every day
- You **must** survive the year
- Exchanges can disappear, restrict regions, or change APIs
- Trading logic should never depend directly on exchange APIs
- **Trading and Treasury (withdrawal) must be separated**
- Maximum Drawdown (DD) is a **hard constraint**, not a parameter

This is not about “how to get rich”.
This is about **not dying first**.

Survivability requires strict separation of roles and responsibilities.

---

## Philosophy: Wind, Forest, Fire, Mountain — and Shadow

This system strictly separates **information, decision, and execution**.

- **Wind (BTC)**  
  Observes overall market direction and volatility.  
  *(BTC's overwhelming trading volume dictates the general market sentiment.)*

- **Forest (Workers)**  
  Executes predefined actions without interpretation or discretion.

- **Fire (BCH)**  
  Detects ignition, overheating, and abnormal market behavior.  
  *(BCH is utilized due to its historical tendency to move independently of BTC,
  serving as a robust anomaly detector.)*

- **Mountain (Supervisor)**  
  Makes all final decisions mechanically, based on rules and constraints.

- **Shadow (Intelligence)**  
  Gathers environmental signals only when requested.  
  The Shadow never executes trades and never issues commands.

The Forest never decides.  
The Shadow never acts.  
The Mountain never guesses.

Emotion, discretion, and hype are intentionally excluded.

---

## What This Repository Is

- A **fixed adapter interface** for crypto exchanges
- A defensive architecture against:
  - API changes
  - exchange exits
  - region bans
  - operational mistakes
- A foundation you can extend to:
  - Bybit
  - MEXC
  - BTCC
  - Bitget
  - Binance
  - (later: Japanese exchanges)

---

## What This Repository Is NOT

- ❌ A trading strategy
- ❌ A profit guarantee
- ❌ Investment advice
- ❌ A ready-to-use money machine
- ❌ A place for API keys or secrets

If you are looking for a “copy & profit bot”, this is not for you.

---

## Core Design

### Adapter Pattern (Fixed Interface)

Your trading system talks only to:

- `TradingAdapter` (no withdrawal capability)
- `TreasuryAdapter` (withdrawal only, stronger guards)

Exchange-specific behavior is fully isolated behind adapters.

If an exchange dies, you replace the adapter — not the system.

---

### Trading vs Treasury (Important)

**TradingAdapter**
- Place / cancel orders
- Read balances & positions
- **No withdrawal capability**

**TreasuryAdapter**
- Withdrawals
- Optional fixed-IP enforcement
- Separate API keys
- Stronger guards & rate limits

This separation exists to protect capital.

---

## Repository Structure (Expected)

> Adjust paths to match your current tree.
```
.
├── adapters/
│ ├── base.py # fixed interfaces (Trading/Treasury)
│ ├── bybit/
│ ├── mexc/
│ └── ...
├── tools/
│ └── meta_supervisor.py # reads balance, computes TradingPot, writes runtime params
├── frontend/ # Vite + React UI (optional)
├── runtime/ # generated at runtime (NOT in git)
├── logs/ # NOT in git
├── out/ # NOT in git
└── README.md
```

---

## Optional Doctrines & Intelligence Layers

Extended philosophy and experimental modules are documented separately:

- `docs/doctrine/` — constitutional doctrines (Wind/Forest/Fire/Mountain/Shadow)
- `intel/` — optional intelligence layers (internal vs public-facing)

These modules never execute trades and remain strictly informational.
