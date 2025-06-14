"""
API Gateway for blockchain data requests.
Centralizes access to blockchain data providers with standardized interfaces.
"""
import logging
import time
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
import asyncio
from functools import wraps

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status

from config.config import config
from src.utils.rate_limiter import rate_limiter
from src.blockchain.solana_client import solana_client, SolanaClientError
from src.blockchain.helius_client import helius_client
from src.services.cache_service import cache_service

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()

class DataSource(Enum):
    """Available data sources for blockchain data."""
    SOLANA_RPC = "solana_rpc"
    HELIUS = "helius"
    SOLSCAN = "solscan"
    JUPITER = "jupiter"
    AUTO = "auto"  # Automatically select the best source

class DataCategory(Enum):
    """Categories of blockchain data for caching and prioritization."""
    TOKEN = "token"
    ACCOUNT = "account"
    TRANSACTION = "transaction"
    PRICE = "price"
    LIQUIDITY = "liquidity"
    HOLDER = "holder"
    PROGRAM = "program"
    MARKET = "market"

# API Gateway cache decorator with category-specific TTL
def with_cache(category: DataCategory, ttl: int = None):
    """
    Decorator for caching API responses.
    
    Args:
        category: Data category for TTL determination
        ttl: Optional override for TTL in seconds
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache first
            cached_result = await cache_service.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_result
            
            # Execute the function if not in cache
            result = await func(*args, **kwargs)
            
            # Determine appropriate TTL if not specified
            effective_ttl = ttl
            if effective_ttl is None:
                # Default TTLs by category
                category_ttls = {
                    DataCategory.TOKEN: 3600,        # 1 hour
                    DataCategory.ACCOUNT: 300,       # 5 minutes
                    DataCategory.TRANSACTION: 86400, # 24 hours
                    DataCategory.PRICE: 60,          # 1 minute
                    DataCategory.LIQUIDITY: 300,     # 5 minutes
                    DataCategory.HOLDER: 900,        # 15 minutes
                    DataCategory.PROGRAM: 86400,     # 24 hours
                    DataCategory.MARKET: 300         # 5 minutes
                }
                effective_ttl = category_ttls.get(category, 300)
            
            # Store in cache
            await cache_service.set(cache_key, result, effective_ttl)
            
            return result
        return wrapper
    return decorator

@router.get("/token/{address}", response_model=Dict[str, Any])
@with_cache(DataCategory.TOKEN)
async def get_token_info(
    address: str = Path(..., description="Token address"),
    source: DataSource = Query(DataSource.AUTO, description="Data source")
):
    """
    Get comprehensive token information.
    
    Args:
        address: Token address
        source: Data source to use
        
    Returns:
        Dict: Token information
    """
    try:
        # Select data source
        if source == DataSource.AUTO:
            # Logic to select best source based on availability and data needs
            source = DataSource.HELIUS if helius_client.api_key else DataSource.SOLANA_RPC
        
        # Get data from selected source
        if source == DataSource.HELIUS:
            token_data = await _get_helius_token_data(address)
        else:
            token_data = await _get_solana_token_data(address)
        
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Token not found: {address}"
            )
        
        return token_data
    
    except SolanaClientError as e:
        logger.error(f"Error fetching token data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Blockchain service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/account/{address}", response_model=Dict[str, Any])
@with_cache(DataCategory.ACCOUNT)
async def get_account_info(
    address: str = Path(..., description="Account address"),
    source: DataSource = Query(DataSource.AUTO, description="Data source")
):
    """
    Get account information.
    
    Args:
        address: Account address
        source: Data source to use
        
    Returns:
        Dict: Account information
    """
    try:
        # Default to Solana RPC for account info
        account_data = await _get_solana_account_data(address)
        
        if not account_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Account not found: {address}"
            )
        
        return account_data
    
    except SolanaClientError as e:
        logger.error(f"Error fetching account data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Blockchain service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/token/{address}/holders", response_model=List[Dict[str, Any]])
@with_cache(DataCategory.HOLDER, ttl=900)  # 15 minutes
async def get_token_holders(
    address: str = Path(..., description="Token address"),
    limit: int = Query(20, description="Maximum number of holders to return"),
    source: DataSource = Query(DataSource.AUTO, description="Data source")
):
    """
    Get token holders information.
    
    Args:
        address: Token address
        limit: Maximum number of holders to return
        source: Data source to use
        
    Returns:
        List[Dict]: Token holders information
    """
    try:
        # Helius is preferred for holder data
        if source == DataSource.AUTO or source == DataSource.HELIUS:
            if helius_client.api_key:
                holders = await _get_helius_token_holders(address, limit)
                if holders:
                    return holders
        
        # Fallback to generic implementation
        holders = await _get_generic_token_holders(address, limit)
        
        return holders
    
    except SolanaClientError as e:
        logger.error(f"Error fetching token holders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Blockchain service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/token/{address}/price", response_model=Dict[str, Any])
@with_cache(DataCategory.PRICE, ttl=60)  # 1 minute
async def get_token_price(
    address: str = Path(..., description="Token address"),
    source: DataSource = Query(DataSource.AUTO, description="Data source")
):
    """
    Get token price information.
    
    Args:
        address: Token address
        source: Data source to use
        
    Returns:
        Dict: Token price information
    """
    try:
        # Implement price fetching logic
        price_data = await _get_token_price_data(address, source)
        
        return price_data
    
    except Exception as e:
        logger.error(f"Error fetching token price: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching price data: {str(e)}"
        )

@router.get("/token/{address}/liquidity", response_model=Dict[str, Any])
@with_cache(DataCategory.LIQUIDITY, ttl=300)  # 5 minutes
async def get_token_liquidity(
    address: str = Path(..., description="Token address"),
    source: DataSource = Query(DataSource.AUTO, description="Data source")
):
    """
    Get token liquidity information.
    
    Args:
        address: Token address
        source: Data source to use
        
    Returns:
        Dict: Token liquidity information
    """
    try:
        # Implement liquidity fetching logic
        liquidity_data = await _get_token_liquidity_data(address, source)
        
        return liquidity_data
    
    except Exception as e:
        logger.error(f"Error fetching token liquidity: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching liquidity data: {str(e)}"
        )

# Helper functions for data fetching

async def _get_helius_token_data(address: str) -> Dict[str, Any]:
    """
    Get token data from Helius API.
    
    Args:
        address: Token address
        
    Returns:
        Dict: Token data
    """
    # TODO: Implement actual Helius API call
    # This is a placeholder for the real implementation
    return {
        "address": address,
        "name": "Sample Token",
        "symbol": "SMPL",
        "decimals": 9,
        "supply": 1000000000,
        "source": "helius"
    }

async def _get_solana_token_data(address: str) -> Dict[str, Any]:
    """
    Get token data from Solana RPC.
    
    Args:
        address: Token address
        
    Returns:
        Dict: Token data
    """
    # Convert sync to async - in real implementation use a native async client
    loop = asyncio.get_event_loop()
    account_info = await loop.run_in_executor(
        None, lambda: solana_client.get_account_info(address)
    )
    
    if not account_info:
        return None
    
    # Parse token data from account info
    # This is simplified - real implementation would parse SPL token data
    return {
        "address": address,
        "data": account_info,
        "source": "solana_rpc"
    }

async def _get_solana_account_data(address: str) -> Dict[str, Any]:
    """
    Get account data from Solana RPC.
    
    Args:
        address: Account address
        
    Returns:
        Dict: Account data
    """
    # Convert sync to async - in real implementation use a native async client
    loop = asyncio.get_event_loop()
    account_info = await loop.run_in_executor(
        None, lambda: solana_client.get_account_info(address)
    )
    
    return account_info

async def _get_helius_token_holders(address: str, limit: int) -> List[Dict[str, Any]]:
    """
    Get token holders from Helius API.
    
    Args:
        address: Token address
        limit: Maximum number of holders to return
        
    Returns:
        List[Dict]: Token holders
    """
    # TODO: Implement actual Helius API call
    # This is a placeholder for the real implementation
    return [
        {
            "address": f"holder{i}",
            "balance": 1000000 - (i * 100000),
            "percentage": 10.0 - (i * 1.0)
        }
        for i in range(min(limit, 10))
    ]

async def _get_generic_token_holders(address: str, limit: int) -> List[Dict[str, Any]]:
    """
    Get token holders using generic method (fallback).
    
    Args:
        address: Token address
        limit: Maximum number of holders to return
        
    Returns:
        List[Dict]: Token holders
    """
    # This is a placeholder - real implementation would query token accounts
    return [
        {
            "address": f"generic_holder{i}",
            "balance": 500000 - (i * 50000),
            "percentage": 5.0 - (i * 0.5)
        }
        for i in range(min(limit, 10))
    ]

async def _get_token_price_data(address: str, source: DataSource) -> Dict[str, Any]:
    """
    Get token price data.
    
    Args:
        address: Token address
        source: Data source
        
    Returns:
        Dict: Price data
    """
    # Placeholder implementation
    return {
        "price": 0.12345,
        "change_24h": 2.5,
        "volume_24h": 1234567,
        "market_cap": 12345678,
        "last_updated": int(time.time())
    }

async def _get_token_liquidity_data(address: str, source: DataSource) -> Dict[str, Any]:
    """
    Get token liquidity data.
    
    Args:
        address: Token address
        source: Data source
        
    Returns:
        Dict: Liquidity data
    """
    # Placeholder implementation
    return {
        "total_liquidity": 2345678,
        "pools": [
            {
                "dex": "Raydium",
                "pair": "SOL",
                "liquidity": 1234567
            },
            {
                "dex": "Orca",
                "pair": "USDC",
                "liquidity": 1111111
            }
        ],
        "last_updated": int(time.time())
    } 