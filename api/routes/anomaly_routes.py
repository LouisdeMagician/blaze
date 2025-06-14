"""
API routes for anomaly detection.
"""
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from src.analysis.anomaly.anomaly_detector import anomaly_detector
from src.api.models.anomaly_models import (
    AnomalyDataPoint,
    AnomalyBatchDataPoints,
    AnomalyResponse,
    AnomalyListResponse
)
from src.api.auth.api_key import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/anomaly",
    tags=["anomaly"],
    dependencies=[Depends(get_api_key)]
)


@router.post("/data/{metric_key}", response_model=dict)
async def add_data_point(
    metric_key: str,
    data_point: AnomalyDataPoint
):
    """
    Add a data point for anomaly detection.
    
    Args:
        metric_key: Unique identifier for the metric
        data_point: Data point to add
        
    Returns:
        Dict: Status message
    """
    try:
        await anomaly_detector.add_data_point(
            metric_key=metric_key,
            value=data_point.value,
            timestamp=data_point.timestamp
        )
        
        return {"status": "success", "message": "Data point added"}
    
    except Exception as e:
        logger.error(f"Error adding data point: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add data point: {str(e)}"
        )


@router.post("/data/{metric_key}/batch", response_model=dict)
async def add_multiple_data_points(
    metric_key: str,
    batch_data: AnomalyBatchDataPoints
):
    """
    Add multiple data points for anomaly detection.
    
    Args:
        metric_key: Unique identifier for the metric
        batch_data: Batch of data points to add
        
    Returns:
        Dict: Status message
    """
    try:
        # Convert to list of (timestamp, value) tuples
        data_points = [(point.timestamp, point.value) for point in batch_data.data_points]
        
        await anomaly_detector.add_multiple_data_points(
            metric_key=metric_key,
            data_points=data_points
        )
        
        return {
            "status": "success", 
            "message": f"Added {len(data_points)} data points"
        }
    
    except Exception as e:
        logger.error(f"Error adding batch data points: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add batch data points: {str(e)}"
        )


@router.get("/{metric_key}", response_model=AnomalyResponse)
async def get_anomalies_for_metric(metric_key: str):
    """
    Get detected anomalies for a specific metric.
    
    Args:
        metric_key: Unique identifier for the metric
        
    Returns:
        AnomalyResponse: Detected anomalies for the metric
    """
    try:
        result = await anomaly_detector.get_anomalies(metric_key)
        
        if result.get("status") == "not_found":
            raise HTTPException(
                status_code=404,
                detail=f"No anomalies found for metric: {metric_key}"
            )
        
        return result
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error getting anomalies: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get anomalies: {str(e)}"
        )


@router.get("/", response_model=AnomalyListResponse)
async def get_all_anomalies():
    """
    Get all detected anomalies across all metrics.
    
    Returns:
        AnomalyListResponse: All detected anomalies
    """
    try:
        result = await anomaly_detector.get_anomalies()
        return result
    
    except Exception as e:
        logger.error(f"Error getting all anomalies: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get all anomalies: {str(e)}"
        )


@router.post("/{metric_key}/detect", response_model=AnomalyResponse)
async def run_anomaly_detection(metric_key: str):
    """
    Run anomaly detection on the data for a specific metric.
    
    Args:
        metric_key: Unique identifier for the metric
        
    Returns:
        AnomalyResponse: Anomaly detection results
    """
    try:
        result = await anomaly_detector.detect_anomalies(metric_key)
        
        if result.get("status") == "error":
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Error running anomaly detection")
            )
        
        return result
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error running anomaly detection: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run anomaly detection: {str(e)}"
        ) 