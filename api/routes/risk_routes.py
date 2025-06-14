"""
API routes for risk classification.
"""
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body

from src.analysis.risk.risk_classifier import risk_classifier
from src.api.models.risk_models import (
    RiskAssessmentRequest,
    RiskAssessmentResponse,
    RiskComparisonRequest,
    BenchmarkUpdateRequest
)
from src.api.auth.api_key import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/risk",
    tags=["risk"],
    dependencies=[Depends(get_api_key)]
)


@router.post("/classify", response_model=RiskAssessmentResponse)
async def classify_risk(
    request: RiskAssessmentRequest
):
    """
    Perform risk classification for a token based on provided data.
    
    Args:
        request: Risk assessment request with token data
        
    Returns:
        RiskAssessmentResponse: Risk classification results
    """
    try:
        token_address = request.token_address
        
        # Convert request to data dictionary
        data = request.dict()
        
        # Perform risk classification
        result = await risk_classifier.classify_risk(token_address, data)
        
        return result
    
    except Exception as e:
        logger.error(f"Error classifying risk: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to classify risk: {str(e)}"
        )


@router.get("/{token_address}", response_model=RiskAssessmentResponse)
async def get_risk_classification(token_address: str):
    """
    Get the risk classification for a token.
    
    Args:
        token_address: Token address
        
    Returns:
        RiskAssessmentResponse: Risk classification results
    """
    try:
        result = await risk_classifier.get_risk_classification(token_address)
        
        if result.get("status") == "not_found":
            raise HTTPException(
                status_code=404,
                detail=f"No risk assessment found for token: {token_address}"
            )
        
        return result
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error getting risk classification: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get risk classification: {str(e)}"
        )


@router.post("/compare", response_model=Dict[str, Any])
async def compare_risk(
    request: RiskComparisonRequest
):
    """
    Compare risk profiles between multiple tokens.
    
    Args:
        request: Risk comparison request with token addresses
        
    Returns:
        Dict: Comparison results
    """
    try:
        token_addresses = request.token_addresses
        
        # Get risk classifications for each token
        classifications = {}
        for address in token_addresses:
            result = await risk_classifier.get_risk_classification(address)
            if result.get("status") != "not_found" and "composite_score" in result:
                classifications[address] = result
        
        if not classifications:
            raise HTTPException(
                status_code=404,
                detail="No risk assessments found for the provided tokens"
            )
        
        # Create comparison results
        comparison = {
            "tokens": {},
            "rankings": {
                "composite": [],
                "categories": {}
            }
        }
        
        # Extract scores for each token
        for address, data in classifications.items():
            comparison["tokens"][address] = {
                "composite_score": data["composite_score"],
                "risk_level": data["risk_level"],
                "category_scores": data["category_scores"]
            }
        
        # Rank by composite score (ascending = safer first)
        ranked_by_composite = sorted(
            classifications.items(),
            key=lambda x: x[1]["composite_score"]
        )
        
        comparison["rankings"]["composite"] = [
            {"token_address": address, "score": data["composite_score"]}
            for address, data in ranked_by_composite
        ]
        
        # Rank by category scores
        categories = set()
        for data in classifications.values():
            categories.update(data.get("category_scores", {}).keys())
        
        for category in categories:
            # Get tokens with this category
            tokens_with_category = [
                (address, data) for address, data in classifications.items()
                if category in data.get("category_scores", {})
            ]
            
            # Rank by category score
            ranked_by_category = sorted(
                tokens_with_category,
                key=lambda x: x[1]["category_scores"][category]
            )
            
            comparison["rankings"]["categories"][category] = [
                {"token_address": address, "score": data["category_scores"][category]}
                for address, data in ranked_by_category
            ]
        
        return comparison
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error comparing risk: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compare risk: {str(e)}"
        )


@router.post("/benchmark", response_model=Dict[str, Any])
async def update_benchmark_data(
    request: BenchmarkUpdateRequest
):
    """
    Update benchmark data for peer comparison.
    
    Args:
        request: Benchmark data update request
        
    Returns:
        Dict: Status message
    """
    try:
        # Update benchmark data
        await risk_classifier.update_benchmark_data(request.benchmark_data)
        
        return {
            "status": "success",
            "message": "Benchmark data updated successfully"
        }
    
    except Exception as e:
        logger.error(f"Error updating benchmark data: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update benchmark data: {str(e)}"
        ) 