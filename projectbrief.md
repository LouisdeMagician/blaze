# Project Brief: BlazeAI Lite – Solana Risk Scanner

## Purpose
Rebuild the Solana analytics bot from scratch with a lean, maintainable and fully **asynchronous** codebase.  The new bot (codename **BlazeAI Lite**) focuses on delivering a concise *risk-rating scan* for any SPL token, similar to the sample report shown below:

```
🧠 BlazeAI Scan Result
Blockchain:  Solana
Token Name:  RugMeNot ($RMN)
Contract:    5k3d…Ab9L
…
```

## Core Functionalities (MVP)
1. **Token Validation & Metadata** – validate mint address, fetch name, symbol and supply via Helius Enhanced Transactions.
2. **Risk Scoring** – evaluate mint/freeze authority, top-holder concentration, liquidity lock, developer wallet history.
3. **Liquidity & Tax Scan** – pull Raydium/Jupiter pool data, evaluate buy/sell/transfer tax.
4. **Holder Distribution** – analyse holder list and compute concentration metrics.
5. **Developer Wallet Reputation** – cross-check against local rug-pull database.
6. **Telegram Output** – format a markdown-rich report identical to the BlazeAI sample.

## Key Non-Functional Requirements
* **Async-first**: All I/O (RPC, database, telegram) uses `asyncio`/`aiohttp`/`aiogram`.
* **Extensibility**: Modular service-adapter-repository layers.
* **Resilience**: Endpoint rotation, exponential back-off, circuit-breaker.
* **Observability**: Structured logging and metrics hooks.

## Out of Scope (for MVP)
* Portfolio dashboards
* ML anomaly detection
* L2 chains

## Success Criteria
* A user can issue `/scan <mint>` in Telegram and receive a full risk report within 5 seconds.
* The bot sustains 20 concurrent scans without rate-limit failures.
* Codebase passes `pytest` suite & `ruff`/`flake8` linting. 