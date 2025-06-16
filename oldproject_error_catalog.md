# Old Project – Extended Error Catalog

The initial summary documented the **critical** architectural flaws. This catalog lists **additional** issues discovered after a deeper static pass over the entire `oldproject/` repository. Each finding includes: *scope*, *problem*, *impact*, and *recommendation*.

---
## 0. Legend
| Severity | Emoji | Meaning |
|----------|-------|---------|
| Critical | 🔴 | Breaks core functionality or risks user funds/data |
| Major    | 🟠 | High likelihood of bugs/perf issues |
| Minor    | 🟡 | Code smell, maintainability |
| Info     | ⚪ | Cosmetic |

---
## 1. Implementation Gaps  
Numerous `pass` placeholders and `TODO` comments indicate unfinished logic.

| File | Lines | Severity | Notes |
|------|-------|----------|-------|
| `blockchain/provider_adapter.py` | 50-85 | 🔴 | All key adapter methods empty – fallback rotation never executed |
| `services/deep_scan_orchestrator.py` | 61-136 | 🟠 | Entire orchestration stubbed, yet referenced by bot flags |
| `dex/*_client.py` | 21-25 | 🟠 | Raydium/Orca/Jupiter sync wrappers are empty; liquidity analysis unreliable |
| `token_analyzer.py` | 30-40 / 651-666 | 🟡 | Async init/close `pass` ⇒ resource leaks |
| `utils/performance_monitor.py` | 90-100 | 🟡 | Placeholder overrides cause `NoneType` errors in runtime metrics |

> **Impact:** Hidden `AttributeError`/`None` surfaces under production load, bot appears to "randomly" fail.

> **Recommendation:** Remove dead code or fully implement before enabling feature flags.

---
## 2. Sync vs Async Collision
* `token_analyzer.py` declares `async def` helpers but internally **calls blocking** `solana_client.py` functions (`requests.post`) – event loop starvation.
* `utils/connection_pool.py` implements a custom async pool, yet underlying connections default to synchronous sockets, defeating concurrency.

| Manifestation | Severity | Fix |
|---------------|----------|-----|
| Long-polling Telegram handler blocks on network | 🔴 | Adopt `aiohttp` + `aiogram` |
| Misleading unit tests marked `pytest.mark.asyncio` but mock sync clients | 🟡 | Switch to real async mocks (`pytest-httpx`) |

---
## 3. Endpoint Misuse
1. **Helius Enhanced Tx** – Used for tokens BEFORE mint finalised (placeholder 40-char), causing 400/"invalid address".
2. **Birdeye Price Calls** – Hard-coded to `/v1/defi/token_overview`, deprecated (returns 410).
3. **Jupiter API** – Hits v6 `/price` with 200 ms rate-limit; no back-off implemented; spams on loop.

| Impact | Severity |
|--------|----------|
| Frequent 400/410 errors escalate to circuit breaker Open state → total scan failure | 🔴 |

---
## 4. Security Concerns
| Issue | File | Severity | Notes |
|-------|------|----------|-------|
| Plaintext password check in sample OAuth route | `api/routes/security_routes.py` | 🔴 | Demo creds stored in code |
| `.env.example` leaks variable names that include `PRIVATE_KEY` placeholders | root | 🟡 | Could encourage bad practices |
| Logging full RPC payload including bearer keys in `blockchain/solana_client.py` debug path | 240-260 | 🟠 | Key leakage risk when logs shared |

---
## 5. Error Handling & Observability
* Exponential back-off logic partially implemented (`utils/circuit_breaker.py`) but **swallows exception** and returns `None`, leading to silent failures.
* Re-tries hardcoded to **3 attempts** without jitter – thundering herd on provider restarts.
* Logs inconsistent JSON vs plain-text; impossible to parse downstream.

---
## 6. Testing Gaps
* 230+ tests exist but majority *mock* high-level calls; coverage of actual RPC integration = **0 %**.
* No contract for log messages → assertions rely on fragile string matching.
* CI uses Python 3.9; code imports 3.11 features (`StrEnum`), causing pipeline failures.

---
## 7. Dependency Drift
| Library | Required Ver | Actual | Issue |
|---------|--------------|--------|-------|
| `python-telegram-bot` | ≥ 20 (async) | 13.11 | Deprecated, sync |
| `solana-py` | 0.30 | Not pinned | API break after 0.29 |
| `requests` | 2.31 | 2.25 | CVE-2023-32681 |

---
## 8. Code Quality
* 5600+ `flake8` violations (unused imports, long lines).
* Circular imports between `services/data_pipeline.py` and `utils/birdeye_client.py` via cache helpers.
* Functions >400 LOC (`data_pipeline.run_full_scan`) hamper maintainability.

---
## 9. Miscellaneous
* **Platform Quirks:** README instructs Unix `source venv/bin/activate` but user environment is Windows.
* **Dockerfile:** Uses Python 3.9-slim but code calls `match` (Python 3.10). Build fails.
* **Cache Keys:** Use raw mint address but not case-normalized → duplicate storage for checksummed vs lower-case.

---
## 10. Consolidated Recommendations (Short-Term)
1. **Eliminate all blocking I/O** – migrate to proper async clients.
2. **Validate mint string** before any network request; short-circuit placeholder mints.
3. **Refactor provider adapter** into reliable rotation with circuit-breaker & jittered back-off.
4. **Upgrade dependencies** & lock via `poetry` or `pip-tools`.
5. **Harden logging** – never record API keys or full payloads.
6. **Remove/complete TODO placeholders**; feature-flag unfinished modules off.
7. **Write integration tests** hitting public Helius sandbox to cover RPC flows.

> Following these will prevent old mistakes from bleeding into BlazeAI Lite. 