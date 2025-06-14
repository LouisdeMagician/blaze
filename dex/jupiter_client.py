"""
Jupiter API client for DEX aggregation.
Provides functionality to interact with Jupiter Aggregator for cross-DEX liquidity and swap data.
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
class JupiterClientError(Exception):
    """Base exception for Jupiter client errors."""
    pass

class JupiterRateLimitError(JupiterClientError):
    """Exception raised when rate limit is exceeded."""
    pass

class JupiterClient:
    """Client for interacting with Jupiter DEX Aggregator."""
    
    # Jupiter program IDs
    JUPITER_V3_PROGRAM_ID = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
    JUPITER_V4_PROGRAM_ID = "JUP4Fb2cqufzdZhxFqwLYZ6hvdpfL6dLN8LZq9RRuNT"
    
    def __init__(self):
        """Initialize the Jupiter client."""
        self.api_url = config.get("dex", {}).get("jupiter", {}).get("api_url", "https://quote-api.jup.ag/v4")
        self.session = None
        self.request_count = 0
        self.last_reset = time.time()
        self.rate_limit = 60  # Default rate limit per minute
        self.max_retries = 3
        self.retry_delay = 1.0
        self.initialized = False
        
        # Cache
        self.tokens_cache = []
        self.tokens_last_updated = 0
        self.tokens_cache_ttl = 3600  # 1 hour
        
        # Price cache with shorter TTL
        self.price_cache = {}
        self.price_last_updated = 0
        self.price_cache_ttl = 60  # 1 minute
    
    async def initialize(self):
        """Initialize the client session."""
        if not self.initialized:
            self.session = aiohttp.ClientSession()
            self.initialized = True
            logger.info("Jupiter client initialized")
    
    async def close(self):
        """Close the client session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.initialized = False
            logger.info("Jupiter client closed")
    
    @circuit_breaker("jupiter_api", failure_threshold=5, timeout=60.0)
    async def _make_request(self, endpoint: str, method: str = "GET", 
                           params: Dict[str, Any] = None, data: Dict = None) -> Dict[str, Any]:
        """
        Make a request to the Jupiter API.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST)
            params: URL parameters
            data: Request body for POST
            
        Returns:
            Dict: Response data
            
        Raises:
            JupiterClientError: On request failure
            JupiterRateLimitError: When rate limited
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
                raise JupiterRateLimitError(f"Rate limit exceeded. Try again in {delay:.2f} seconds")
        
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
                            logger.warning(f"Rate limited by Jupiter API. Retrying in {delay:.2f}s")
                            await asyncio.sleep(delay)
                            continue
                        
                        response.raise_for_status()
                        return await response.json()
                        
                elif method.upper() == "POST":
                    async with self.session.post(url, params=params, json=data, headers=headers) as response:
                        if response.status == 429:  # Rate limited
                            retries += 1
                            delay = self.retry_delay * (2 ** retries)
                            logger.warning(f"Rate limited by Jupiter API. Retrying in {delay:.2f}s")
                            await asyncio.sleep(delay)
                            continue
                        
                        response.raise_for_status()
                        return await response.json()
                
                else:
                    raise JupiterClientError(f"Unsupported HTTP method: {method}")
                    
            except aiohttp.ClientResponseError as e:
                if e.status == 429:  # Rate limited
                    retries += 1
                    delay = self.retry_delay * (2 ** retries)
                    logger.warning(f"Rate limited by Jupiter API. Retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                    continue
                
                logger.error(f"Jupiter API error: {e}")
                raise JupiterClientError(f"API error: {e}")
                
            except aiohttp.ClientError as e:
                retries += 1
                if retries <= self.max_retries:
                    delay = self.retry_delay * (2 ** retries)
                    logger.warning(f"Jupiter API request failed: {e}. Retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                    continue
                
                logger.error(f"Jupiter API request failed after {retries} retries: {e}")
                raise JupiterClientError(f"Request failed: {e}")
                
        raise JupiterClientError(f"Failed after {self.max_retries} retries")
    
    async def get_tokens(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get all tokens supported by Jupiter.
        
        Args:
            force_refresh: Force refresh the tokens cache
            
        Returns:
            List[Dict]: List of tokens
        """
        now = time.time()
        
        # Check if we can use cached data
        if (not force_refresh and 
            self.tokens_cache and 
            now - self.tokens_last_updated < self.tokens_cache_ttl):
            return self.tokens_cache
        
        try:
            # Get tokens from Jupiter API
            tokens = await self._make_request("tokens")
            
            # Update cache
            self.tokens_cache = tokens
            self.tokens_last_updated = now
            
            return tokens
            
        except Exception as e:
            logger.error(f"Error getting Jupiter tokens: {e}", exc_info=True)
            
            # If we have cached data, return it even if expired
            if self.tokens_cache:
                logger.warning("Returning stale token data due to error")
                return self.tokens_cache
                
            raise JupiterClientError(f"Failed to get tokens: {e}")
    
    async def get_token_price(self, token_address: str, quote_token: str = "USDC") -> Optional[Dict[str, Any]]:
        """
        Get token price from Jupiter.
        
        Args:
            token_address: Token mint address
            quote_token: Quote token symbol (default: USDC)
            
        Returns:
            Optional[Dict]: Token price data or None if not available
        """
        cache_key = f"{token_address}:{quote_token}"
        now = time.time()
        
        # Check cache first
        if cache_key in self.price_cache and now - self.price_last_updated < self.price_cache_ttl:
            return self.price_cache[cache_key]
        
        try:
            # Get all tokens first to find the quote token address
            tokens = await self.get_tokens()
            
            # Find the quote token address (usually USDC)
            quote_token_info = next((t for t in tokens if t.get("symbol") == quote_token), None)
            
            if not quote_token_info:
                logger.warning(f"Quote token {quote_token} not found in Jupiter tokens")
                return None
            
            quote_token_address = quote_token_info.get("address")
            
            # Get price from Jupiter's price API
            price_data = await self._make_request(f"price?ids={token_address}&vsToken={quote_token_address}")
            
            if not price_data or token_address not in price_data:
                return None
            
            result = {
                "token_address": token_address,
                "quote_token": quote_token,
                "price": price_data[token_address],
                "last_updated": int(time.time()),
                "source": "jupiter"
            }
            
            # Update cache
            self.price_cache[cache_key] = result
            self.price_last_updated = now
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting token price for {token_address}: {e}", exc_info=True)
            return None
    
    async def get_swap_quote(self, input_token: str, output_token: str, amount: float, slippage_bps: int = 100) -> Optional[Dict[str, Any]]:
        """
        Get a swap quote from Jupiter.
        
        Args:
            input_token: Input token address
            output_token: Output token address
            amount: Amount in input token (in smallest units)
            slippage_bps: Slippage tolerance in basis points (1 bps = 0.01%)
            
        Returns:
            Optional[Dict]: Swap quote data or None if not available
        """
        try:
            # Parameters for Jupiter quote API
            params = {
                "inputMint": input_token,
                "outputMint": output_token,
                "amount": str(int(amount)),
                "slippageBps": slippage_bps
            }
            
            # Get quote
            quote = await self._make_request("quote", params=params)
            
            return quote
            
        except Exception as e:
            logger.error(f"Error getting swap quote: {e}", exc_info=True)
            return None
    
    async def calculate_price_impact(self, token_address: str, amount_usd: float) -> Dict[str, Any]:
        """
        Calculate price impact for trading a token.
        
        Args:
            token_address: Token address
            amount_usd: Trade amount in USD
            
        Returns:
            Dict: Price impact information
        """
        try:
            # Get price of the token in USDC
            price_data = await self.get_token_price(token_address)
            
            if not price_data or not price_data.get("price"):
                return {
                    "price_impact_percent": 100,
                    "error": "Token price not available"
                }
            
            price = price_data["price"]
            
            # Calculate token amount based on USD value
            token_amount = amount_usd / price
            
            # Get USDC token info
            tokens = await self.get_tokens()
            usdc_token = next((t for t in tokens if t.get("symbol") == "USDC"), None)
            
            if not usdc_token:
                return {
                    "price_impact_percent": 100,
                    "error": "USDC token not found"
                }
            
            # Get quote for the token amount
            token_decimals = next((t for t in tokens if t.get("address") == token_address), {}).get("decimals", 6)
            token_amount_smallest = int(token_amount * (10 ** token_decimals))
            
            # Get a quote from Jupiter
            quote = await self.get_swap_quote(
                token_address,
                usdc_token["address"],
                token_amount_smallest
            )
            
            if not quote or "priceImpactPct" not in quote:
                return {
                    "price_impact_percent": 100,
                    "error": "Failed to get price impact from Jupiter"
                }
            
            # Jupiter returns price impact as decimal (e.g., 0.01 for 1%)
            price_impact_pct = float(quote["priceImpactPct"]) * 100
            
            return {
                "token_address": token_address,
                "amount_usd": amount_usd,
                "price_impact_percent": price_impact_pct,
                "route_count": len(quote.get("routesInfos", [])),
                "best_route_dexes": [route.get("marketInfos", [{}])[0].get("amm", {}).get("label", "Unknown") for route in quote.get("routesInfos", [])[:3]],
                "last_updated": int(time.time()),
                "source": "jupiter"
            }
            
        except Exception as e:
            logger.error(f"Error calculating price impact: {e}", exc_info=True)
            return {
                "price_impact_percent": 100,
                "error": str(e)
            }
    
    async def get_token_liquidity_data(self, token_address: str) -> Dict[str, Any]:
        """
        Get comprehensive liquidity data for a token across all DEXes via Jupiter.
        
        Args:
            token_address: Token mint address
            
        Returns:
            Dict: Token liquidity data
        """
        try:
            # Get token price and other details
            price_data = await self.get_token_price(token_address)
            
            if not price_data:
                return {
                    "token_address": token_address,
                    "total_liquidity_usd": 0,
                    "routes": [],
                    "last_updated": int(time.time()),
                    "source": "jupiter"
                }
            
            # Calculate price impact for different trade sizes
            impact_samples = []
            for amount in [100, 1000, 10000, 100000]:
                impact = await self.calculate_price_impact(token_address, amount)
                impact_samples.append({
                    "amount_usd": amount,
                    "price_impact_percent": impact.get("price_impact_percent", 100)
                })
            
            # Get a sample quote for routing information
            tokens = await self.get_tokens()
            token_info = next((t for t in tokens if t.get("address") == token_address), None)
            usdc_token = next((t for t in tokens if t.get("symbol") == "USDC"), None)
            
            if not token_info or not usdc_token:
                return {
                    "token_address": token_address,
                    "price_usd": price_data.get("price"),
                    "impact_samples": impact_samples,
                    "routes": [],
                    "last_updated": int(time.time()),
                    "source": "jupiter"
                }
            
            # Get a sample quote to extract routing information
            token_decimals = token_info.get("decimals", 6)
            token_amount = 1 * (10 ** token_decimals)  # 1 token
            
            quote = await self.get_swap_quote(
                token_address,
                usdc_token["address"],
                token_amount
            )
            
            routes = []
            if quote and "routesInfos" in quote:
                for route_info in quote["routesInfos"][:5]:  # Limit to top 5 routes
                    route_data = {
                        "percent": route_info.get("percentage", 0) * 100,
                        "out_amount": route_info.get("outAmount", 0),
                        "market_infos": []
                    }
                    
                    # Extract market (DEX) information
                    for market in route_info.get("marketInfos", []):
                        market_data = {
                            "id": market.get("id", "unknown"),
                            "label": market.get("amm", {}).get("label", "Unknown DEX"),
                            "in_amount": market.get("inAmount", 0),
                            "out_amount": market.get("outAmount", 0),
                            "liquidity_fee": market.get("lpFee", {}).get("amount", 0)
                        }
                        route_data["market_infos"].append(market_data)
                    
                    routes.append(route_data)
            
            # Estimate total liquidity based on price impact
            # This is very approximate - in a real implementation we'd use more sophisticated methods
            estimated_liquidity = 0
            if impact_samples:
                # Find the sample with closest to 1% impact
                closest_sample = min(impact_samples, key=lambda x: abs(x.get("price_impact_percent", 100) - 1))
                if closest_sample.get("price_impact_percent", 100) < 50:
                    # Rough estimate: if 1% impact at X dollars, then liquidity ~= 100*X
                    estimated_liquidity = closest_sample.get("amount_usd", 0) * 100 / max(0.1, closest_sample.get("price_impact_percent", 100))
            
            return {
                "token_address": token_address,
                "token_symbol": token_info.get("symbol"),
                "price_usd": price_data.get("price"),
                "estimated_liquidity_usd": estimated_liquidity,
                "impact_samples": impact_samples,
                "dex_count": len(set(r.get("market_infos", [{}])[0].get("label") for r in routes)),
                "routes": routes,
                "last_updated": int(time.time()),
                "source": "jupiter"
            }
            
        except Exception as e:
            logger.error(f"Error getting token liquidity data from Jupiter for {token_address}: {e}", exc_info=True)
            return {
                "token_address": token_address,
                "total_liquidity_usd": 0,
                "routes": [],
                "error": str(e),
                "last_updated": int(time.time()),
                "source": "jupiter"
            }


# Initialize the client
jupiter_client = JupiterClient() 