"""
API routes for token ownership analysis.
Provides endpoints for token ownership and distribution analysis.
"""
import logging
from fastapi import APIRouter, HTTPException, Query, Path
from typing import Dict, Any, Optional

from src.analysis.ownership.ownership_analyzer import ownership_analyzer
from src.analysis.ownership.whale_analyzer import whale_analyzer
from src.analysis.ownership.wallet_clustering import wallet_clusterer
from src.analysis.ownership.dev_wallet_analyzer import dev_wallet_analyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ownership", tags=["ownership"])

@router.get("/analyze/{token_address}")
async def analyze_token_ownership(
    token_address: str = Path(..., description="Token address to analyze"),
    force_refresh: bool = Query(False, description="Force refresh the analysis")
) -> Dict[str, Any]:
    """
    Perform comprehensive ownership analysis for a token.
    
    Args:
        token_address: Token address
        force_refresh: Whether to force refresh the data
        
    Returns:
        Dict: Ownership analysis results
    """
    try:
        result = ownership_analyzer.analyze_token_ownership(token_address, force_refresh)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing token ownership for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/whales/{token_address}")
async def get_token_whales(
    token_address: str = Path(..., description="Token address to analyze"),
    force_refresh: bool = Query(False, description="Force refresh the analysis")
) -> Dict[str, Any]:
    """
    Get whale wallet analysis for a token.
    
    Args:
        token_address: Token address
        force_refresh: Whether to force refresh the data
        
    Returns:
        Dict: Whale analysis results
    """
    try:
        result = await whale_analyzer.analyze_whale_wallets(token_address, force_refresh)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return result
        
    except Exception as e:
        logger.error(f"Error getting whale analysis for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/clusters/{token_address}")
async def get_token_wallet_clusters(
    token_address: str = Path(..., description="Token address to analyze"),
    force_refresh: bool = Query(False, description="Force refresh the analysis")
) -> Dict[str, Any]:
    """
    Get wallet clustering analysis for a token.
    
    Args:
        token_address: Token address
        force_refresh: Whether to force refresh the data
        
    Returns:
        Dict: Wallet clustering results
    """
    try:
        result = await wallet_clusterer.cluster_token_wallets(token_address, force_refresh)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return result
        
    except Exception as e:
        logger.error(f"Error getting wallet clustering for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/team/{token_address}")
async def get_token_team_info(
    token_address: str = Path(..., description="Token address to analyze"),
    force_refresh: bool = Query(False, description="Force refresh the analysis")
) -> Dict[str, Any]:
    """
    Get team/developer wallet analysis for a token.
    
    Args:
        token_address: Token address
        force_refresh: Whether to force refresh the data
        
    Returns:
        Dict: Team wallet analysis results
    """
    try:
        if force_refresh:
            # Run full analysis to refresh the data
            await dev_wallet_analyzer.analyze_dev_wallets(token_address, force_refresh=True)
            
        # Get team info (uses cached data if available)
        result = await dev_wallet_analyzer.get_token_team_info(token_address)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return result
        
    except Exception as e:
        logger.error(f"Error getting team info for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/wallet/{wallet_address}/is_developer")
async def check_if_developer_wallet(
    wallet_address: str = Path(..., description="Wallet address to check")
) -> Dict[str, Any]:
    """
    Check if a wallet is identified as a developer wallet for any token.
    
    Args:
        wallet_address: Wallet address to check
        
    Returns:
        Dict: Developer wallet information
    """
    try:
        result = await dev_wallet_analyzer.is_developer_wallet(wallet_address)
        return result
        
    except Exception as e:
        logger.error(f"Error checking if {wallet_address} is a developer wallet: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/wallet/{wallet_address}/related")
async def get_related_wallets(
    wallet_address: str = Path(..., description="Wallet address to check"),
    token_address: Optional[str] = Query(None, description="Optional token address to filter by")
) -> Dict[str, Any]:
    """
    Get wallets related to a specific wallet based on transaction patterns.
    
    Args:
        wallet_address: Wallet address to check
        token_address: Optional token address to filter by
        
    Returns:
        Dict: Related wallet information
    """
    try:
        result = await wallet_clusterer.get_related_wallets(wallet_address, token_address)
        return result
        
    except Exception as e:
        logger.error(f"Error getting related wallets for {wallet_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/whale/movements/{token_address}")
async def get_whale_movements(
    token_address: str = Path(..., description="Token address to analyze"),
    days: int = Query(7, description="Number of days to analyze")
) -> Dict[str, Any]:
    """
    Analyze recent whale movements for a token.
    
    Args:
        token_address: Token address
        days: Number of days to analyze
        
    Returns:
        Dict: Whale movement analysis
    """
    try:
        # Make sure we have recent whale data
        await whale_analyzer.analyze_whale_wallets(token_address)
        
        # Get whale movement analysis
        result = await whale_analyzer.get_whale_movement_analysis(token_address, days)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing whale movements for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 