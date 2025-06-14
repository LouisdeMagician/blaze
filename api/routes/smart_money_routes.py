"""
API routes for smart money tracking.
"""
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body

from src.analysis.smart_money.smart_money_tracker import smart_money_tracker
from src.api.models.smart_money_models import (
    SmartWalletIdentificationRequest,
    SmartWalletListResponse,
    SmartWalletResponse,
    FlowTrackingRequest,
    FlowMetricsResponse,
    ConcentrationRequest,
    ConcentrationResponse,
    FollowerRequest,
    FollowerResponse,
    SentimentRequest,
    SentimentResponse,
    WalletLabelRequest,
    WalletLabelResponse
)
from src.api.auth.api_key import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/smart-money",
    tags=["smart-money"],
    dependencies=[Depends(get_api_key)]
)


@router.post("/identify", response_model=SmartWalletListResponse)
async def identify_smart_wallets(
    request: SmartWalletIdentificationRequest
):
    """
    Identify smart money wallets based on transaction data.
    
    Args:
        request: Smart wallet identification request with transaction data
        
    Returns:
        SmartWalletListResponse: List of identified smart wallets
    """
    try:
        # Call smart money tracker to identify wallets
        smart_wallets = await smart_money_tracker.identify_smart_wallets(request.transactions)
        
        # Format response
        wallet_list = [
            {
                "address": address,
                "smart_score": data["smart_score"],
                "label": data.get("label", "Unknown"),
                "metrics": data.get("metrics", {})
            }
            for address, data in smart_wallets.items()
        ]
        
        # Sort by smart score
        wallet_list = sorted(wallet_list, key=lambda x: x["smart_score"], reverse=True)
        
        return {
            "wallets": wallet_list,
            "count": len(wallet_list)
        }
    
    except Exception as e:
        logger.error(f"Error identifying smart wallets: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to identify smart wallets: {str(e)}"
        )


@router.post("/flows", response_model=FlowMetricsResponse)
async def track_wallet_flows(
    request: FlowTrackingRequest
):
    """
    Track fund flows between wallets.
    
    Args:
        request: Flow tracking request with transaction data
        
    Returns:
        FlowMetricsResponse: Flow metrics data
    """
    try:
        # Call smart money tracker to track flows
        flow_metrics = await smart_money_tracker.track_wallet_flows(request.transactions)
        
        return flow_metrics
    
    except Exception as e:
        logger.error(f"Error tracking wallet flows: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to track wallet flows: {str(e)}"
        )


@router.post("/concentration", response_model=ConcentrationResponse)
async def analyze_token_concentration(
    request: ConcentrationRequest
):
    """
    Analyze smart money concentration for a specific token.
    
    Args:
        request: Concentration request with token holder data
        
    Returns:
        ConcentrationResponse: Concentration metrics
    """
    try:
        # Call smart money tracker to analyze concentration
        concentration = smart_money_tracker.analyze_token_concentration(
            request.token_address, request.holders
        )
        
        return concentration
    
    except Exception as e:
        logger.error(f"Error analyzing token concentration: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze token concentration: {str(e)}"
        )


@router.post("/followers", response_model=FollowerResponse)
async def identify_followers(
    request: FollowerRequest
):
    """
    Identify wallets that follow a specific smart money wallet.
    
    Args:
        request: Follower identification request
        
    Returns:
        FollowerResponse: Follower data
    """
    try:
        # Call smart money tracker to identify followers
        followers = await smart_money_tracker.identify_followers(
            request.wallet_address, request.transactions
        )
        
        return followers
    
    except Exception as e:
        logger.error(f"Error identifying followers: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to identify followers: {str(e)}"
        )


@router.post("/sentiment", response_model=SentimentResponse)
async def calculate_smart_money_sentiment(
    request: SentimentRequest
):
    """
    Calculate smart money sentiment indicators for a token.
    
    Args:
        request: Sentiment request with transaction data
        
    Returns:
        SentimentResponse: Sentiment indicators
    """
    try:
        # Call smart money tracker to calculate sentiment
        sentiment = await smart_money_tracker.calculate_smart_money_sentiment(
            request.token_address, request.transactions
        )
        
        return sentiment
    
    except Exception as e:
        logger.error(f"Error calculating sentiment: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate sentiment: {str(e)}"
        )


@router.post("/label", response_model=WalletLabelResponse)
async def label_wallet(
    request: WalletLabelRequest
):
    """
    Label a wallet with a descriptive name.
    
    Args:
        request: Wallet label request
        
    Returns:
        WalletLabelResponse: Status message
    """
    try:
        # Call smart money tracker to label wallet
        result = await smart_money_tracker.label_wallet(
            request.wallet_address, request.label
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Error labeling wallet: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to label wallet: {str(e)}"
        )


@router.get("/labels", response_model=Dict[str, str])
async def get_wallet_labels():
    """
    Get all wallet labels.
    
    Returns:
        Dict: Wallet labels
    """
    try:
        # Call smart money tracker to get labels
        labels = await smart_money_tracker.get_wallet_labels()
        
        return labels
    
    except Exception as e:
        logger.error(f"Error getting wallet labels: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get wallet labels: {str(e)}"
        ) 