"""
API routes for trading pattern analysis.
Provides endpoints for analyzing trading patterns on tokens.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from src.analysis.trading import transaction_monitor, wash_trading_detector, pump_dump_detector, trading_pattern_analyzer
from src.api.dependencies import get_token_address

router = APIRouter(prefix="/trading", tags=["Trading Analysis"])

@router.get("/analyze/{token_address}")
async def analyze_token_trading(
    token_address: str = Depends(get_token_address),
    force_refresh: bool = Query(False, description="Force refresh of analysis")
) -> Dict[str, Any]:
    """
    Perform comprehensive trading pattern analysis for a token.
    
    Analyzes transaction patterns, detects wash trading, pump and dump schemes, etc.
    
    Args:
        token_address: Token mint address
        force_refresh: Whether to force a refresh of all analyses
    
    Returns:
        Dict: Comprehensive trading analysis results
    """
    try:
        result = trading_pattern_analyzer.analyze_token_trading(token_address, force_refresh)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transactions/{token_address}")
async def get_token_transactions(
    token_address: str = Depends(get_token_address),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of transactions to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    days: int = Query(7, ge=1, le=30, description="Number of days to look back")
) -> Dict[str, Any]:
    """
    Get token transactions for a specific time period.
    
    Args:
        token_address: Token mint address
        limit: Maximum number of transactions to return
        offset: Offset for pagination
        days: Number of days to look back
        
    Returns:
        Dict: Token transactions and metadata
    """
    try:
        # Calculate start date
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get transactions
        transactions = await transaction_monitor.get_token_transactions(
            token_address,
            start_date=start_date,
            limit=limit,
            offset=offset
        )
        
        # Get stats for context
        stats = await transaction_monitor.get_transaction_stats(token_address, "daily")
        recent_stats = [s for s in stats if s.get("timestamp") and s.get("timestamp") >= start_date]
        
        return {
            "token_address": token_address,
            "transactions": transactions,
            "total_in_period": sum(s.get("transaction_count", 0) for s in recent_stats),
            "period_stats": recent_stats,
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/wash-trading/{token_address}")
async def detect_wash_trading(
    token_address: str = Depends(get_token_address),
    force_refresh: bool = Query(False, description="Force refresh of analysis")
) -> Dict[str, Any]:
    """
    Detect wash trading patterns for a token.
    
    Args:
        token_address: Token mint address
        force_refresh: Whether to force a refresh of the analysis
        
    Returns:
        Dict: Wash trading analysis results
    """
    try:
        result = await wash_trading_detector.detect_wash_trading(token_address, force_refresh)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pump-dump/{token_address}")
async def detect_pump_dump(
    token_address: str = Depends(get_token_address),
    force_refresh: bool = Query(False, description="Force refresh of analysis")
) -> Dict[str, Any]:
    """
    Detect pump and dump patterns for a token.
    
    Args:
        token_address: Token mint address
        force_refresh: Whether to force a refresh of the analysis
        
    Returns:
        Dict: Pump and dump analysis results
    """
    try:
        result = await pump_dump_detector.detect_pump_dump(token_address, force_refresh)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/{token_address}")
async def get_trading_stats(
    token_address: str = Depends(get_token_address),
    period: str = Query("daily", description="Aggregation period (hourly, daily, weekly)")
) -> Dict[str, Any]:
    """
    Get trading statistics for a token.
    
    Args:
        token_address: Token mint address
        period: Aggregation period (hourly, daily, weekly)
        
    Returns:
        Dict: Trading statistics
    """
    try:
        # Make sure we have data
        tracking_result = await transaction_monitor.track_token_transactions(token_address, force_refresh=False)
        
        if "error" in tracking_result:
            raise HTTPException(status_code=500, detail=tracking_result["error"])
        
        # Get stats
        stats = await transaction_monitor.get_transaction_stats(token_address, period)
        
        return {
            "token_address": token_address,
            "period": period,
            "stats": stats,
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 