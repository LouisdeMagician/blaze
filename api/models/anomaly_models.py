"""
API models for anomaly detection.
"""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, validator
import time


class AnomalyDataPoint(BaseModel):
    """
    Model for a single data point for anomaly detection.
    """
    value: float = Field(..., description="The value of the data point")
    timestamp: Optional[float] = Field(
        None, 
        description="Timestamp of the data point (defaults to current time)"
    )
    
    @validator("timestamp", pre=True, always=True)
    def set_timestamp(cls, v):
        """Set timestamp to current time if not provided."""
        return v or time.time()


class AnomalyBatchDataPoints(BaseModel):
    """
    Model for batch data points for anomaly detection.
    """
    data_points: List[AnomalyDataPoint] = Field(
        ...,
        description="List of data points",
        min_items=1
    )


class AnomalyInfo(BaseModel):
    """
    Model for information about a detected anomaly.
    """
    timestamp: float = Field(..., description="Timestamp of the anomaly")
    value: float = Field(..., description="Value that triggered the anomaly")
    detection_methods: List[str] = Field(
        ...,
        description="List of methods that detected the anomaly"
    )
    confidence_score: float = Field(
        ...,
        description="Confidence score (0-1) of the anomaly detection"
    )
    confidence_level: str = Field(
        ...,
        description="Confidence level (very low, low, medium, high, very high)"
    )


class AnomalyResponse(BaseModel):
    """
    Model for the response from anomaly detection.
    """
    status: str = Field(..., description="Status of the operation")
    metric: Optional[str] = Field(None, description="Metric key")
    message: Optional[str] = Field(None, description="Optional status message")
    anomalies: Optional[List[AnomalyInfo]] = Field(
        None,
        description="List of detected anomalies"
    )


class AnomalyMetricData(BaseModel):
    """
    Model for anomaly data for a specific metric.
    """
    metric: str = Field(..., description="Metric key")
    anomalies: List[AnomalyInfo] = Field(..., description="List of detected anomalies")


class AnomalyListResponse(BaseModel):
    """
    Model for the response containing all anomalies across metrics.
    """
    status: str = Field(..., description="Status of the operation")
    metrics: Optional[Dict[str, AnomalyResponse]] = Field(
        None,
        description="Dictionary of metrics with their anomalies"
    )
    message: Optional[str] = Field(None, description="Optional status message") 