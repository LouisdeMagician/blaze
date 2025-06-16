# System Patterns

## High-Level Architecture
```
┌───────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  Telegram UI  │──────▶│  Bot Command     │──────▶│  Application     │
│  (aiogram)    │       │  Handlers        │       │  Services Layer  │
└───────────────┘       └──────────────────┘       └─────────┬────────┘
                                                  ┌──────────▼──────────┐
                                                  │  Adapters (RPC,     │
                                                  │  Helius, Jupiter)   │
                                                  └──────────┬──────────┘
                                                             ▼
                                                  ┌──────────────────────┐
                                                  │ External Services    │
                                                  └──────────────────────┘
```

* **Ports & Adapters (Hexagonal)** – decouple core logic from Solana/Web APIs.
* **Command pattern** – each `/scan` invocation spawns an async command object.
* **Repository pattern** – optional Mongo caches via `TokenRepo`, `WalletRepo`.
* **Circuit Breaker** – wrap each adapter with breaker to short-circuit failing endpoints.
* **Retry with Back-off** – global `@retry_async` decorator using `tenacity`.
* **DI Container** – simple provider module that wires singletons (clients, repos).

## Async Flow
1. Telegram handler receives `/scan <mint>` ⇒ validates `.44()`.
2. Dispatches `ScanService.scan_token(mint)` coroutine.
3. `ScanService` gathers concurrently:
   * `MetadataService` (Helius asset endpoint)
   * `HolderService` (holders list)
   * `LiquidityService` (Jupiter & DexScreener)
4. Results fed into `RiskEngine` which outputs `RiskReport` dataclass.
5. `TelegramFormatter` converts report → markdown v2.

## Error Handling Strategy
* Wrap each external call in `@catch_and_log` → returns `Result[T, Error]`.
* Map common exceptions to user-friendly messages (`HeliusRateLimitError`, `InvalidMintError`).

## Observability
* Structured logs (`json`) per request id (`uuid4` propagated via contextvar).
* Metrics exported via `/metrics` Prometheus on optional FastAPI route.

## Deployment Pattern
* Docker container, run `uvicorn telegram_webhook:app --factory` or long-poll mode.

## Test Pyramid
* **Unit** – services & adapters mocked (80% coverage).
* **Integration** – hit Helius sandbox & public RPC in CI.
* **E2E** – docker-compose with local Telegram test bot. 