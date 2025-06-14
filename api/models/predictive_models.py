"""
API models for predictive analytics.
"""
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field, validator
import time


class PriceDataPoint(BaseModel):
    """
    Model for a historical price data point.
    """
    timestamp: float = Field(..., description="Timestamp in seconds since epoch")
    price: float = Field(..., description="Price value")
    volume: Optional[float] = Field(None, description="Trading volume")
    market_cap: Optional[float] = Field(None, description="Market capitalization")


class LiquidityDataPoint(BaseModel):
    """
    Model for a historical liquidity data point.
    """
    timestamp: float = Field(..., description="Timestamp in seconds since epoch")
    liquidity: float = Field(..., description="Liquidity value")
    depth: Optional[float] = Field(None, description="Liquidity depth")
    volatility: Optional[float] = Field(None, description="Liquidity volatility")


class RiskDataPoint(BaseModel):
    """
    Model for a historical risk data point.
    """
    timestamp: float = Field(..., description="Timestamp in seconds since epoch")
    risk_score: float = Field(..., description="Overall risk score")
    liquidity_risk: Optional[float] = Field(None, description="Liquidity risk score")
    ownership_risk: Optional[float] = Field(None, description="Ownership risk score")
    contract_risk: Optional[float] = Field(None, description="Contract risk score")
    trading_risk: Optional[float] = Field(None, description="Trading risk score")


class HolderDataPoint(BaseModel):
    """
    Model for a historical holder data point.
    """
    timestamp: float = Field(..., description="Timestamp in seconds since epoch")
    holder_count: int = Field(..., description="Number of holders")
    concentration: Optional[float] = Field(None, description="Token concentration")
    new_holders: Optional[int] = Field(None, description="New holders in period")
    departed_holders: Optional[int] = Field(None, description="Holders who left in period")


class PredictionPoint(BaseModel):
    """
    Model for a prediction point.
    """
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    value: float = Field(..., description="Predicted value")
    lower_bound: Optional[float] = Field(None, description="Lower confidence bound")
    upper_bound: Optional[float] = Field(None, description="Upper confidence bound")


class PriceTrajectoryRequest(BaseModel):
    """
    Model for price trajectory prediction request.
    """
    token_address: str = Field(..., description="Token address")
    historical_data: List[PriceDataPoint] = Field(..., description="Historical price data")
    horizon_days: Optional[int] = Field(7, description="Forecast horizon in days")


class ConfidenceInterval(BaseModel):
    """
    Model for confidence interval.
    """
    lower: List[float] = Field(..., description="Lower bound values")
    upper: List[float] = Field(..., description="Upper bound values")


class PredictionModels(BaseModel):
    """
    Model for individual prediction model outputs.
    """
    arima: Optional[List[float]] = Field(None, description="ARIMA model predictions")
    exponential_smoothing: Optional[List[float]] = Field(None, description="Exponential smoothing predictions")
    linear_regression: Optional[List[float]] = Field(None, description="Linear regression predictions")


class PredictionData(BaseModel):
    """
    Model for prediction data.
    """
    dates: List[str] = Field(..., description="Prediction dates")
    values: List[float] = Field(..., description="Predicted values")
    models: Optional[PredictionModels] = Field(None, description="Individual model predictions")


class QualityMetrics(BaseModel):
    """
    Model for prediction quality metrics.
    """
    historical_volatility: float = Field(..., description="Historical volatility")
    prediction_volatility: float = Field(..., description="Prediction volatility")
    trend_strength: float = Field(..., description="Trend strength correlation")
    confidence_score: float = Field(..., description="Overall confidence score")


class PriceTrajectoryResponse(BaseModel):
    """
    Model for price trajectory prediction response.
    """
    token_address: str = Field(..., description="Token address")
    timestamp: float = Field(default_factory=time.time, description="Timestamp of prediction")
    status: Optional[str] = Field(None, description="Status (e.g., error, insufficient_data)")
    message: Optional[str] = Field(None, description="Status message")
    horizon_days: Optional[int] = Field(None, description="Forecast horizon in days")
    prediction: Optional[PredictionData] = Field(None, description="Prediction data")
    confidence_intervals: Optional[Dict[str, ConfidenceInterval]] = Field(None, description="Confidence intervals")
    quality_metrics: Optional[QualityMetrics] = Field(None, description="Prediction quality metrics")
    data_points_used: Optional[int] = Field(None, description="Number of data points used")


class LiquidityChangeRequest(BaseModel):
    """
    Model for liquidity change forecast request.
    """
    token_address: str = Field(..., description="Token address")
    historical_data: List[LiquidityDataPoint] = Field(..., description="Historical liquidity data")
    horizon_days: Optional[int] = Field(7, description="Forecast horizon in days")


class StressEvent(BaseModel):
    """
    Model for liquidity stress event.
    """
    day: int = Field(..., description="Day number in the forecast")
    date: str = Field(..., description="Date of the event")
    expected_change: float = Field(..., description="Expected liquidity change")
    severity: str = Field(..., description="Severity (high, medium)")
    estimated_impact: str = Field(..., description="Estimated impact description")


class LiquidityChangeResponse(BaseModel):
    """
    Model for liquidity change forecast response.
    """
    token_address: str = Field(..., description="Token address")
    timestamp: float = Field(default_factory=time.time, description="Timestamp of prediction")
    status: Optional[str] = Field(None, description="Status (e.g., error, insufficient_data)")
    message: Optional[str] = Field(None, description="Status message")
    horizon_days: Optional[int] = Field(None, description="Forecast horizon in days")
    prediction: Optional[PredictionData] = Field(None, description="Prediction data")
    confidence_intervals: Optional[Dict[str, ConfidenceInterval]] = Field(None, description="Confidence intervals")
    stress_events: Optional[List[StressEvent]] = Field(None, description="Potential stress events")
    data_points_used: Optional[int] = Field(None, description="Number of data points used")


