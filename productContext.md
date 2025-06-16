# Product Context

### Problem Statement
Solana traders often struggle to quickly assess the rug-pull risk of newly launched tokens. Existing scanners either focus on Ethereum or provide shallow analysis. Manual due-diligence (reading Solscan, checking liquidity pools, scanning dev wallets) is time-consuming and error-prone.

### Solution Overview
BlazeAI Lite delivers a one-command Telegram experience that summarises on-chain risk vectors (mint authority, liquidity lock, holder distribution, tax, dev wallet history) within seconds.

### Target Users
* Retail Solana traders
* Crypto influencers/alpha callers
* Telegram community managers who vet tokens before promotion

### User Experience Goals
1. **One-click simplicity** – `/scan <mint>` returns a colour-coded verdict.
2. **Actionable insight** – highlight specific red flags and root causes.
3. **Speed** – response in <5 s for 95th percentile.
4. **Transparency** – link out to Solscan, DexScreener, liquidity lock, etc.
5. **Trust** – auditable open-source logic and publicly verifiable data sources.

### Success Metrics
* Daily active scans ≥ 500
* Average user rating ≥ 4.5/5
* False-negative rug-pulls ≤ 1 % 