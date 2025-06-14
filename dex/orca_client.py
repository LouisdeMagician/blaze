"""
Orca API client for liquidity data.
Provides functionality to interact with Orca DEX on Solana.
"""
import logging
import time
import json
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple
import aiohttp
from datetime import datetime

from config.config import config
from src.utils.circuit_breaker import circuit_breaker
from src.blockchain.solana_client import solana_client, SolanaClientError

logger = logging.getLogger(__name__)

# Custom exceptions
class OrcaClientError(Exception):
    """Base exception for Orca client errors."""
    pass

class OrcaRateLimitError(OrcaClientError):
    """Exception raised when rate limit is exceeded."""
    pass

class OrcaClient:
    """Client for interacting with Orca DEX API and on-chain data."""
    
    # Orca program IDs
    ORCA_WHIRLPOOL_PROGRAM_ID = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"
    ORCA_V2_PROGRAM_ID = "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP"
    
    def __init__(self):
        """Initialize the Orca client."""
        self.api_url = config.get("dex", {}).get("orca", {}).get("api_url", "https://api.orca.so")
        self.session = None
        self.request_count = 0
        self.last_reset = time.time()
        self.rate_limit = 60  # Default rate limit per minute
        self.max_retries = 3
        self.retry_delay = 1.0
        self.initialized = False
        
        # Pool cache
        self.pools_cache = {}
        self.whirlpools_cache = {}
        self.pools_last_updated = 0
        self.pools_cache_ttl = 300  # 5 minutes
    
    async def initialize(self):
        """Initialize the client session."""
        if not self.initialized:
            self.session = aiohttp.ClientSession()
            self.initialized = True
            logger.info("Orca client initialized")
    
    async def close(self):
        """Close the client session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.initialized = False
            logger.info("Orca client closed")
    
    @circuit_breaker("orca_api", failure_threshold=5, timeout=60.0)
    async def _make_request(self, endpoint: str, method: str = "GET", 
                            params: Dict[str, Any] = None, data: Dict = None) -> Dict[str, Any]:
        """
        Make a request to the Orca API.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST)
            params: URL parameters
            data: Request body for POST
            
        Returns:
            Dict: Response data
            
        Raises:
            OrcaClientError: On request failure
            OrcaRateLimitError: When rate limited
        """
        if not self.initialized:
            await self.initialize()
        
        # Check rate limiting
        now = time.time()
        if now - self.last_reset > 60:
            self.request_count = 0
            self.last_reset = now
        
        self.request_count += 1
        
        # Apply rate limiting
        if self.request_count > self.rate_limit:
            delay = 60 - (now - self.last_reset)
            if delay > 0:
                raise OrcaRateLimitError(f"Rate limit exceeded. Try again in {delay:.2f} seconds")
        
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        headers = {"Content-Type": "application/json"}
        
        retries = 0
        while retries <= self.max_retries:
            try:
                if method.upper() == "GET":
                    async with self.session.get(url, params=params, headers=headers) as response:
                        if response.status == 429:  # Rate limited
                            retries += 1
                            delay = self.retry_delay * (2 ** retries)
                            logger.warning(f"Rate limited by Orca API. Retrying in {delay:.2f}s")
                            await asyncio.sleep(delay)
                            continue
                        
                        response.raise_for_status()
                        return await response.json()
                        
                elif method.upper() == "POST":
                    async with self.session.post(url, params=params, json=data, headers=headers) as response:
                        if response.status == 429:  # Rate limited
                            retries += 1
                            delay = self.retry_delay * (2 ** retries)
                            logger.warning(f"Rate limited by Orca API. Retrying in {delay:.2f}s")
                            await asyncio.sleep(delay)
                            continue
                        
                        response.raise_for_status()
                        return await response.json()
                
                else:
                    raise OrcaClientError(f"Unsupported HTTP method: {method}")
                    
            except aiohttp.ClientResponseError as e:
                if e.status == 429:  # Rate limited
                    retries += 1
                    delay = self.retry_delay * (2 ** retries)
                    logger.warning(f"Rate limited by Orca API. Retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                    continue
                
                logger.error(f"Orca API error: {e}")
                raise OrcaClientError(f"API error: {e}")
                
            except aiohttp.ClientError as e:
                retries += 1
                if retries <= self.max_retries:
                    delay = self.retry_delay * (2 ** retries)
                    logger.warning(f"Orca API request failed: {e}. Retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                    continue
                
                logger.error(f"Orca API request failed after {retries} retries: {e}")
                raise OrcaClientError(f"Request failed: {e}")
                
        raise OrcaClientError(f"Failed after {self.max_retries} retries")
    
    async def get_all_whirlpools(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get all Orca Whirlpools (concentrated liquidity).
        
        Args:
            force_refresh: Force refresh the pools cache
            
        Returns:
            List[Dict]: List of Whirlpools
        """
        now = time.time()
        
        # Check if we can use cached data
        if (not force_refresh and 
            self.whirlpools_cache and 
            now - self.pools_last_updated < self.pools_cache_ttl):
            return self.whirlpools_cache
        
        try:
            # Orca doesn't have a direct API for this, so we need to query the on-chain data
            # For now, we'll use a simplified approach with mock data
            # In a real implementation, we'd use Solana RPC calls to get pool data
            
            # Mock data for now - would be replaced with actual implementation
            whirlpools = [
                {
                    "id": "whirlpool1",
                    "token_a": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                    "token_b": "So11111111111111111111111111111111111111112",  # Wrapped SOL
                    "token_a_name": "USDC",
                    "token_b_name": "SOL",
                    "liquidity": 8000000,
                    "volume_24h": 1500000,
                    "fee_rate": 0.003,
                    "price": 22.4,
                    "tick_spacing": 64,
                    "program_id": self.ORCA_WHIRLPOOL_PROGRAM_ID
                },
                {
                    "id": "whirlpool2",
                    "token_a": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                    "token_b": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
                    "token_a_name": "USDC",
                    "token_b_name": "USDT",
                    "liquidity": 12000000,
                    "volume_24h": 5000000,
                    "fee_rate": 0.0005,
                    "price": 1.002,
                    "tick_spacing": 1,
                    "program_id": self.ORCA_WHIRLPOOL_PROGRAM_ID
                }
            ]
            
            # Update cache
            self.whirlpools_cache = whirlpools
            self.pools_last_updated = now
            
            return whirlpools
            
        except Exception as e:
            logger.error(f"Error getting Orca whirlpools: {e}", exc_info=True)
            
            # If we have cached data, return it even if expired
            if self.whirlpools_cache:
                logger.warning("Returning stale whirlpool data due to error")
                return self.whirlpools_cache
                
            raise OrcaClientError(f"Failed to get whirlpools: {e}")
    
    async def get_all_pools(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get all Orca v2 pools (non-concentrated liquidity).
        
        Args:
            force_refresh: Force refresh the pools cache
            
        Returns:
            List[Dict]: List of pools
        """
        now = time.time()
        
        # Check if we can use cached data
        if (not force_refresh and 
            self.pools_cache and 
            now - self.pools_last_updated < self.pools_cache_ttl):
            return self.pools_cache
        
        try:
            # Mock data for v2 pools
            pools = [
                {
                    "id": "poolv2_1",
                    "token_a": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                    "token_b": "So11111111111111111111111111111111111111112",  # Wrapped SOL
                    "lp_token": "lp_token_address_orca1",
                    "token_a_name": "USDC",
                    "token_b_name": "SOL",
                    "liquidity": 2000000,
                    "volume_24h": 400000,
                    "fee_rate": 0.0025,
                    "price": 22.5,
                    "program_id": self.ORCA_V2_PROGRAM_ID
                },
                {
                    "id": "poolv2_2",
                    "token_a": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                    "token_b": "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",  # mSOL
                    "lp_token": "lp_token_address_orca2",
                    "token_a_name": "USDC",
                    "token_b_name": "mSOL",
                    "liquidity": 1500000,
                    "volume_24h": 250000,
                    "fee_rate": 0.0025,
                    "price": 23.0,
                    "program_id": self.ORCA_V2_PROGRAM_ID
                }
            ]
            
            # Update cache
            self.pools_cache = pools
            self.pools_last_updated = now
            
            return pools
            
        except Exception as e:
            logger.error(f"Error getting Orca v2 pools: {e}", exc_info=True)
            
            # If we have cached data, return it even if expired
            if self.pools_cache:
                logger.warning("Returning stale pool data due to error")
                return self.pools_cache
                
            raise OrcaClientError(f"Failed to get pools: {e}")
    
    async def find_pools_for_token(self, token_address: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Find all pools (both v2 and whirlpools) for a specific token.
        
        Args:
            token_address: Token mint address
            
        Returns:
            Dict: Dictionary with 'v2_pools' and 'whirlpools' lists
        """
        try:
            v2_pools = await self.get_all_pools()
            whirlpools = await self.get_all_whirlpools()
            
            # Find pools where the token is either token A or token B
            token_v2_pools = [
                pool for pool in v2_pools
                if pool["token_a"] == token_address or pool["token_b"] == token_address
            ]
            
            token_whirlpools = [
                pool for pool in whirlpools
                if pool["token_a"] == token_address or pool["token_b"] == token_address
            ]
            
            return {
                "v2_pools": token_v2_pools,
                "whirlpools": token_whirlpools
            }
            
        except Exception as e:
            logger.error(f"Error finding pools for token {token_address}: {e}", exc_info=True)
            return {
                "v2_pools": [],
                "whirlpools": []
            }
    
    async def calculate_price_impact(self, pool_id: str, token_address: str, amount_usd: float, 
                                  pool_type: str = "whirlpool") -> Dict[str, Any]:
        """
        Calculate price impact for a trade in a specific pool.
        
        Args:
            pool_id: Pool ID
            token_address: Token address being traded
            amount_usd: Trade amount in USD
            pool_type: 'whirlpool' or 'v2'
            
        Returns:
            Dict: Price impact information
        """
        try:
            # Get the pool data based on type
            if pool_type == "whirlpool":
                pools = await self.get_all_whirlpools()
                pool = next((p for p in pools if p["id"] == pool_id), None)
            else:
                pools = await self.get_all_pools()
                pool = next((p for p in pools if p["id"] == pool_id), None)
            
            if not pool:
                return {
                    "price_impact_percent": 100,
                    "error": f"Pool not found: {pool_id}"
                }
            
            # Different impact calculations for different pool types
            if pool_type == "whirlpool":
                # Whirlpools have concentrated liquidity, so impact depends on price range
                # This is a simplified model
                liquidity = pool["liquidity"]
                if liquidity > 0:
                    # Concentrated liquidity typically has lower impact for same TVL
                    impact_percent = min((amount_usd / (liquidity * 2)) * 100, 100)
                else:
                    impact_percent = 100
            else:
                # Regular v2 pools follow standard AMM curve
                liquidity = pool["liquidity"]
                if liquidity > 0:
                    impact_percent = min((amount_usd / liquidity) * 100, 100)
                else:
                    impact_percent = 100
            
            return {
                "pool_id": pool_id,
                "token_address": token_address,
                "amount_usd": amount_usd,
                "liquidity_usd": pool["liquidity"],
                "pool_type": pool_type,
                "price_impact_percent": impact_percent,
                "slippage_percent": impact_percent * 1.5  # Estimate slippage as slightly higher than impact
            }
            
        except Exception as e:
            logger.error(f"Error calculating price impact for pool {pool_id}: {e}", exc_info=True)
            return {
                "price_impact_percent": 100,
                "error": str(e)
            }
    
    async def get_token_liquidity_data(self, token_address: str) -> Dict[str, Any]:
        """
        Get comprehensive liquidity data for a token across all Orca pools.
        
        Args:
            token_address: Token mint address
            
        Returns:
            Dict: Token liquidity data
        """
        try:
            pools = await self.find_pools_for_token(token_address)
            v2_pools = pools["v2_pools"]
            whirlpools = pools["whirlpools"]
            
            all_pools = v2_pools + whirlpools
            
            if not all_pools:
                return {
                    "token_address": token_address,
                    "total_liquidity_usd": 0,
                    "total_volume_24h": 0,
                    "v2_pools": [],
                    "whirlpools": [],
                    "last_updated": int(time.time()),
                    "source": "orca"
                }
            
            # Calculate total liquidity and volume
            total_v2_liquidity = sum(pool["liquidity"] for pool in v2_pools)
            total_whirlpool_liquidity = sum(pool["liquidity"] for pool in whirlpools)
            total_liquidity = total_v2_liquidity + total_whirlpool_liquidity
            
            total_v2_volume = sum(pool["volume_24h"] for pool in v2_pools)
            total_whirlpool_volume = sum(pool["volume_24h"] for pool in whirlpools)
            total_volume = total_v2_volume + total_whirlpool_volume
            
            # Calculate price impact for different trade sizes
            impact_samples = []
            
            # Use the largest pool for samples
            if all_pools:
                largest_pool = max(all_pools, key=lambda p: p["liquidity"])
                pool_type = "whirlpool" if largest_pool.get("tick_spacing") is not None else "v2"
                
                for amount in [100, 1000, 10000, 100000]:
                    impact = await self.calculate_price_impact(
                        largest_pool["id"], 
                        token_address, 
                        amount, 
                        pool_type
                    )
                    impact_samples.append({
                        "amount_usd": amount,
                        "price_impact_percent": impact["price_impact_percent"],
                        "slippage_percent": impact.get("slippage_percent", impact["price_impact_percent"] * 1.5)
                    })
            
            # Analyze liquidity concentration
            if total_liquidity > 0:
                # Find largest pool by liquidity
                if all_pools:
                    largest_pool_liquidity = max(pool["liquidity"] for pool in all_pools)
                    concentration = largest_pool_liquidity / total_liquidity
                else:
                    concentration = 0
            else:
                concentration = 0
            
            # Check for concentrated liquidity
            concentrated_liquidity_ratio = 0
            if total_liquidity > 0:
                concentrated_liquidity_ratio = total_whirlpool_liquidity / total_liquidity
            
            return {
                "token_address": token_address,
                "total_liquidity_usd": total_liquidity,
                "total_volume_24h": total_volume,
                "v2_pool_count": len(v2_pools),
                "whirlpool_count": len(whirlpools),
                "total_pool_count": len(all_pools),
                "concentration_ratio": concentration,
                "concentrated_liquidity_ratio": concentrated_liquidity_ratio,
                "impact_samples": impact_samples,
                "v2_pools": v2_pools,
                "whirlpools": whirlpools,
                "last_updated": int(time.time()),
                "source": "orca"
            }
            
        except Exception as e:
            logger.error(f"Error getting token liquidity data for {token_address}: {e}", exc_info=True)
            return {
                "token_address": token_address,
                "total_liquidity_usd": 0,
                "total_volume_24h": 0,
                "v2_pools": [],
                "whirlpools": [],
                "error": str(e),
                "last_updated": int(time.time()),
                "source": "orca"
            }


# Initialize the client
orca_client = OrcaClient() 