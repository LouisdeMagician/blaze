# Tech Context

## Languages & Runtimes
* **Python 3.11** – primary backend language
* **Node.js 20** – optional helper scripts (Jest tests, chart rendering)

## Key Libraries & Frameworks
| Purpose | Library |
|---------|---------|
| Async HTTP & Websocket | `aiohttp`, `websockets` |
| Solana JSON-RPC & Helius API | `solders` (low-level) + custom async client |
| Data validation | `pydantic` v2 |
| Database (optional) | `motor` (async Mongo) – stubbed for MVP |
| Telegram Bot | `aiogram` v3 |
| Retry / Circuit-breaker | `tenacity`, custom breaker in utils |
| Testing | `pytest`, `pytest-asyncio`, `pytest-httpx` |
| Linting / Formatting | `ruff`, `black`, `mypy` |

## Infrastructure
* **RPC** – `https://mainnet.helius-rpc.com` plus fallback to Triton & Ankr using round-robin.
* **CI/CD** – GitHub Actions running lint + test matrix.
* **Docker** – Multistage build (`slim-bullseye`) for deployment to Fly.io/Heroku.

## Constraints
* Must remain free-tier friendly: avoid heavy disk or RAM usage.
* No storing of user private keys.
* All config via environment variables – no secrets committed.

## External Services
1. **Helius Enhanced APIs** – metadata, transactions, holders.
2. **Jupiter Aggregator** – liquidity pools & tax estimation.
3. **DexScreener API** – price & liquidity lock reference.
4. **Birdeye** – volume & price chart (optional, caching required).

## Async Guidelines
* All I/O functions declared with `async def`.
* Use `async with aiohttp.ClientSession()` per request burst; share session via DI.
* Never call blocking libraries inside async tasks (use `run_in_executor` if needed).

## Endpoint Strategy
* Validate mint string length (44 chars, base58) before any request.
* Rotate between RPC URLs on timeout / rate-limit.
* Exponential back-off (`tenacity.retry`) with jitter and caps.

## Version Pinning (initial)
```
aiohttp==3.9.3
aiogram==3.4.1
pydantic==2.7.0
tenacity==8.2.3
solders==0.19.0
motor==3.3.1
pytest==8.1.1
pytest-asyncio==0.23.3
ruff==0.4.2
``` 