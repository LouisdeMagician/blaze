# Old Project Summary (Reference Only)

This document distils the essential knowledge from **`oldproject/`** so that we can cherry-pick good ideas and consciously avoid past mistakes while building **BlazeAI Lite**.

---
## 1. High-Level Architecture (Legacy)
```
┌──────────┐    HTTP     ┌─────────────┐
│ Telegram │────────────▶│ telegram_bot│
└──────────┘             └─────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ services/    │  (Business logic – sync)
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ analysis/    │  (Risk, liquidity, ML)
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ blockchain/  │  (Solana, Helius, utils)
                     └──────────────┘
```
* Everything ran **synchronously** (`requests`, `python-telegram-bot` v13).
* MongoDB access was stubbed behind `database_service.py` but never fully implemented.

---
## 2. Detailed Module Inventory

### `src/blockchain/`
| File | Purpose | Key Issues |
|------|---------|-----------|
| `solana_client.py` | Raw JSON-RPC wrapper using `requests.post` | Blocking, single endpoint, brittle error handling |
| `helius_client.py` | Helius REST wrapper (assets, holders, enhanced-tx) | Same blocking pattern; 400 error on invalid mint not caught early |
| `provider_adapter.py` | Abstracts multiple providers | Implemented but still synchronous; no true rotation logic |
| `utils.py` | Address derivations (PDA, metadata) | Generally solid – can port to async version |
| `enhanced_rpc_provider.py`, `rpc_provider.py` | Additional wrappers | Redundant complexity |

### `src/analysis/`
| Area | Notable Files | Observations |
|------|---------------|-------------|
| Liquidity & Risk | `liquidity_analyzer.py`, `token_analyzer.py`, `smart_money/` | Useful heuristics but tightly coupled to sync clients |
| ML Stubs | `anomaly_detector.py` (deleted), etc. | Partial / unfinished |

### `src/services/`
| Service | Function | Pitfalls |
|---------|----------|----------|
| `deep_scan_orchestrator.py` | Multi-step scan pipeline | Heavy, sequential, slow |
| `cache_service.py` | In-memory cache | Lacked eviction policy |
| `database_service.py` | Mongo stub | Unused, no async driver |

### `src/bot/`
* Handlers in `telegram_bot.py` and command modules.
* Relied on **blocking long-polling**; rate-limited easily.

---
## 3. Root-Cause Analysis of Production Failures
1. **Cloudflare 522** – Dedicated Helius endpoint required IP whitelist. The bot never fell back to the public `mainnet.helius-rpc.com`.
2. **Invalid Mint Handling** – Pump.fun placeholders ended with `pump`; string was truncated to 40 chars (instead of 44) ⇒ Helius 400 "invalid address".
3. **Synchronous Design** – Each network call blocked the main thread; timeouts (even after raising from 10→25 s) cascaded and froze the bot.
4. **No Endpoint Rotation** – Provider adapter listed multiple RPCs but selected just one; no exponential back-off or circuit breaker.
5. **Outdated Dependencies** – `python-telegram-bot==13.x` (non-async), `requests==2.x`; incompatible with modern async paradigms.
6. **Over-Engineering Without Delivery** – Deep scan pipeline & ML stubs added complexity but never produced stable output.

---
## 4. Components Worth Recycling
| Component | Why Keep? | Porting Notes |
|-----------|-----------|--------------|
| `src/utils/address_utils.py` | Robust base58 validation, truncation & program checks | Lift into new `utils/` with minor tweaks |
| `src/utils/circuit_breaker.py` | Generic breaker with half-open state | Add async-aware wrapper |
| `src/utils/performance_monitor.py` | Decorator for timing functions | Ensure it supports `async def` |
| Emoji / Markdown message templates | Good UX language | Re-implement in aiogram-compatible format |

---
## 5. Lessons Learned → Guiding Principles for BlazeAI Lite
1. **Async-First Everything** – Use `aiohttp`, `aiogram`, `motor`, `pytest-asyncio`.
2. **Validate Early** – Check mint length (44 base58 chars) before any network hit.
3. **Endpoint Strategy**
   * Rotate across `mainnet.helius-rpc.com`, Triton, Ankr.
   * Exponential back-off (`tenacity`) + circuit breaker.
4. **Lean MVP** – Resist premature ML; focus on deterministic heuristics.
5. **Observability Built-in** – Structured JSON logs, correlation ID, metrics.
6. **Modular Adapters** – Isolate Solana & Helius logic behind async interfaces.
7. **Test Coverage** – Keep >80 % unit test coverage with fast mocks.
8. **Memory Bank Discipline** – Record architectural decisions (specstory) to avoid context loss.

---
## 6. Mapping Old → New Modules
| Legacy Path | Replacement in `newproject/` |
|-------------|-----------------------------|
| `src/blockchain/solana_client.py` | `blaze/blockchain/solana_client_async.py` (aiohttp, rotations) |
| `src/blockchain/helius_client.py` | `blaze/blockchain/helius_adapter.py` (async, enhanced & assets) |
| `telegram_bot.py` | `blaze/bot/main.py` using `aiogram` v3 |
| `deep_scan_orchestrator.py` | 🔥 Omit for MVP – replaced by lightweight `ScanService` |
| `database_service.py` | `blaze/repos/token_repo.py` (motor) – optional cache |

---
## 7. Reference Snippets
### Invalid Pump Fun Truncation
```python
# oldproject/src/blockchain/utils.py
if mint.endswith("pump"):
    mint = mint[:-4]  # Leaves 40 chars – INVALID
```

### Blocking RPC Call
```python
# oldproject/src/blockchain/solana_client.py
response = requests.post(url, json=payload, timeout=25)
```

---
## 8. Action Items Extracted
- [ ] Port `address_utils` with async / no external deps.
- [ ] Build async Helius adapter with `/v0/token-metadata`, `/v0/transactions`.
- [ ] Implement `RiskEngine` with rule-based scoring.
- [ ] Write unit tests covering:
  * Mint validation edge cases
  * Endpoint rotation logic
  * Risk rules (mint authority, liquidity lock, holder concentration)

---
**Conclusion:** While `oldproject/` contains valuable heuristics and utility code, its blocking architecture and endpoint misconfigurations caused cascading failures. BlazeAI Lite will embrace an async, modular design with rigorous validation and observability to avoid repeating these mistakes. 