class RiskTrendRequest(BaseModel):
    """
    Model for risk trend prediction request.
    """
    token_address: str = Field(..., description="Token address")
    historical_data: List[RiskDataPoint] = Field(..., description="Historical risk data")
    horizon_days: Optional[int] = Field(7, description="Forecast horizon in days")


class TrendReversal(BaseModel):
    """
    Model for trend reversal event.
    """
    day: int = Field(..., description="Day number in the forecast")
    date: str = Field(..., description="Date of the event")
    trend_before: str = Field(..., description="Trend before reversal")
    trend_after: str = Field(..., description="Trend after reversal")
    confidence: float = Field(..., description="Confidence in the reversal")


class RiskTrendResponse(BaseModel):
    """
    Model for risk trend prediction response.
    """
    token_address: str = Field(..., description="Token address")
    timestamp: float = Field(default_factory=time.time, description="Timestamp of prediction")
    status: Optional[str] = Field(None, description="Status (e.g., error, insufficient_data)")
    message: Optional[str] = Field(None, description="Status message")
    horizon_days: Optional[int] = Field(None, description="Forecast horizon in days")
    prediction: Optional[PredictionData] = Field(None, description="Prediction data")
    trend_reversals: Optional[List[TrendReversal]] = Field(None, description="Potential trend reversals")
    data_points_used: Optional[int] = Field(None, description="Number of data points used")


class MarketImpactRequest(BaseModel):
    """
    Model for market impact estimation request.
    """
    token_address: str = Field(..., description="Token address")
    order_size: float = Field(..., description="Order size in token units")
    historical_data: List[Union[PriceDataPoint, LiquidityDataPoint]] = Field(..., description="Historical price and liquidity data")


class PriceImpact(BaseModel):
    """
    Model for price impact estimation.
    """
    expected_impact_percent: float = Field(..., description="Expected price impact as percentage")
    confidence_interval: Optional[List[float]] = Field(None, description="Confidence interval for impact")
    impact_decay_minutes: Optional[float] = Field(None, description="Expected time for impact to decay")


class SlippageEstimation(BaseModel):
    """
    Model for slippage estimation.
    """
    expected_slippage_percent: float = Field(..., description="Expected slippage as percentage")
    confidence_interval: Optional[List[float]] = Field(None, description="Confidence interval for slippage")
    execution_quality: str = Field(..., description="Execution quality assessment")


class MarketResilience(BaseModel):
    """
    Model for market resilience estimation.
    """
    resilience_score: float = Field(..., description="Market resilience score (0-1)")
    recovery_time_minutes: Optional[float] = Field(None, description="Expected recovery time in minutes")
    liquidity_fragility: str = Field(..., description="Liquidity fragility assessment")


class MarketImpactResponse(BaseModel):
    """
    Model for market impact estimation response.
    """
    token_address: str = Field(..., description="Token address")
    timestamp: float = Field(default_factory=time.time, description="Timestamp of estimation")
    status: Optional[str] = Field(None, description="Status (e.g., error, insufficient_data)")
    message: Optional[str] = Field(None, description="Status message")
    order_size: float = Field(..., description="Order size in token units")
    price_impact: Optional[PriceImpact] = Field(None, description="Price impact estimation")
    slippage: Optional[SlippageEstimation] = Field(None, description="Slippage estimation")
    resilience: Optional[MarketResilience] = Field(None, description="Market resilience estimation")
    data_points_used: Optional[int] = Field(None, description="Number of data points used")


class HolderBehaviorRequest(BaseModel):
    """
    Model for holder behavior prediction request.
    """
    token_address: str = Field(..., description="Token address")
    historical_data: List[HolderDataPoint] = Field(..., description="Historical holder data")
    horizon_days: Optional[int] = Field(7, description="Forecast horizon in days")


class HoldTimePrediction(BaseModel):
    """
    Model for hold time prediction.
    """
    average_hold_days: float = Field(..., description="Average hold time in days")
    distribution: Dict[str, float] = Field(..., description="Hold time distribution")
    trend: str = Field(..., description="Hold time trend")


class SellProbability(BaseModel):
    """
    Model for sell probability prediction.
    """
    next_day: float = Field(..., description="Sell probability for next day")
    next_week: float = Field(..., description="Sell probability for next week")
    next_month: float = Field(..., description="Sell probability for next month")
    distribution: Dict[str, float] = Field(..., description="Sell probability distribution")


class LoyaltyScores(BaseModel):
    """
    Model for loyalty scores prediction.
    """
    average_score: float = Field(..., description="Average loyalty score")
    distribution: Dict[str, float] = Field(..., description="Loyalty score distribution")
    trend: str = Field(..., description="Loyalty score trend")


class HolderBehaviorResponse(BaseModel):
    """
    Model for holder behavior prediction response.
    """
    token_address: str = Field(..., description="Token address")
    timestamp: float = Field(default_factory=time.time, description="Timestamp of prediction")
    status: Optional[str] = Field(None, description="Status (e.g., error, insufficient_data)")
    message: Optional[str] = Field(None, description="Status message")
    horizon_days: Optional[int] = Field(None, description="Forecast horizon in days")
    hold_time_prediction: Optional[HoldTimePrediction] = Field(None, description="Hold time prediction")
    sell_probability: Optional[SellProbability] = Field(None, description="Sell probability prediction")
    loyalty_scores: Optional[LoyaltyScores] = Field(None, description="Loyalty scores prediction")
    data_points_used: Optional[int] = Field(None, description="Number of data points used") 