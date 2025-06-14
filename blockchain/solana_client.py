"""
Solana client stub for blockchain interactions.
This is a placeholder that provides basic Solana functionality.
"""
import logging
import requests
import os
import datetime
from typing import Dict, List, Any, Optional, Union
from dotenv import load_dotenv

# Ensure environment variables (HELIUS_API_KEY etc.) are loaded before anything else
load_dotenv()

logger = logging.getLogger(__name__)

class SolanaClientError(Exception):
    """Base exception for Solana client errors."""
    pass

class RateLimitExceededError(SolanaClientError):
    """Exception raised when RPC rate limit is exceeded."""
    pass

class SolanaAPIClient:
    """Stub client for interacting with Solana blockchain."""
    
    def __init__(self):
        """Initialize the Solana API client with Helius-keyed RPC or public fallback."""
        api_key = os.getenv("HELIUS_API_KEY", "")
        env_rpc = os.getenv("HELIUS_RPC_URL")

        # If HELIUS_RPC_URL set but missing api-key query param, append it (if we have a key)
        if env_rpc and api_key and "api-key" not in env_rpc:
            env_rpc = env_rpc.rstrip("/?") + f"/?api-key={api_key}"

        if env_rpc:
            self.rpc_url = env_rpc
        else:
            # Build default helius keyed endpoint or fallback to Solana public RPC
            if api_key:
                self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={api_key}"
            else:
                # Allow comma-separated list in RPC_URLS for rotation later
                self.rpc_url = os.getenv("RPC_URLS", "https://api.mainnet-beta.solana.com").split(",")[0]

        # ---------------- NEW: build ordered RPC candidate list for fail-over --------------
        # Priority: explicit HELIUS_RPC_URL → other URLs from RPC_URLS (if any) → public node
        rpc_candidates = []
        if env_rpc:
            rpc_candidates.append(env_rpc)
        # Append additional URLs from RPC_URLS env (may include the public endpoint)
        for u in os.getenv("RPC_URLS", "https://api.mainnet-beta.solana.com").split(","):
            u = u.strip()
            if u and u not in rpc_candidates:
                rpc_candidates.append(u)
        self._rpc_candidates = rpc_candidates or [self.rpc_url]
        # ----------------------------------------------------------------------------------

    def _post(self, method: str, params: list) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        last_err = None
        for url in self._rpc_candidates:
            try:
                resp = requests.post(url, json=payload, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if "error" in data and data["error"]:
                    raise SolanaClientError(data["error"])
                # Persist the working URL for subsequent calls
                self.rpc_url = url
                return data["result"]
            except Exception as e:
                logger.warning("RPC %s failed on %s → %s", method, url, e)
                last_err = e
                continue  # try next candidate
        # All tried and failed
        logger.error("Solana RPC %s failed on all candidates", method)
        raise SolanaClientError(str(last_err))

    def get_account_info(self, address: str) -> Optional[Dict[str, Any]]:
        try:
            result = self._post("getAccountInfo", [address, {"encoding": "jsonParsed"}])
            return result.get("value")
        except Exception as e:
            logger.error(f"Failed to get account info for {address}: {e}")
            return None

    def get_token_supply(self, token_address: str) -> Optional[int]:
        try:
            result = self._post("getTokenSupply", [token_address])
            return int(result["value"]["amount"])
        except Exception as e:
            logger.error(f"Failed to get token supply for {token_address}: {e}")
            return None

    def get_token_accounts_by_owner(self, owner_address: str, token_address: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            params = [owner_address, {"mint": token_address}, {"encoding": "jsonParsed"}]
            result = self._post("getTokenAccountsByOwner", params)
            return result.get("value", [])
        except Exception as e:
            logger.error(f"Failed to get token accounts by owner for {owner_address}: {e}")
            return []
    
    def get_token_metadata(self, address: str) -> Optional[Dict[str, Any]]:
        # Solana does not have a direct RPC for metadata; this is usually fetched from Metaplex or Helius
        # For now, return None or use Helius as a fallback in the analyzer
        logger.info(f"No direct RPC for token metadata for {address}")
        return None

    def get_recent_transactions(self, address: str, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            result = self._post("getSignaturesForAddress", [address, {"limit": limit}])
            return result
        except Exception as e:
            logger.error(f"Failed to get recent transactions for {address}: {e}")
            return []

    def get_token_holders(self, token_address: str, limit: int = 20) -> list:
        """Fetch token holders using Solana RPC getTokenLargestAccounts."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenLargestAccounts",
            "params": [token_address]
        }
        try:
            resp = requests.post(self.rpc_url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            accounts = data.get("result", {}).get("value", [])
            holders = []
            for acc in accounts[:limit]:
                holders.append({
                    "address": acc.get("address"),
                    "amount": acc.get("amount"),
                    "decimals": acc.get("decimals"),
                    "uiAmount": acc.get("uiAmount"),
                })
            return holders
        except Exception as e:
            logger.error(f"Solana RPC get_token_holders failed for {token_address}: {e}")
            return []

    def get_dex_info(self, token_address: str) -> dict:
        """Placeholder for DEX info; not implemented for SolanaAPIClient."""
        logger.warning("get_dex_info not implemented for SolanaAPIClient")
        return {}

    # ------------------------------------------------------------------
    # Extra helper methods expected by higher-level analyzers
    # ------------------------------------------------------------------

    def get_token_info(self, token_address: str) -> dict:
        """Retrieve token metadata using the DataPipeline fallbacks (sync)."""
        from src.services.data_pipeline import data_pipeline  # local import to avoid circular

        logger.debug(f"SolanaClient: fetching token metadata for {token_address}")

        try:
            meta = data_pipeline.get_token_metadata(token_address) or {}

            # Ensure mandatory fields exist
            meta.setdefault("mint", token_address)

            # Enrich with supply/decimals if missing
            if "supply" not in meta or meta.get("supply") in (0, None):
                try:
                    supply_info = data_pipeline.get_token_supply(token_address) or {}
                    if supply_info:
                        meta["supply"] = supply_info.get("supply") or supply_info.get("uiAmount", 0)
                        meta.setdefault("decimals", supply_info.get("decimals"))
                except Exception as _e:
                    logger.debug("Unable to fetch supply for %s: %s", token_address, _e)

            class _AwaitableWrapper:
                __slots__ = ("_val",)

                def __init__(self, val):
                    self._val = val

                # Awaiting returns the underlying dict
                def __await__(self):
                    if False:
                        yield self._val
                    return self._val

                def __getattr__(self, item):
                    return getattr(self._val, item)

                def __getitem__(self, item):
                    return self._val[item]

                def get(self, key, default=None):
                    return self._val.get(key, default)

                def items(self):
                    return self._val.items()

                def __repr__(self):
                    return repr(self._val)

            return _AwaitableWrapper(meta)
        except Exception as e:
            logger.error(f"Failed to fetch token metadata for {token_address}: {e}")
            return {"mint": token_address, "error": str(e)}

    def get_token_transfers(self, token_address: str, limit: int = 100, days: int = 7, **kwargs):
        """Fetch recent token transfers via Helius Enhanced RPC (sync)."""
        import requests, datetime, os

        logger.debug(
            f"SolanaClient: fetching token transfers for {token_address} limit={limit} days={days}"
        )

        # Accept full mint addresses including 'pump' suffix; do not trim.

        api_key = os.getenv("HELIUS_API_KEY", "")
        rpc_url = os.getenv("HELIUS_RPC_URL")
        if rpc_url and api_key and "api-key" not in rpc_url:
            rpc_url = rpc_url.rstrip("/?") + f"/?api-key={api_key}"
        if not rpc_url:
            rpc_url = f"https://mainnet.helius-rpc.com/?api-key={api_key}" if api_key else os.getenv("RPC_URLS", "https://api.mainnet-beta.solana.com").split(",")[0]

        transfers: list = []
        try:
            params = {
                "limit": min(limit, 100),  # Helius cap is 100
                "type": "TRANSFER",  # keep explicit so we skip unrelated txs
            }
            if api_key:
                params["api-key"] = api_key

            # ---------------- NEW HELIUS TOKEN TRANSFER LOGIC ----------------
            # Helius retired the "/tokens/{mint}/transfers" route (returns 404).
            # The recommended way now is to pull recent transactions for the *mint address*
            # via the Enhanced-Transactions API and then extract the tokenTransfers list.
            # -----------------------------------------------------------------
            rest_base = "https://api.helius.xyz/v0"
            url = f"{rest_base}/addresses/{token_address}/transactions"

            try:
                resp = requests.get(url, params=params, timeout=25)
                if resp.ok:
                    txs = resp.json() or []
                    # Flatten tokenTransfers belonging to *this* mint.
                    for tx in txs:
                        for tr in tx.get("tokenTransfers", []):
                            if tr.get("mint") == token_address:
                                transfers.append(tr)
                else:
                    # Log body for diagnostics then attempt recovery.
                    logger.warning("Enhanced-Tx HTTP %s for %s : %s", resp.status_code, token_address, resp.text[:120])

                    # Some errors (e.g. 400 for unsupported query) can self-heal by retrying without the `type` filter.
                    if params.get("type"):
                        params.pop("type")
                        try:
                            retry = requests.get(url, params=params, timeout=25)
                            if retry.ok:
                                txs = retry.json() or []
                                for tx in txs:
                                    for tr in tx.get("tokenTransfers", []):
                                        if tr.get("mint") == token_address:
                                            transfers.append(tr)
                            else:
                                logger.info("Enhanced-Tx retry still failed (%s) – using RPC fallback", retry.status_code)
                                transfers = self._fallback_transfers_rpc(token_address, limit)
                        except Exception as e2:
                            logger.error("Enhanced-Tx retry error %s – using RPC fallback", e2)
                            transfers = self._fallback_transfers_rpc(token_address, limit)
                    else:
                        # On 404 or other error, fall back to RPC method
                        logger.info("Helius Enhanced-Transactions %s for %s – falling back to RPC signatures", resp.status_code, token_address)
                        transfers = self._fallback_transfers_rpc(token_address, limit)
            except Exception as e:
                logger.error(f"Error fetching token transfers for {token_address}: {e}")
                transfers = self._fallback_transfers_rpc(token_address, limit)
            # -----------------------------------------------------------------

        except Exception as e:
            logger.error(f"Error fetching token transfers for {token_address}: {e}")

        class _AwaitableWrapper:
            __slots__ = ("_val",)

            def __init__(self, val):
                self._val = val

            def __await__(self):
                if False:
                    yield self._val
                return self._val

            def __iter__(self):
                return iter(self._val)

            def __len__(self):
                return len(self._val)

            def __repr__(self):
                return repr(self._val)

        return _AwaitableWrapper(transfers)

    # ------------------------------------------------------------------
    # SPL helper – largest accounts
    # ------------------------------------------------------------------

    def get_token_largest_accounts(self, token_address: str, limit: int = 20):
        """Return dummy largest account list (awaitable)."""
        logger.debug("Fetching getTokenLargestAccounts for %s", token_address)

        import requests, os, json

        api_key = os.getenv("HELIUS_API_KEY", "")
        rpc_url = os.getenv("HELIUS_RPC_URL")
        if rpc_url and api_key and "api-key" not in rpc_url:
            rpc_url = rpc_url.rstrip("/?") + f"/?api-key={api_key}"
        if not rpc_url:
            rpc_url = f"https://mainnet.helius-rpc.com/?api-key={api_key}" if api_key else os.getenv("RPC_URLS", "https://api.mainnet-beta.solana.com").split(",")[0]

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenLargestAccounts",
            "params": [token_address],
        }

        holders = {"value": []}
        try:
            resp = requests.post(rpc_url, json=payload, timeout=10)
            if resp.ok:
                holders = resp.json().get("result", {})
            else:
                logger.warning("getTokenLargestAccounts failed %s: %s", resp.status_code, resp.text[:120])
        except Exception as e:
            logger.warning("RPC getTokenLargestAccounts error for %s: %s", token_address, e)

        class _AwaitableWrapper:
            __slots__ = ("_val",)
            def __init__(self, val):
                self._val = val
            def __await__(self):
                if False:
                    yield self._val
                return self._val
            def __getitem__(self, item):
                return self._val[item]
            def get(self, key, default=None):
                return self._val.get(key, default)
            def __repr__(self):
                return repr(self._val)

        return _AwaitableWrapper(holders)

    # ------------------------------------------------------------------
    # Minimal helpers required by ownership & dev analyzers
    # ------------------------------------------------------------------

    def get_token_transactions(self, token_address: str, start_date=None, end_date=None, limit: int = 100, **kwargs):
        """Return dummy token transactions list (awaitable)."""
        logger.info(
            f"SolanaClient stub: get_token_transactions called for {token_address} (limit={limit})"
        )
        return self.get_token_transfers(token_address, limit=limit)

    def get_token_accounts(self, token_address: str, **kwargs):
        """Return dummy list of token-related program accounts (awaitable)."""
        logger.info(f"SolanaClient stub: get_token_accounts called for {token_address}")
        # empty list
        class _AwaitableWrapper:
            __slots__ = ("_val",)
            def __init__(self, val):
                self._val = val
            def __await__(self):
                if False:
                    yield self._val
                return self._val
            def __iter__(self):
                return iter(self._val)
            def __len__(self):
                return len(self._val)
        return _AwaitableWrapper([])

    def get_token_authorities(self, token_address: str):
        """Return dummy list of authorities (awaitable)."""
        logger.info(f"SolanaClient stub: get_token_authorities called for {token_address}")

        class _AwaitableWrapper:
            """Simple wrapper that can be awaited or used synchronously."""
            __slots__ = ("_val",)

            def __init__(self, val):
                self._val = val

            # Allow `await wrapper` to return the underlying value
            def __await__(self):
                if False:
                    yield self._val
                return self._val

            # Delegate attribute access to the wrapped value so calls like
            # `wrapper.items()` or `wrapper.get()` behave as expected when the
            # caller forgets to await.
            def __getattr__(self, item):
                return getattr(self._val, item)

            def __iter__(self):
                return iter(self._val)

            def __repr__(self):
                return repr(self._val)

        # Return an *empty dict* instead of a list so that callers that expect
        # a mapping (and call `.items()` on it) do not raise exceptions.
        return _AwaitableWrapper({})

    # ------------------------------------------------------------------
    # Additional helpers referenced by higher-level analyzers & trackers
    # ------------------------------------------------------------------

    def get_program_info(self, program_id: str):
        """Return dummy program information (awaitable)."""
        logger.info(f"SolanaClient stub: get_program_info called for {program_id}")

        data = {
            "program_id": program_id,
            "deployer": None,  # unknown in stub
            "upgrade_authority": None,
        }

        class _AwaitableWrapper:
            __slots__ = ("_val",)
            def __init__(self, val):
                self._val = val
            def __await__(self):
                if False:
                    yield self._val
                return self._val
            def __getattr__(self, item):
                return getattr(self._val, item)
            def __repr__(self):
                return repr(self._val)

        return _AwaitableWrapper(data)

    def get_program_updates(self, program_id: str, start_date=None, end_date=None):
        """Return dummy list of program update events (awaitable)."""
        logger.info(
            f"SolanaClient stub: get_program_updates called for {program_id} (start_date={start_date}, end_date={end_date})"
        )

        class _AwaitableWrapper:
            __slots__ = ("_val",)
            def __init__(self, val):
                self._val = val
            def __await__(self):
                if False:
                    yield self._val
                return self._val
            def __iter__(self):
                return iter(self._val)
            def __repr__(self):
                return repr(self._val)

            def __getattr__(self, item):
                return getattr(self._val, item)

        return _AwaitableWrapper([])

    def get_token_balance(self, token_address: str, wallet_address: str):
        """Return dummy token balance (awaitable)."""
        logger.info(
            f"SolanaClient stub: get_token_balance called for {token_address} / wallet {wallet_address}"
        )

        class _AwaitableNumber(int):
            """Integer that can also be awaited for async compatibility."""

            def __new__(cls, val):
                return int.__new__(cls, val)

            def __await__(self):
                if False:
                    yield self
                return self

        return _AwaitableNumber(0)  # zero balance by default

    def get_wallet_transactions(self, wallet_address: str, days: int = 30, limit: int = 100):
        """Return dummy wallet transactions (awaitable)."""
        logger.info(
            f"SolanaClient stub: get_wallet_transactions called for {wallet_address} (days={days}, limit={limit})"
        )

        class _AwaitableWrapper:
            __slots__ = ("_val",)
            def __init__(self, val):
                self._val = val
            def __await__(self):
                if False:
                    yield self._val
                return self._val
            def __iter__(self):
                return iter(self._val)
            def __len__(self):
                return len(self._val)
            def __repr__(self):
                return repr(self._val)
            def __getattr__(self, item):
                return getattr(self._val, item)

        return _AwaitableWrapper([])

    async def is_program(self, address: str) -> bool:
        """Stub to determine if an address is a program account (always False)."""
        logger.info(f"SolanaClient stub: is_program called for {address}")
        return False

    # ------------------------------------------------------------------
    # Internal fallback helpers
    # ------------------------------------------------------------------

    def _fallback_transfers_rpc(self, token_address: str, limit: int = 100):
        """Use getConfirmedSignaturesForAddress2 RPC when Helius REST is unavailable."""
        import requests, os, json

        api_key = os.getenv("HELIUS_API_KEY", "")
        rpc_url = os.getenv("HELIUS_RPC_URL")
        if rpc_url and api_key and "api-key" not in rpc_url:
            rpc_url = rpc_url.rstrip("/?") + f"/?api-key={api_key}"
        if not rpc_url:
            rpc_url = f"https://mainnet.helius-rpc.com/?api-key={api_key}" if api_key else os.getenv("RPC_URLS", "https://api.mainnet-beta.solana.com").split(",")[0]

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getConfirmedSignaturesForAddress2",
            "params": [token_address, {"limit": limit}],
        }
        try:
            resp = requests.post(rpc_url, json=payload, timeout=10)
            resp.raise_for_status()
            sigs = [s["signature"] for s in resp.json().get("result", [])]
            # basic structure so fee analyzer can count len()
            return [{"signature": s} for s in sigs]
        except Exception as e:
            logger.warning("RPC fallback signatures failed for %s: %s", token_address, e)
            return []

# Initialize client
solana_client = SolanaAPIClient()

# Add a stub SolanaClient class for compatibility
class SolanaClient(SolanaAPIClient):
    pass
