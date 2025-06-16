# Old Project – Re-usable Assets for BlazeAI Lite

This file lists **only** the well-implemented, non-broken components and ideas from `oldproject/` that are worth porting into the new asynchronous codebase.  The selection was made after:
1. A lint/quality scan (flake8, grep for `pass`/`TODO`),
2. Manual inspection of logic & unit-test coverage, and
3. Confirmation that external APIs used remain **current** and **supported**.

---
## 1. Utility Functions & Helpers

| File | Function(s) | Why They're Good | Porting Notes |
|------|-------------|-----------------|---------------|
| `src/utils/address_utils.py` | `validate_solana_address`, `truncate_address`, `is_program_address` | Accurate Base58 & checksum validation; concise, <40 LOC; unit tests pass | Convert to pure functions in `blaze/utils/address.py`; already free of I/O so async-ready |
| `src/blockchain/utils.py` | `get_metadata_address`, `get_associated_token_address`, PDA helpers | Correct derivation of SPL Metadata & ATA PDAs using `sha256` seeds | Replace `pysolana` with `solders` seeds API; leave algorithm intact |
| `src/utils/circuit_breaker.py` | `CircuitBreaker` class (excluding unfinished fallback stubs) | Implements half-open window, failure threshold, reset timer | Wrap internal calls in `asyncio.to_thread` or refactor methods to async; reuse state logic |
| `src/utils/performance_monitor.py` | `time_function` decorator | Simple decorator measuring execution time & logging | Re-export as `@timed` in new `utils/metrics.py`; ensure works with async via `functools.wraps` & `async def` support |
| `src/utils/validators.py` | Basic numeric & string validators | Lightweight, pure functions; high test coverage | Keep as is; move to `blaze/utils/validators.py` |

---
## 2. Risk-Scoring Heuristics (Logic Only)

Although the **old analyzers** mix sync I/O, the **heuristic formulas** are sound and can be transplanted:

1. **Holder Concentration** – `analysis/token_analyzer.py` (method `analyze_holder_distribution`) computes top-1 / top-5 / top-10 share and flags thresholds >40 %, 70 %, 85 %.
2. **Mint & Freeze Authority Checks** – logic around `mint_authority == null` and `freeze_authority == null` to downgrade risk when both revoked.
3. **Liquidity Risk Score** – simple scoring: if LP lock missing → +4 risk; if lock <30 days → +2.
4. **Developer Wallet Reputation** – cross-reference wallet against static `rugpull_db.json` and add +5 risk per offence.

These algorithms are **stateless** and free of external calls; they can be re-implemented inside the new `RiskEngine` without modification.

---
## 3. UX & Messaging Assets

| Asset | Location | Benefit | Action |
|-------|----------|---------|--------|
| Emoji constants & Markdown templates | `src/bot/message_templates.py` | Consistent, user-friendly output identical to sample scan result | Copy into `blaze/bot/templates.py`; adjust to Telegram MarkdownV2 escape rules in aiogram |
| Risk-level colour coding (🟢 / 🟡 / 🔴) | `src/models/risk_level.py` | Clear enum mapping risk-score ranges (0-3 green, 4-6 yellow, 7-10 red) | Re-use enum exactly; ensure `enum.StrEnum` for Python 3.11 |

---
## 4. Environment & Config Patterns

* `.env.example` enumerates **all** runtime variables (BOT_TOKEN, HELIUS_API_KEY, RPC_URLS, LOG_LEVEL).  The list itself is valid; only the sample secrets are placeholders.
* `config/` directory contains `default.yml` with log formatters & cache TTLs.  YAML layout is reusable; we will load via `pydantic-settings`.

---
## 5. Documentation Snippets Worth Keeping

* **README sections 2–5** (Runtime Architecture, External Integrations, Caching, Error Handling) offer clear explanatory diagrams and tables.  We will adapt the wording but retain the diagrams in the new README.
* Mermaid **sequence diagram** for `/scan` call-flow provides an excellent visual that remains accurate for our pared-down MVP.

---
## 6. Test Cases to Salvage

| Test File | Why Keep? | Adaptation |
|-----------|-----------|------------|
| `tests/analysis/test_risk_classifier.py` | Validates risk level thresholds & explanation strings | Convert to async where needed; keep input fixtures |
| `tests/blockchain/test_solana_client.py` (metadata parsing only) | Tests Base64 decoding & struct unpacking logic | Detach from requests mocks; supply binary fixtures |

---
## 7. Algorithms Confirmed **Obsolete** (DO NOT PORT)

* Deep scan orchestrator, anomaly detector ML stubs, custom connection pool, legacy Telegram polling loop – all marked for removal.

---
## 8. Next Actions
1. Port **utility functions** into `newproject/blaze/utils/` with unit tests.
2. Migrate **risk heuristics** into `blaze/analysis/risk_engine.py`.
3. Re-use **message templates** & enums in new `aiogram` handlers.
4. Incorporate `.env.example` variables into new `pydantic` `Settings` model.

By focusing on these vetted assets, we leverage the strong parts of the old code while avoiding its pitfalls. 