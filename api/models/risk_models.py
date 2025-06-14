"""
API models for risk classification.
"""
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field, validator
import time


class LiquidityData(BaseModel):
    """
    Model for liquidity-related risk data.
    """
    depth: Optional[float] = Field(None, description="Liquidity depth in USD")
    volatility: Optional[float] = Field(None, description="Liquidity volatility percentage")
    market_cap_to_liquidity_ratio: Optional[float] = Field(None, description="Market cap to liquidity ratio")
    is_locked: Optional[bool] = Field(None, description="Whether liquidity is locked")
    lock_duration_days: Optional[float] = Field(None, description="Duration of liquidity lock in days")


class OwnershipData(BaseModel):
    """
    Model for ownership-related risk data.
    """
    creator_percentage: Optional[float] = Field(None, description="Percentage owned by creator")
    top_holder_percentage: Optional[float] = Field(None, description="Percentage owned by top holders")
    gini_coefficient: Optional[float] = Field(None, description="Gini coefficient of token distribution")
    mint_authority_exists: Optional[bool] = Field(None, description="Whether mint authority exists")
    freeze_authority_exists: Optional[bool] = Field(None, description="Whether freeze authority exists")


class ContractData(BaseModel):
    """
    Model for contract-related risk data.
    """
    is_verified: Optional[bool] = Field(None, description="Whether contract is verified")
    has_proxy: Optional[bool] = Field(None, description="Whether contract uses proxy pattern")
    is_upgradeable: Optional[bool] = Field(None, description="Whether contract is upgradeable")
    has_high_fees: Optional[bool] = Field(None, description="Whether contract has high fees")
    has_honeypot_code: Optional[bool] = Field(None, description="Whether contract has honeypot patterns")


class TradingData(BaseModel):
    """
    Model for trading-related risk data.
    """
    volume_volatility: Optional[float] = Field(None, description="Trading volume volatility")
    price_volatility: Optional[float] = Field(None, description="Price volatility")
    wash_trading_score: Optional[float] = Field(None, description="Wash trading detection score")
    abnormal_tx_percentage: Optional[float] = Field(None, description="Percentage of abnormal transactions")
    manipulation_score: Optional[float] = Field(None, description="Market manipulation score")


class SocialData(BaseModel):
    """
    Model for social-related risk data.
    """
    age_days: Optional[float] = Field(None, description="Age of token in days")
    community_size: Optional[float] = Field(None, description="Size of the community")
    developer_activity: Optional[float] = Field(None, description="Level of developer activity")
    sentiment_score: Optional[float] = Field(None, description="Social sentiment score")
    reported_scam: Optional[bool] = Field(None, description="Whether token has been reported as scam")


class RiskAssessmentRequest(BaseModel):
    """
    Model for risk assessment request.
    """
    token_address: str = Field(..., description="Token address")
    force_refresh: Optional[bool] = Field(False, description="Force refresh of risk assessment")
    liquidity: Optional[LiquidityData] = Field(None, description="Liquidity-related risk data")
    ownership: Optional[OwnershipData] = Field(None, description="Ownership-related risk data")
    contract: Optional[ContractData] = Field(None, description="Contract-related risk data")
    trading: Optional[TradingData] = Field(None, description="Trading-related risk data")
    social: Optional[SocialData] = Field(None, description="Social-related risk data")


class RiskFactorImportance(BaseModel):
    """
    Model for risk factor importance.
    """
    factor: str = Field(..., description="Risk factor name")
    importance: float = Field(..., description="Importance score")


class RiskCategoryScore(BaseModel):
    """
    Model for risk category score.
    """
    category: str = Field(..., description="Risk category name")
    score: float = Field(..., description="Risk score")
    factors: List[RiskFactorImportance] = Field(..., description="Risk factors")


class TrendAdjustment(BaseModel):
    """
    Model for trend-based risk adjustment.
    """
    factor: str = Field(..., description="Adjustment factor")
    adjustment: float = Field(..., description="Adjustment value")
    explanation: str = Field(..., description="Explanation of adjustment")


class PeerComparison(BaseModel):
    """
    Model for peer comparison data.
    """
    percentile: Dict[str, float] = Field(..., description="Risk percentile by category")
    relative_risk: Dict[str, str] = Field(..., description="Relative risk description by category")


class RiskAssessmentResponse(BaseModel):
    """
    Model for risk assessment response.
    """
    token_address: str = Field(..., description="Token address")
    timestamp: float = Field(..., description="Timestamp of assessment")
    status: Optional[str] = Field(None, description="Status (error, not_found)")
    error: Optional[str] = Field(None, description="Error message if status is error")
    message: Optional[str] = Field(None, description="Message if status is not_found")
    composite_score: Optional[float] = Field(None, description="Composite risk score")
    risk_level: Optional[str] = Field(None, description="Risk level (low, medium, high, very high)")
    category_scores: Optional[Dict[str, float]] = Field(None, description="Risk scores by category")
    risk_factors: Optional[Dict[str, Dict[str, float]]] = Field(None, description="Normalized risk factors")
    feature_importance: Optional[Dict[str, Dict[str, float]]] = Field(None, description="Feature importance by category")
    explanations: Optional[Dict[str, List[str]]] = Field(None, description="Explanations by category")
    trend_adjustments: Optional[List[Dict[str, Any]]] = Field(None, description="Trend-based adjustments")
    peer_comparison: Optional[Dict[str, Any]] = Field(None, description="Peer comparison data")


class RiskComparisonRequest(BaseModel):
    """
    Model for risk comparison request.
    """
    token_addresses: List[str] = Field(..., description="List of token addresses to compare")


class BenchmarkUpdateRequest(BaseModel):
    """
    Model for benchmark data update request.
    """
    benchmark_data: Dict[str, List[float]] = Field(
        ...,
        description="Benchmark data with risk scores for different categories"
    ) 