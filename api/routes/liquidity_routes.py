"""
API routes for token liquidity analysis.
Provides endpoints for comprehensive liquidity analysis and historical data.
"""
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Path, Depends

from src.dex.liquidity_analyzer import liquidity_analyzer
from src.dex.liquidity_history_tracker import liquidity_history_tracker
from src.dex.rugpull_detector import rugpull_detector
from src.dex.lp_token_tracker import lp_token_tracker
from src.dex.dex_aggregator import dex_aggregator
from src.utils.rate_limiter import rate_limit
from src.api.dependencies import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/liquidity", tags=["liquidity"])


@router.get("/analyze/{token_address}")
async def analyze_token_liquidity(
    token_address: str,
    force_refresh: bool = Query(False, description="Force refresh the data")
) -> Dict[str, Any]:
    """
    Perform comprehensive liquidity analysis for a token.
    
    Args:
        token_address: Token mint address
        force_refresh: Whether to force a refresh of the data
        
    Returns:
        Dict: Comprehensive liquidity analysis
    """
    try:
        result = liquidity_analyzer.analyze_token_liquidity(token_address, force_refresh)
        return result
    except Exception as e:
        logger.error(f"Error analyzing token liquidity for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error analyzing token: {str(e)}")


@router.get("/rugpull-risk/{token_address}")
async def get_rugpull_risk(token_address: str) -> Dict[str, Any]:
    """
    Get rugpull risk analysis for a token.
    
    Args:
        token_address: Token mint address
        
    Returns:
        Dict: Rugpull risk analysis
    """
    try:
        result = await rugpull_detector.analyze_rugpull_risk(token_address)
        return result
    except Exception as e:
        logger.error(f"Error getting rugpull risk for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error analyzing rugpull risk: {str(e)}")


@router.get("/lp-risk/{token_address}")
async def get_lp_token_risk(token_address: str) -> Dict[str, Any]:
    """
    Get LP token risk analysis for a token.
    
    Args:
        token_address: Token mint address
        
    Returns:
        Dict: LP token risk analysis
    """
    try:
        result = await lp_token_tracker.analyze_lp_token_risk(token_address)
        return result
    except Exception as e:
        logger.error(f"Error getting LP token risk for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error analyzing LP token risk: {str(e)}")


@router.get("/history/{token_address}")
async def get_liquidity_history(
    token_address: str,
    days: int = Query(30, description="Number of days of history to retrieve")
) -> Dict[str, Any]:
    """
    Get historical liquidity data for a token.
    
    Args:
        token_address: Token mint address
        days: Number of days of history to retrieve
        
    Returns:
        Dict: Historical liquidity data
    """
    try:
        result = await liquidity_history_tracker.get_liquidity_history(token_address, days)
        return {"token_address": token_address, "days": days, "history": result}
    except Exception as e:
        logger.error(f"Error getting liquidity history for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting liquidity history: {str(e)}")


@router.get("/chart-data/{token_address}")
async def get_liquidity_chart_data(
    token_address: str,
    days: int = Query(30, description="Number of days of history to retrieve")
) -> Dict[str, Any]:
    """
    Get data for liquidity history chart.
    
    Args:
        token_address: Token mint address
        days: Number of days of history to retrieve
        
    Returns:
        Dict: Chart data
    """
    try:
        result = liquidity_analyzer.get_historical_liquidity_chart_data(token_address, days)
        return result
    except Exception as e:
        logger.error(f"Error getting liquidity chart data for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting chart data: {str(e)}")


@router.get("/anomalies/{token_address}")
async def get_liquidity_anomalies(
    token_address: str,
    days: int = Query(30, description="Number of days to analyze")
) -> Dict[str, Any]:
    """
    Detect anomalies in liquidity data.
    
    Args:
        token_address: Token mint address
        days: Number of days to analyze
        
    Returns:
        Dict: Detected anomalies
    """
    try:
        result = await liquidity_history_tracker.detect_liquidity_anomalies(token_address, days)
        return result
    except Exception as e:
        logger.error(f"Error detecting liquidity anomalies for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error detecting anomalies: {str(e)}")


