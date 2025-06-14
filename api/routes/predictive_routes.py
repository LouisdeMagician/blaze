"""
API routes for predictive analytics.
"""
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body

from src.analysis.predictive.predictive_analyzer import predictive_analyzer
from src.api.models.predictive_models import (
    PriceTrajectoryRequest,
    PriceTrajectoryResponse,
    LiquidityChangeRequest,
    LiquidityChangeResponse,
    RiskTrendRequest,
    RiskTrendResponse,
    MarketImpactRequest,
    MarketImpactResponse,
    HolderBehaviorRequest,
    HolderBehaviorResponse
)
from src.api.auth.api_key import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/predictive",
    tags=["predictive"],
    dependencies=[Depends(get_api_key)]
)


@router.post("/price-trajectory", response_model=PriceTrajectoryResponse)
async def predict_price_trajectory(
    request: PriceTrajectoryRequest
):
    """
    Predict price trajectory for a token.
    
    Args:
        request: Price trajectory prediction request
        
    Returns:
        PriceTrajectoryResponse: Prediction results
    """
    try:
        # Convert request model to the format expected by the analyzer
        historical_data = [item.dict() for item in request.historical_data]
        
        # Call predictive analyzer
        prediction = await predictive_analyzer.predict_price_trajectory(
            request.token_address,
            historical_data,
            request.horizon_days
        )
        
        return prediction
    
    except Exception as e:
        logger.error(f"Error predicting price trajectory: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to predict price trajectory: {str(e)}"
        )


@router.post("/liquidity-changes", response_model=LiquidityChangeResponse)
async def forecast_liquidity_changes(
    request: LiquidityChangeRequest
):
    """
    Forecast liquidity changes for a token.
    
    Args:
        request: Liquidity change forecast request
        
    Returns:
        LiquidityChangeResponse: Forecast results
    """
    try:
        # Convert request model to the format expected by the analyzer
        historical_data = [item.dict() for item in request.historical_data]
        
        # Call predictive analyzer
        forecast = await predictive_analyzer.forecast_liquidity_changes(
            request.token_address,
            historical_data,
            request.horizon_days
        )
        
        return forecast
    
    except Exception as e:
        logger.error(f"Error forecasting liquidity changes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to forecast liquidity changes: {str(e)}"
        )


@router.post("/risk-trends", response_model=RiskTrendResponse)
async def predict_risk_trends(
    request: RiskTrendRequest
):
    """
    Predict risk trends for a token.
    
    Args:
        request: Risk trend prediction request
        
    Returns:
        RiskTrendResponse: Prediction results
    """
    try:
        # Convert request model to the format expected by the analyzer
        historical_data = [item.dict() for item in request.historical_data]
        
        # Call predictive analyzer
        prediction = await predictive_analyzer.predict_risk_trends(
            request.token_address,
            historical_data,
            request.horizon_days
        )
        
        return prediction
    
    except Exception as e:
        logger.error(f"Error predicting risk trends: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to predict risk trends: {str(e)}"
        )


@router.post("/market-impact", response_model=MarketImpactResponse)
async def estimate_market_impact(
    request: MarketImpactRequest
):
    """
    Estimate market impact of a trade.
    
    Args:
        request: Market impact estimation request
        
    Returns:
        MarketImpactResponse: Estimation results
    """
    try:
        # Convert request model to the format expected by the analyzer
        historical_data = [item.dict() for item in request.historical_data]
        
        # Call predictive analyzer
        estimation = await predictive_analyzer.estimate_market_impact(
            request.token_address,
            request.order_size,
            historical_data
        )
        
        return estimation
    
    except Exception as e:
        logger.error(f"Error estimating market impact: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to estimate market impact: {str(e)}"
        )


@router.post("/holder-behavior", response_model=HolderBehaviorResponse)
async def predict_holder_behavior(
    request: HolderBehaviorRequest
):
    """
    Predict holder behavior for a token.
    
    Args:
        request: Holder behavior prediction request
        
    Returns:
        HolderBehaviorResponse: Prediction results
    """
    try:
        # Convert request model to the format expected by the analyzer
        historical_data = [item.dict() for item in request.historical_data]
        
        # Call predictive analyzer
        prediction = await predictive_analyzer.predict_holder_behavior(
            request.token_address,
            historical_data,
            request.horizon_days
        )
        
        return prediction
    
    except Exception as e:
        logger.error(f"Error predicting holder behavior: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to predict holder behavior: {str(e)}"
        ) 