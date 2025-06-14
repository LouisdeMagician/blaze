"""
Helius API client stub for enhanced Solana data.
This is a placeholder that provides basic Helius API functionality.
"""
import logging
import os
import requests
from typing import Dict, List, Any, Optional
import base64
import struct
from solana.publickey import PublicKey
import datetime

logger = logging.getLogger(__name__)

class HeliusClientError(Exception):
    """Base exception for Helius client errors."""
    pass

class HeliusClient:
    """Real client for the Helius API (Solana)."""
    
    def __init__(self):
        """Initialize the Helius client stub."""
        self.api_key = os.environ.get("HELIUS_API_KEY", "")
        self.base_url = "https://api.helius.xyz/v0"
        if not self.api_key:
            logger.warning("HELIUS_API_KEY not set in environment!")
        self.session = requests.Session()
        self.initialized = False
        logger.info("Initialized Helius client")
    
    def initialize(self):
        """Initialize the client."""
        self.initialized = True
        logger.info("Helius client initialized")
        
    def close(self):
        """Close the client."""
        self.initialized = False
        self.session.close()
        logger.info("Helius client closed")
    
    def check_health(self):
        """Check if Helius API is available."""
        return bool(self.api_key)
    
    def _get(self, endpoint: str, params: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Helius API GET {endpoint} failed: {e}")
            raise HeliusClientError(str(e))
    
    def _post(self, endpoint: str, body: dict) -> Any:
        url = f"{self.base_url}{endpoint}?api-key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        try:
            resp = self.session.post(url, headers=headers, json=body, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Helius API POST {endpoint} failed: {e}")
            raise HeliusClientError(str(e))
    
    def get_token_data(self, token_address: str) -> dict:
        """Fetch SPL token metadata using the Helius /tokens/metadata endpoint."""
        try:
            body = {"mintAccounts": [token_address]}
            data = self._post("/tokens/metadata", body)
            if data and isinstance(data, list) and len(data) > 0:
                meta = data[0]
                # Normalize to flat dict
                return {
                    "address": token_address,
                    "name": meta.get("name", "Unknown"),
                    "symbol": meta.get("symbol", "UNKN"),
                    "decimals": meta.get("decimals", 0),
                    "supply": meta.get("supply", 0),
                    "verified": meta.get("verified", False),
                    "isProxy": meta.get("isProxy", False),
                    "audited": meta.get("audited", False),
                    "createdAt": meta.get("createdAt"),
                    "metadata": meta,
                }
            else:
                logger.warning(f"Helius API: No metadata found for {token_address}")
                return {}
        except Exception as e:
            logger.error(f"Helius API POST /tokens/metadata for {token_address} failed: {e}")
            return {}

    def get_token_holders(self, token_address: str, limit: int = 10) -> list:
        """Fetch token holders using Helius Enhanced RPC getTokenLargestAccounts."""
        url = f"https://mainnet.helius-rpc.com/?api-key={self.api_key}"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenLargestAccounts",
            "params": [token_address]
        }
        try:
            resp = self.session.post(url, json=payload, timeout=10)
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
            logger.error(f"Helius Enhanced RPC getTokenLargestAccounts failed for {token_address}: {e}")
            return []
    
    def get_token_price_data(self, token_address: str) -> Dict[str, Any]:
        """Get token price data from Helius."""
        try:
            data = self._get(f"/tokens/{token_address}/price")
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"Failed to get token price data for {token_address}: {e}")
            return {}
    
    def get_token_transfers(self, token_address: str, limit: int = 50, days: int = None):
        """Get token transfers – returns awaitable wrapper so callers may use ``await``."""
        try:
            # The legacy `/tokens/{mint}/transfers` route was removed (returns 404).
            # New approach: query the Enhanced-Transactions API for the mint address
            # and extract `tokenTransfers` entries for that mint.
            params = {
                "api-key": self.api_key,
                "type": "TRANSFER",
                "limit": min(limit, 100),
            }
            tx_url = f"{self.base_url}/addresses/{token_address}/transactions"
            raw = self.session.get(tx_url, params=params, timeout=25)
            txs = []
            if raw.ok:
                txs = raw.json() or []
            else:
                logger.warning("HeliusClient ETx HTTP %s for %s : %s", raw.status_code, token_address, raw.text[:120])
                if params.get("type"):
                    params.pop("type")
                    try:
                        retry = self.session.get(tx_url, params=params, timeout=25)
                        if retry.ok:
                            txs = retry.json() or []
                        else:
                            logger.info("HeliusClient retry still failed (%s)", retry.status_code)
                    except Exception as e2:
                        logger.error("HeliusClient retry error %s", e2)

            transfers: list = []
            for tx in txs:
                for tr in tx.get("tokenTransfers", []):
                    if tr.get("mint") == token_address:
                        transfers.append(tr)
        except Exception as e:
            logger.error(f"Failed to get token transfers for {token_address}: {e}")
            transfers = []

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

        return _AwaitableWrapper(transfers)
    
    def get_token_price_history(self, token_address: str, days=None, limit: int = 30) -> list:
        """Stub for price history; returns empty list and logs a warning. Accepts 'days' for compatibility."""
        logger.warning(f"get_token_price_history is not implemented for {token_address} (days={days}, limit={limit})")
        return []

    def get_token_volume_history(self, token_address: str, days=None, limit: int = 30) -> list:
        """Stub for volume history; returns empty list and logs a warning. Accepts 'days' for compatibility."""
        logger.warning(f"get_token_volume_history is not implemented for {token_address} (days={days}, limit={limit})")
        return []
    
    def get_raydium_pools(self) -> list:
        """Fetch all Raydium pools using Enhanced RPC."""
        RAYDIUM_PROGRAM_ID = "RVKd61ztZW9GdKzvKQC5bQKBdZLk6J7bTzjR4p6tS4k"
        try:
            pools = self.get_program_accounts(RAYDIUM_PROGRAM_ID)
            return pools
        except Exception as e:
            logger.error(f"Error fetching Raydium pools: {e}")
            return []

    def decode_raydium_pool(self, pool_account_data: str) -> dict:
        """Decode Raydium pool binary data using the official struct layout."""
        try:
            raw = base64.b64decode(pool_account_data)
            # Raydium AMM pool struct: base mint at 72, quote mint at 104, lp mint at 136 (all 32 bytes)
            base_mint = raw[72:104]
            quote_mint = raw[104:136]
            lp_mint = raw[136:168]
            # Convert to base58 addresses
            base_mint_b58 = str(PublicKey(base_mint))
            quote_mint_b58 = str(PublicKey(quote_mint))
            lp_mint_b58 = str(PublicKey(lp_mint))
            return {
                "base_mint": base_mint_b58,
                "quote_mint": quote_mint_b58,
                "lp_mint": lp_mint_b58
            }
        except Exception as e:
            logger.error(f"Error decoding Raydium pool: {e}")
            return {}

    def get_dex_info(self, token_address: str) -> dict:
        """Find Raydium pool for token and return DEX info (base58 match)."""
        try:
            pools = self.get_raydium_pools()
            for pool in pools:
                account_data = pool.get('account', {}).get('data', [None])[0]
                decoded = self.decode_raydium_pool(account_data)
                if not decoded:
                    continue
                if token_address in [decoded['base_mint'], decoded['quote_mint']]:
                    logger.info(f"Found Raydium pool for {token_address}: {pool.get('pubkey')}")
                    return {
                        "pool_pubkey": pool.get('pubkey'),
                        "base_mint": decoded['base_mint'],
                        "quote_mint": decoded['quote_mint'],
                        "lp_mint": decoded['lp_mint']
                    }
            logger.warning(f"No Raydium pool found for token {token_address}")
            return {}
        except Exception as e:
            logger.error(f"Error in get_dex_info for {token_address}: {e}")
            return {}

    def get_liquidity_lock_status(self, token_address: str) -> dict:
        """Check Raydium pool for liquidity lock status using Enhanced RPC."""
        try:
            dex_info = self.get_dex_info(token_address)
            lp_mint = dex_info.get('lp_mint')
            if not lp_mint:
                return {"status": "unknown", "reason": "No Raydium pool found for token"}
            mint_info = self._get_account_info(lp_mint)
            # Robustly decode freeze authority
            freeze_auth = None
            try:
                parsed = mint_info.get('result', {}).get('value', {}).get('data', {}).get('parsed', {})
                freeze_auth = parsed.get('info', {}).get('freezeAuthority')
            except Exception as e:
                logger.warning(f"Could not decode freeze authority for {lp_mint}: {e}")
            if freeze_auth:
                return {"status": "locked", "locker": freeze_auth, "lp_mint": lp_mint}
            else:
                return {"status": "unlocked", "lp_mint": lp_mint}
        except Exception as e:
            logger.error(f"Error in get_liquidity_lock_status for {token_address}: {e}")
            return {"status": "unknown", "error": str(e)}

    def get_fee_info(self, token_address: str) -> dict:
        """Analyze recent transfer transactions for fee/tax evidence (sample 30 txs)."""
        try:
            txs = self.get_historical_transactions(token_address, limit=30)
            for tx in txs:
                meta = tx.get('meta', {})
                pre_balances = meta.get('preTokenBalances', [])
                post_balances = meta.get('postTokenBalances', [])
                if pre_balances and post_balances:
                    for pre, post in zip(pre_balances, post_balances):
                        pre_amt = float(pre.get('uiTokenAmount', {}).get('uiAmount', 0))
                        post_amt = float(post.get('uiTokenAmount', {}).get('uiAmount', 0))
                        if pre_amt > post_amt:
                            fee_pct = round(100 * (pre_amt - post_amt) / pre_amt, 4) if pre_amt else 0
                            return {"fee_detected": True, "fee_percent": fee_pct, "pre": pre_amt, "post": post_amt, "signature": tx.get('transaction', {}).get('signatures', [None])[0]}
            return {"fee_detected": False, "details": "No fee/tax detected in recent transfers"}
        except Exception as e:
            logger.error(f"Error in get_fee_info for {token_address}: {e}")
            return {"fee_detected": "unknown", "error": str(e)}

    def get_program_accounts(self, program_id: str, filters: list = None) -> list:
        """Fetch program accounts using Helius Enhanced RPC or fallback to Solana RPC."""
        # Helius Enhanced RPC endpoint
        url = f"https://mainnet.helius-rpc.com/?api-key={self.api_key}"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getProgramAccounts",
            "params": [program_id, {"encoding": "jsonParsed", "filters": filters or []}]
        }
        try:
            resp = self.session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", [])
        except Exception as e:
            logger.error(f"Helius get_program_accounts failed for {program_id}: {e}")
            return []

    def get_historical_transactions(self, address: str, limit: int = 20) -> list:
        """Fetch historical transactions for an address using Helius Enhanced Transactions API."""
        url = f"{self.base_url}/addresses/{address}/transactions?api-key={self.api_key}"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Helius get_historical_transactions failed for {address}: {e}")
            return []

    def _get_account_info(self, address: str) -> dict:
        url = f"https://mainnet.helius-rpc.com/?api-key={self.api_key}"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [address, {"encoding": "jsonParsed"}]
        }
        try:
            resp = self.session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Error in _get_account_info for {address}: {e}")
            return {}

# Initialize client
helius_client = HeliusClient()