@router.post("/record-snapshot/{token_address}")
async def record_liquidity_snapshot(token_address: str) -> Dict[str, Any]:
    """
    Record current liquidity data as a snapshot.
    
    Args:
        token_address: Token mint address
        
    Returns:
        Dict: Recorded snapshot data
    """
    try:
        result = await liquidity_history_tracker.record_liquidity_snapshot(token_address)
        return result
    except Exception as e:
        logger.error(f"Error recording liquidity snapshot for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error recording snapshot: {str(e)}")


@router.get("/token/{token_address}")
@rate_limit(max_calls=20, time_window=60)
async def get_token_liquidity(
    token_address: str = Path(..., description="Token mint address"),
    refresh: bool = Query(False, description="Force refresh the data"),
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    Get comprehensive liquidity data for a token.
    
    Args:
        token_address: Token mint address
        refresh: Force refresh the data
        api_key: API key for authentication
    
    Returns:
        Dict: Comprehensive liquidity data
    """
    try:
        liquidity_data = await dex_aggregator.get_token_liquidity(token_address, force_refresh=refresh)
        return liquidity_data
        
    except Exception as e:
        logger.error(f"Error getting liquidity data for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting liquidity data: {str(e)}")


@router.get("/token/{token_address}/risk")
@rate_limit(max_calls=30, time_window=60)
async def get_token_liquidity_risk(
    token_address: str = Path(..., description="Token mint address"),
    refresh: bool = Query(False, description="Force refresh the data"),
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    Get liquidity risk assessment for a token.
    
    Args:
        token_address: Token mint address
        refresh: Force refresh the data
        api_key: API key for authentication
    
    Returns:
        Dict: Liquidity risk metrics
    """
    try:
        liquidity_data = await dex_aggregator.get_token_liquidity(token_address, force_refresh=refresh)
        
        # Extract just the risk metrics and key info
        risk_data = {
            "token_address": token_address,
            "total_liquidity_usd": liquidity_data.get("total_liquidity_usd", 0),
            "price_usd": liquidity_data.get("price_usd"),
            "risk_metrics": liquidity_data.get("risk_metrics", {}),
            "liquidity_concentration": liquidity_data.get("liquidity_concentration", {}),
            "slippage_samples": liquidity_data.get("slippage_samples", []),
            "last_updated": liquidity_data.get("last_updated", 0),
        }
        
        return risk_data
        
    except Exception as e:
        logger.error(f"Error getting liquidity risk for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting liquidity risk: {str(e)}")


@router.get("/token/{token_address}/dexes")
@rate_limit(max_calls=20, time_window=60)
async def get_token_dex_breakdown(
    token_address: str = Path(..., description="Token mint address"),
    refresh: bool = Query(False, description="Force refresh the data"),
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    Get DEX breakdown for a token's liquidity.
    
    Args:
        token_address: Token mint address
        refresh: Force refresh the data
        api_key: API key for authentication
    
    Returns:
        Dict: DEX breakdown for token liquidity
    """
    try:
        liquidity_data = await dex_aggregator.get_token_liquidity(token_address, force_refresh=refresh)
        
        # Extract DEX breakdown
        dex_data = {
            "token_address": token_address,
            "total_liquidity_usd": liquidity_data.get("total_liquidity_usd", 0),
            "dex_breakdown": liquidity_data.get("dex_breakdown", {}),
            "pools_count": liquidity_data.get("total_pool_count", 0),
            "highest_liquidity_dex": liquidity_data.get("liquidity_concentration", {}).get("dex_with_highest", ""),
            "highest_concentration": liquidity_data.get("liquidity_concentration", {}).get("highest_concentration", 0),
            "last_updated": liquidity_data.get("last_updated", 0),
        }
        
        return dex_data
        
    except Exception as e:
        logger.error(f"Error getting DEX breakdown for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting DEX breakdown: {str(e)}")


@router.get("/token/{token_address}/pools")
@rate_limit(max_calls=15, time_window=60)
async def get_token_pools(
    token_address: str = Path(..., description="Token mint address"),
    refresh: bool = Query(False, description="Force refresh the data"),
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    Get all liquidity pools for a token.
    
    Args:
        token_address: Token mint address
        refresh: Force refresh the data
        api_key: API key for authentication
    
    Returns:
        Dict: All liquidity pools for the token
    """
    try:
        liquidity_data = await dex_aggregator.get_token_liquidity(token_address, force_refresh=refresh)
        
        # Extract pools data
        pools_data = {
            "token_address": token_address,
            "total_pool_count": liquidity_data.get("total_pool_count", 0),
            "pools": liquidity_data.get("pools", []),
            "last_updated": liquidity_data.get("last_updated", 0),
        }
        
        return pools_data
        
    except Exception as e:
        logger.error(f"Error getting pools for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting pools: {str(e)}")


@router.get("/token/{token_address}/slippage")
@rate_limit(max_calls=20, time_window=60)
async def get_token_slippage(
    token_address: str = Path(..., description="Token mint address"),
    amount_usd: float = Query(1000, description="Trade amount in USD for slippage calculation"),
    refresh: bool = Query(False, description="Force refresh the data"),
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    Get slippage estimation for a token trade.
    
    Args:
        token_address: Token mint address
        amount_usd: Trade amount in USD
        refresh: Force refresh the data
        api_key: API key for authentication
    
    Returns:
        Dict: Slippage estimation
    """
    try:
        liquidity_data = await dex_aggregator.get_token_liquidity(token_address, force_refresh=refresh)
        
        # Find the closest slippage sample to the requested amount
        slippage_samples = liquidity_data.get("slippage_samples", [])
        if not slippage_samples:
            return {
                "token_address": token_address,
                "amount_usd": amount_usd,
                "estimated_slippage_percent": 100,
                "error": "No slippage data available"
            }
        
        # Find the closest sample
        closest_sample = min(slippage_samples, key=lambda x: abs(x.get("amount_usd", 0) - amount_usd))
        
        # Use the closest sample or interpolate
        if closest_sample.get("amount_usd") == amount_usd:
            estimated_slippage = closest_sample.get("slippage_percent", closest_sample.get("price_impact_percent", 100))
        else:
            # Simple linear interpolation between samples
            # Find the two closest samples
            sorted_samples = sorted(slippage_samples, key=lambda x: x.get("amount_usd", 0))
            lower = next((s for s in sorted_samples if s.get("amount_usd", 0) <= amount_usd), sorted_samples[0])
            upper = next((s for s in sorted_samples if s.get("amount_usd", 0) >= amount_usd), sorted_samples[-1])
            
            if lower == upper:
                estimated_slippage = lower.get("slippage_percent", lower.get("price_impact_percent", 100))
            else:
                lower_amount = lower.get("amount_usd", 0)
                upper_amount = upper.get("amount_usd", 0)
                lower_slippage = lower.get("slippage_percent", lower.get("price_impact_percent", 100))
                upper_slippage = upper.get("slippage_percent", upper.get("price_impact_percent", 100))
                
                # Interpolate
                if upper_amount - lower_amount > 0:
                    ratio = (amount_usd - lower_amount) / (upper_amount - lower_amount)
                    estimated_slippage = lower_slippage + ratio * (upper_slippage - lower_slippage)
                else:
                    estimated_slippage = lower_slippage
        
        return {
            "token_address": token_address,
            "amount_usd": amount_usd,
            "estimated_slippage_percent": estimated_slippage,
            "total_liquidity_usd": liquidity_data.get("total_liquidity_usd", 0),
            "last_updated": liquidity_data.get("last_updated", 0),
        }
        
    except Exception as e:
        logger.error(f"Error calculating slippage for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error calculating slippage: {str(e)}") 