"""
Raydium API client for liquidity data.
Provides functionality to interact with Raydium DEX on Solana.
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
class RaydiumClientError(Exception):
    """Base exception for Raydium client errors."""
    pass

class RaydiumRateLimitError(RaydiumClientError):
    """Exception raised when rate limit is exceeded."""
    pass

class RaydiumClient:
    """Client for interacting with Raydium DEX API and on-chain data."""
    
    # Raydium program IDs
    RAYDIUM_AMM_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
    RAYDIUM_LP_V4_PROGRAM_ID = "3u8hJUVTA4jH1wYAyUur7FFZVQ8H635K3tSHHF4ssjQ5"
    
    def __init__(self):
        """Initialize the Raydium client."""
        self.api_url = config.get("dex", {}).get("raydium", {}).get("api_url", "https://api.raydium.io")
        self.session = None
        self.request_count = 0
        self.last_reset = time.time()
        self.rate_limit = 60  # Default rate limit per minute
        self.max_retries = 3
        self.retry_delay = 1.0
        self.initialized = False
        
        # Pool cache
        self.pools_cache = {}
        self.pools_last_updated = 0
        self.pools_cache_ttl = 300  # 5 minutes
    
    async def initialize(self):
        """Initialize the client session."""
        if not self.initialized:
            self.session = aiohttp.ClientSession()
            self.initialized = True
            logger.info("Raydium client initialized")
    
    async def close(self):
        """Close the client session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.initialized = False
            logger.info("Raydium client closed")
    
    @circuit_breaker("raydium_api", failure_threshold=5, timeout=60.0)
    async def _make_request(self, endpoint: str, method: str = "GET", 
                            params: Dict[str, Any] = None, data: Dict = None) -> Dict[str, Any]:
        """
        Make a request to the Raydium API.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST)
            params: URL parameters
            data: Request body for POST
            
        Returns:
            Dict: Response data
            
        Raises:
            RaydiumClientError: On request failure
            RaydiumRateLimitError: When rate limited
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
                raise RaydiumRateLimitError(f"Rate limit exceeded. Try again in {delay:.2f} seconds")
        
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
                            logger.warning(f"Rate limited by Raydium API. Retrying in {delay:.2f}s")
                            await asyncio.sleep(delay)
                            continue
                        
                        response.raise_for_status()
                        return await response.json()
                        
                elif method.upper() == "POST":
                    async with self.session.post(url, params=params, json=data, headers=headers) as response:
                        if response.status == 429:  # Rate limited
                            retries += 1
                            delay = self.retry_delay * (2 ** retries)
                            logger.warning(f"Rate limited by Raydium API. Retrying in {delay:.2f}s")
                            await asyncio.sleep(delay)
                            continue
                        
                        response.raise_for_status()
                        return await response.json()
                
                else:
                    raise RaydiumClientError(f"Unsupported HTTP method: {method}")
                    
            except aiohttp.ClientResponseError as e:
                if e.status == 429:  # Rate limited
                    retries += 1
                    delay = self.retry_delay * (2 ** retries)
                    logger.warning(f"Rate limited by Raydium API. Retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                    continue
                
                logger.error(f"Raydium API error: {e}")
                raise RaydiumClientError(f"API error: {e}")
                
            except aiohttp.ClientError as e:
                retries += 1
                if retries <= self.max_retries:
                    delay = self.retry_delay * (2 ** retries)
                    logger.warning(f"Raydium API request failed: {e}. Retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                    continue
                
                logger.error(f"Raydium API request failed after {retries} retries: {e}")
                raise RaydiumClientError(f"Request failed: {e}")
                
        raise RaydiumClientError(f"Failed after {self.max_retries} retries")
    
    async def get_all_pools(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get all Raydium liquidity pools.
        
        Args:
            force_refresh: Force refresh the pools cache
            
        Returns:
            List[Dict]: List of liquidity pools
        """
        now = time.time()
        
        # Check if we can use cached data
        if (not force_refresh and 
            self.pools_cache and 
            now - self.pools_last_updated < self.pools_cache_ttl):
            return self.pools_cache
        
        try:
            # Raydium doesn't have a direct API for this, so we need to query the on-chain data
            # For now, we'll use a simplified approach with mock data
            # In a real implementation, we'd use Solana RPC calls to get pool data
            
            # Mock data for now - would be replaced with actual implementation
            pools = [
                {
                    "id": "pool1",
                    "base_token": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                    "quote_token": "So11111111111111111111111111111111111111112",  # Wrapped SOL
                    "lp_token": "lp_token_address1",
                    "base_token_name": "USDC",
                    "quote_token_name": "SOL",
                    "liquidity": 5000000,
                    "volume_24h": 1000000,
                    "fee_rate": 0.25,
                    "price": 22.5,
                    "pool_version": "V4",
                    "program_id": self.RAYDIUM_LP_V4_PROGRAM_ID
                },
                {
                    "id": "pool2",
                    "base_token": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                    "quote_token": "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",  # mSOL
                    "lp_token": "lp_token_address2",
                    "base_token_name": "USDC",
                    "quote_token_name": "mSOL",
                    "liquidity": 3000000,
                    "volume_24h": 500000,
                    "fee_rate": 0.25,
                    "price": 23.1,
                    "pool_version": "V4",
                    "program_id": self.RAYDIUM_LP_V4_PROGRAM_ID
                }
            ]
            
            # Update cache
            self.pools_cache = pools
            self.pools_last_updated = now
            
            return pools
            
        except Exception as e:
            logger.error(f"Error getting Raydium pools: {e}", exc_info=True)
            
            # If we have cached data, return it even if expired
            if self.pools_cache:
                logger.warning("Returning stale pool data due to error")
                return self.pools_cache
                
            raise RaydiumClientError(f"Failed to get pools: {e}")
    
    async def find_pools_for_token(self, token_address: str) -> List[Dict[str, Any]]:
        """
        Find all liquidity pools for a specific token.
        
        Args:
            token_address: Token mint address
            
        Returns:
            List[Dict]: List of liquidity pools containing the token
        """
        try:
            all_pools = await self.get_all_pools()
            
            # Find pools where the token is either the base or quote token
            token_pools = [
                pool for pool in all_pools
                if pool["base_token"] == token_address or pool["quote_token"] == token_address
            ]
            
            return token_pools
            
        except Exception as e:
            logger.error(f"Error finding pools for token {token_address}: {e}", exc_info=True)
            return []
    
    async def get_pool_data(self, pool_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed data for a specific pool.
        
        Args:
            pool_id: Pool ID
            
        Returns:
            Optional[Dict]: Pool data or None if not found
        """
        try:
            all_pools = await self.get_all_pools()
            
            # Find the specific pool
            pool = next((p for p in all_pools if p["id"] == pool_id), None)
            
            if not pool:
                return None
            
            # In a real implementation, we would fetch additional data about the pool
            # like reserves, LP token distribution, etc.
            
            # For now, return the basic pool data
            return pool
            
        except Exception as e:
            logger.error(f"Error getting pool data for {pool_id}: {e}", exc_info=True)
            return None
    
    async def calculate_slippage(self, pool_id: str, token_address: str, amount_usd: float) -> Dict[str, Any]:
        """
        Calculate slippage for a trade in a specific pool.
        
        Args:
            pool_id: Pool ID
            token_address: Token address being traded
            amount_usd: Trade amount in USD
            
        Returns:
            Dict: Slippage information
        """
        try:
            pool = await self.get_pool_data(pool_id)
            
            if not pool:
                return {
                    "slippage_percent": 100,
                    "error": "Pool not found"
                }
            
            # Simple slippage model for demonstration
            # In a real implementation, we would use the actual AMM formula
            
            liquidity = pool["liquidity"]
            
            # Simplified slippage calculation
            # This is just an approximation - real calculation would use the bonding curve
            if liquidity > 0:
                slippage_percent = min((amount_usd / liquidity) * 100, 100)
            else:
                slippage_percent = 100
            
            return {
                "pool_id": pool_id,
                "token_address": token_address,
                "amount_usd": amount_usd,
                "liquidity_usd": liquidity,
                "slippage_percent": slippage_percent,
                "price_impact": slippage_percent / 2  # Simplified approximation
            }
            
        except Exception as e:
            logger.error(f"Error calculating slippage for pool {pool_id}: {e}", exc_info=True)
            return {
                "slippage_percent": 100,
                "error": str(e)
            }
    
    async def get_token_liquidity_data(self, token_address: str) -> Dict[str, Any]:
        """
        Get comprehensive liquidity data for a token.
        
        Args:
            token_address: Token mint address
            
        Returns:
            Dict: Token liquidity data
        """
        try:
            pools = await self.find_pools_for_token(token_address)
            
            if not pools:
                return {
                    "token_address": token_address,
                    "total_liquidity_usd": 0,
                    "total_volume_24h": 0,
                    "pools": [],
                    "last_updated": int(time.time())
                }
            
            # Calculate total liquidity and volume
            total_liquidity = sum(pool["liquidity"] for pool in pools)
            total_volume = sum(pool["volume_24h"] for pool in pools)
            
            # Calculate slippage for different trade sizes
            slippage_samples = []
            for amount in [100, 1000, 10000, 100000]:
                # Get slippage for largest pool
                largest_pool = max(pools, key=lambda p: p["liquidity"])
                slippage = await self.calculate_slippage(largest_pool["id"], token_address, amount)
                slippage_samples.append({
                    "amount_usd": amount,
                    "slippage_percent": slippage["slippage_percent"]
                })
            
            # Analyze concentration
            if len(pools) > 0:
                largest_pool_liquidity = max(pool["liquidity"] for pool in pools)
                concentration = largest_pool_liquidity / total_liquidity if total_liquidity > 0 else 1
            else:
                concentration = 0
            
            return {
                "token_address": token_address,
                "total_liquidity_usd": total_liquidity,
                "total_volume_24h": total_volume,
                "pool_count": len(pools),
                "concentration_ratio": concentration,
                "slippage_samples": slippage_samples,
                "pools": pools,
                "last_updated": int(time.time()),
                "source": "raydium"
            }
            
        except Exception as e:
            logger.error(f"Error getting token liquidity data for {token_address}: {e}", exc_info=True)
            return {
                "token_address": token_address,
                "total_liquidity_usd": 0,
                "total_volume_24h": 0,
                "pools": [],
                "error": str(e),
                "last_updated": int(time.time()),
                "source": "raydium"
            }


# Initialize the client
raydium_client = RaydiumClient() 