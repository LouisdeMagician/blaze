"""
Pydantic models for trading pattern analysis API.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, AnyHttpUrl


class TradingAnalysisRequest(BaseModel):
    """Request model for trading pattern analysis."""
    token_address: str = Field(..., description="Token mint address to analyze")
    force_refresh: bool = Field(False, description="Force refresh of analysis")
    analysis_components: Optional[List[str]] = Field(
        None, 
        description="Components to analyze (if not specified, all components will be analyzed)"
    )


class TradePatternAnalysisResult(BaseModel):
    """Result model for trading pattern analysis."""
    token_address: str = Field(..., description="Token mint address")
    suspicious_patterns_detected: bool = Field(..., description="Whether suspicious patterns were detected")
    detected_patterns: List[Dict[str, Any]] = Field([], description="List of detected patterns")
    confidence_score: float = Field(..., description="Confidence score of the analysis (0-1)")
    risk_level: str = Field(..., description="Risk level assessment")
    risk_factors: Dict[str, float] = Field({}, description="Risk factors with scores")
    analysis_confidence: str = Field(..., description="Confidence level of the analysis (LOW, MEDIUM, HIGH)")
    explanation: str = Field(..., description="Human-readable explanation")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "suspicious_patterns_detected": True,
                "detected_patterns": [
                    {
                        "type": "cyclic_transactions",
                        "confidence": 0.85,
                        "details": {
                            "affected_wallets": 3,
                            "cycle_count": 12
                        }
                    }
                ],
                "confidence_score": 0.85,
                "risk_level": "HIGH",
                "risk_factors": {
                    "cyclic_transactions": 0.85,
                    "unusual_timing": 0.7
                },
                "analysis_confidence": "MEDIUM",
                "explanation": "Detected cyclic transaction patterns among 3 wallets",
                "timestamp": "2023-04-15T12:30:45.123456"
            }
        }


class WashTradingAnalysisResult(BaseModel):
    """Result model for wash trading analysis."""
    token_address: str = Field(..., description="Token mint address")
    wash_trading_detected: bool = Field(..., description="Whether wash trading was detected")
    wash_volume_percentage: float = Field(..., description="Estimated percentage of wash trading volume")
    suspected_wash_trading_wallets: List[Dict[str, Any]] = Field([], description="List of wallets suspected of wash trading")
    circular_trades_detected: bool = Field(..., description="Whether circular trades were detected")
    risk_level: str = Field(..., description="Risk level assessment")
    risk_factors: Dict[str, float] = Field({}, description="Risk factors with scores")
    confidence_score: float = Field(..., description="Confidence score of the analysis (0-1)")
    analysis_confidence: str = Field(..., description="Confidence level of the analysis (LOW, MEDIUM, HIGH)")
    explanation: str = Field(..., description="Human-readable explanation")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "wash_trading_detected": True,
                "wash_volume_percentage": 35.2,
                "suspected_wash_trading_wallets": [
                    {
                        "address": "Wallet1Address",
                        "confidence": 0.9,
                        "volume": 15000
                    }
                ],
                "circular_trades_detected": True,
                "risk_level": "HIGH",
                "risk_factors": {
                    "circular_trades": 0.9,
                    "self_trades": 0.7
                },
                "confidence_score": 0.85,
                "analysis_confidence": "MEDIUM",
                "explanation": "Detected significant wash trading activity",
                "timestamp": "2023-04-15T12:30:45.123456"
            }
        }


class PumpDumpAnalysisResult(BaseModel):
    """Result model for pump and dump analysis."""
    token_address: str = Field(..., description="Token mint address")
    pump_dump_patterns_detected: bool = Field(..., description="Whether pump and dump patterns were detected")
    historical_patterns: List[Dict[str, Any]] = Field([], description="List of historical pump and dump patterns")
    current_phase: str = Field(..., description="Current phase if in a pump and dump cycle")
    price_volatility: float = Field(..., description="Price volatility score")
    volume_spikes: List[Dict[str, Any]] = Field([], description="List of volume spikes")
    risk_level: str = Field(..., description="Risk level assessment")
    risk_factors: Dict[str, float] = Field({}, description="Risk factors with scores")
    confidence_score: float = Field(..., description="Confidence score of the analysis (0-1)")
    analysis_confidence: str = Field(..., description="Confidence level of the analysis (LOW, MEDIUM, HIGH)")
    explanation: str = Field(..., description="Human-readable explanation")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "pump_dump_patterns_detected": True,
                "historical_patterns": [
                    {
                        "start_date": "2023-03-01T00:00:00",
                        "end_date": "2023-03-05T00:00:00",
                        "price_increase": 250.5,
                        "price_decrease": 80.2,
                        "volume_increase": 500.0
                    }
                ],
                "current_phase": "ACCUMULATION",
                "price_volatility": 0.85,
                "volume_spikes": [
                    {
                        "date": "2023-04-10T12:00:00",
                        "volume_increase": 350.2,
                        "duration_hours": 4
                    }
                ],
                "risk_level": "HIGH",
                "risk_factors": {
                    "extreme_price_volatility": 0.85,
                    "coordinated_buy_activity": 0.75
                },
                "confidence_score": 0.8,
                "analysis_confidence": "MEDIUM",
                "explanation": "Detected classic pump and dump pattern",
                "timestamp": "2023-04-15T12:30:45.123456"
            }
        }


class MarketManipulationAnalysisResult(BaseModel):
    """Result model for market manipulation analysis."""
    token_address: str = Field(..., description="Token mint address")
    manipulation_detected: bool = Field(..., description="Whether market manipulation was detected")
    patterns: List[Dict[str, Any]] = Field([], description="List of detected manipulation patterns")
    risk_level: str = Field(..., description="Risk level assessment")
    risk_factors: Dict[str, float] = Field({}, description="Risk factors with scores")
    analysis_confidence: str = Field(..., description="Confidence level of the analysis (LOW, MEDIUM, HIGH)")
    explanation: str = Field(..., description="Human-readable explanation")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "manipulation_detected": True,
                "patterns": [
                    {
                        "type": "spoofing",
                        "confidence": 0.8,
                        "details": {
                            "suspicious_wallets": 2
                        }
                    },
                    {
                        "type": "layering",
                        "confidence": 0.75,
                        "details": {
                            "price_levels": 5
                        }
                    }
                ],
                "risk_level": "HIGH",
                "risk_factors": {
                    "spoofing_detected": 0.8,
                    "layering_detected": 0.75
                },
                "analysis_confidence": "MEDIUM",
                "explanation": "Detected spoofing and layering patterns",
                "timestamp": "2023-04-15T12:30:45.123456"
            }
        }


class VolumeAnalysisResult(BaseModel):
    """Result model for volume analysis."""
    token_address: str = Field(..., description="Token mint address")
    normalized_volume: Dict[str, Any] = Field(..., description="Normalized volume metrics")
    trend_analysis: Dict[str, Any] = Field(..., description="Volume trend analysis")
    unusual_volume: Dict[str, Any] = Field(..., description="Unusual volume detection")
    pressure_analysis: Dict[str, Any] = Field(..., description="Buy/sell pressure analysis")
    risk_level: str = Field(..., description="Risk level assessment")
    risk_factors: Dict[str, float] = Field({}, description="Risk factors with scores")
    analysis_confidence: str = Field(..., description="Confidence level of the analysis (LOW, MEDIUM, HIGH)")
    explanation: str = Field(..., description="Human-readable explanation")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "normalized_volume": {
                    "avg_daily_volume": 50000,
                    "avg_daily_tx_count": 120,
                    "avg_tx_size": 416.67,
                    "volume_volatility": 0.45,
                    "tx_count_volatility": 0.25,
                    "data_points": 14
                },
                "trend_analysis": {
                    "trend": "INCREASING",
                    "trend_strength": 0.65,
                    "volume_change_percentage": 65.0,
                    "has_significant_trend": True
                },
                "unusual_volume": {
                    "unusual_volume_detected": True,
                    "unusual_volume_days": [
                        {
                            "timestamp": "2023-04-10T00:00:00",
                            "volume": 150000,
                            "volume_ratio": 3.5
                        }
                    ],
                    "max_volume_ratio": 3.5
                },
                "pressure_analysis": {
                    "buy_sell_ratio": 1.5,
                    "net_buy_volume": 20000,
                    "buy_percentage": 60,
                    "sell_percentage": 40,
                    "pressure_direction": "BUY",
                    "pressure_strength": 0.2
                },
                "risk_level": "MEDIUM",
                "risk_factors": {
                    "moderate_volume_volatility": 0.45,
                    "significant_volume_spikes": 0.6
                },
                "analysis_confidence": "HIGH",
                "explanation": "Trading volume is increasing (65.0% change) | Detected 1 day(s) with unusual volume spikes (up to 3.5x normal volume) | Buy pressure dominates (60.0% buys vs 40.0% sells) | Volume shows moderate volatility (0.45)",
                "timestamp": "2023-04-15T12:30:45.123456"
            }
        }


class TradingAnalysisResponse(BaseModel):
    """Complete response model for trading pattern analysis."""
    token_address: str = Field(..., description="Token mint address")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    pattern_analysis: Optional[TradePatternAnalysisResult] = Field(None, description="Trading pattern analysis")
    wash_trading: Optional[WashTradingAnalysisResult] = Field(None, description="Wash trading analysis")
    pump_dump: Optional[PumpDumpAnalysisResult] = Field(None, description="Pump and dump analysis")
    market_manipulation: Optional[MarketManipulationAnalysisResult] = Field(None, description="Market manipulation analysis")
    volume_analysis: Optional[VolumeAnalysisResult] = Field(None, description="Volume analysis")
    
    class Config:
        schema_extra = {
            "example": {
                "token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "timestamp": "2023-04-15T12:30:45.123456",
                "pattern_analysis": {
                    "token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "suspicious_patterns_detected": True,
                    "detected_patterns": [
                        {
                            "type": "cyclic_transactions",
                            "confidence": 0.85,
                            "details": {
                                "affected_wallets": 3,
                                "cycle_count": 12
                            }
                        }
                    ],
                    "confidence_score": 0.85,
                    "risk_level": "HIGH",
                    "risk_factors": {
                        "cyclic_transactions": 0.85,
                        "unusual_timing": 0.7
                    },
                    "analysis_confidence": "MEDIUM",
                    "explanation": "Detected cyclic transaction patterns among 3 wallets",
                    "timestamp": "2023-04-15T12:30:45.123456"
                },
                "wash_trading": {
                    "token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "wash_trading_detected": True,
                    "wash_volume_percentage": 35.2,
                    "suspected_wash_trading_wallets": [
                        {
                            "address": "Wallet1Address",
                            "confidence": 0.9,
                            "volume": 15000
                        }
                    ],
                    "circular_trades_detected": True,
                    "risk_level": "HIGH",
                    "risk_factors": {
                        "circular_trades": 0.9,
                        "self_trades": 0.7
                    },
                    "confidence_score": 0.85,
                    "analysis_confidence": "MEDIUM",
                    "explanation": "Detected significant wash trading activity",
                    "timestamp": "2023-04-15T12:30:45.123456"
                },
                "market_manipulation": {
                    "token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "manipulation_detected": True,
                    "patterns": [
                        {
                            "type": "spoofing",
                            "confidence": 0.8,
                            "details": {
                                "suspicious_wallets": 2
                            }
                        }
                    ],
                    "risk_level": "HIGH",
                    "risk_factors": {
                        "spoofing_detected": 0.8
                    },
                    "analysis_confidence": "MEDIUM",
                    "explanation": "Detected spoofing patterns",
                    "timestamp": "2023-04-15T12:30:45.123456"
                },
                "volume_analysis": {
                    "token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "normalized_volume": {
                        "avg_daily_volume": 50000,
                        "avg_daily_tx_count": 120,
                        "avg_tx_size": 416.67,
                        "volume_volatility": 0.45
                    },
                    "trend_analysis": {
                        "trend": "INCREASING",
                        "trend_strength": 0.65,
                        "volume_change_percentage": 65.0
                    },
                    "unusual_volume": {
                        "unusual_volume_detected": True,
                        "max_volume_ratio": 3.5
                    },
                    "pressure_analysis": {
                        "buy_sell_ratio": 1.5,
                        "pressure_direction": "BUY"
                    },
                    "risk_level": "MEDIUM",
                    "risk_factors": {
                        "moderate_volume_volatility": 0.45
                    },
                    "analysis_confidence": "HIGH",
                    "explanation": "Trading volume is increasing with moderate volatility",
                    "timestamp": "2023-04-15T12:30:45.123456"
                }
            }
        }


class AnalysisStatusResponse(BaseModel):
    """Response model for analysis status."""
    analysis_id: str = Field(..., description="Analysis ID")
    status: str = Field(..., description="Analysis status (queued, in_progress, completed, failed, partial)")
    token_address: str = Field(..., description="Token mint address")
    message: str = Field(..., description="Status message")
    error: Optional[str] = Field(None, description="Error message if analysis failed")
    components_status: Optional[Dict[str, str]] = Field(None, description="Status of individual analysis components")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when analysis completed")
    estimated_time_seconds: int = Field(0, description="Estimated time to completion in seconds")
    
    class Config:
        schema_extra = {
            "example": {
                "analysis_id": "trading_EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v_1681563045",
                "status": "in_progress",
                "token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "message": "Analysis is in_progress",
                "components_status": {
                    "transaction_tracking": "completed",
                    "pattern_analysis": "in_progress",
                    "wash_trading": "pending",
                    "pump_dump": "pending",
                    "market_manipulation": "pending",
                    "volume_analysis": "pending"
                },
                "estimated_time_seconds": 45
            }
        }


class WebhookRegistrationRequest(BaseModel):
    """Request model for webhook registration."""
    callback_url: AnyHttpUrl = Field(..., description="URL to call when events occur")
    event_types: List[str] = Field(..., description="Event types to subscribe to")
    token_addresses: Optional[List[str]] = Field(None, description="Token addresses to monitor (null for all)")
    description: Optional[str] = Field(None, description="Description of this webhook") 