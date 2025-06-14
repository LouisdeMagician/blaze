"""
Comprehensive liquidity analyzer for token analysis.
Combines multiple liquidity analysis components to provide a complete risk assessment.
"""
import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime

from src.dex.dex_aggregator import dex_aggregator
from src.dex.liquidity_history_tracker import liquidity_history_tracker
from src.dex.rugpull_detector import rugpull_detector
from src.dex.lp_token_tracker import lp_token_tracker
from src.models.risk_level import RiskLevel

logger = logging.getLogger(__name__)

class LiquidityAnalyzer:
    """Comprehensive liquidity analyzer that combines multiple analysis components."""
    
    def __init__(self):
        """Initialize the liquidity analyzer."""
        self.result_cache = {}
        self.result_cache_ttl = 1800  # 30 minutes
        self.result_cache_time = {}
    
    async def analyze_token_liquidity(self, token_address: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Perform comprehensive liquidity analysis for a token.
        
        Args:
            token_address: Token mint address
            force_refresh: Whether to force a refresh of the data
            
        Returns:
            Dict: Comprehensive liquidity analysis
        """
        # Check cache unless force refresh is requested
        now = time.time()
        if (not force_refresh and 
            token_address in self.result_cache and 
            now - self.result_cache_time.get(token_address, 0) < self.result_cache_ttl):
            return self.result_cache[token_address]
        
        try:
            # Get current liquidity data
            liquidity_data = await dex_aggregator.get_token_liquidity(token_address, force_refresh=force_refresh)
            
            # Ensure we have a historical record
            await liquidity_history_tracker.record_liquidity_snapshot(token_address)
            
            # Get rugpull risk analysis
            rugpull_risk = await rugpull_detector.analyze_rugpull_risk(token_address)
            
            # Get LP token risk analysis
            lp_token_risk = await lp_token_tracker.analyze_lp_token_risk(token_address)
            
            # Get liquidity change metrics
            change_metrics = await liquidity_history_tracker.get_liquidity_change_metrics(token_address, days=7)
            
            # Get liquidity anomalies
            anomalies = await liquidity_history_tracker.detect_liquidity_anomalies(token_address, days=30)
            
            # Combine all analyses into a comprehensive assessment
            comprehensive_analysis = self._combine_analyses(
                token_address,
                liquidity_data,
                rugpull_risk,
                lp_token_risk,
                change_metrics,
                anomalies
            )
            
            # Update cache
            self.result_cache[token_address] = comprehensive_analysis
            self.result_cache_time[token_address] = now
            
            return comprehensive_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing token liquidity for {token_address}: {e}", exc_info=True)
            return {
                "token_address": token_address,
                "overall_risk_level": "MEDIUM",  # Default to medium risk on error
                "error": str(e),
                "last_updated": int(time.time())
            }
    
    def _combine_analyses(
        self,
        token_address: str,
        liquidity_data: Dict[str, Any],
        rugpull_risk: Dict[str, Any],
        lp_token_risk: Dict[str, Any],
        change_metrics: Dict[str, Any],
        anomalies: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Combine multiple analyses into a comprehensive assessment.
        
        Args:
            token_address: Token mint address
            liquidity_data: Current liquidity data
            rugpull_risk: Rugpull risk analysis
            lp_token_risk: LP token risk analysis
            change_metrics: Liquidity change metrics
            anomalies: Detected liquidity anomalies
            
        Returns:
            Dict: Comprehensive liquidity analysis
        """
        # Extract risk levels
        rugpull_risk_level = RiskLevel[rugpull_risk.get("risk_level", "MEDIUM")]
        lp_token_risk_level = RiskLevel[lp_token_risk.get("risk_level", "MEDIUM")]
        
        # Determine overall risk level (take the highest risk level)
        overall_risk_level = max(rugpull_risk_level, lp_token_risk_level)
        
        # Calculate risk scores for each category
        risk_scores = {
            "rugpull_risk": rugpull_risk.get("risk_score", 0.5),
            "lp_token_risk": self._risk_level_to_score(lp_token_risk_level),
            "liquidity_volatility": min(1.0, change_metrics.get("liquidity_volatility", 0) / 50),  # Normalize to 0-1
            "anomaly_risk": min(1.0, anomalies.get("anomalies_detected", 0) / 5)  # More than 5 anomalies is max risk
        }
        
        # Calculate weighted overall risk score
        weights = {
            "rugpull_risk": 0.4,
            "lp_token_risk": 0.3,
            "liquidity_volatility": 0.15,
            "anomaly_risk": 0.15
        }
        
        overall_risk_score = sum(risk_scores[k] * weights[k] for k in weights)
        
        # Combine explanations
        explanations = []
        if "explanation" in rugpull_risk and rugpull_risk["explanation"]:
            explanations.append(rugpull_risk["explanation"])
        if "explanation" in lp_token_risk and lp_token_risk["explanation"]:
            explanations.append(lp_token_risk["explanation"])
        
        # Combine recommendations
        recommendations = []
        if "recommendations" in rugpull_risk:
            recommendations.extend(rugpull_risk["recommendations"])
        if "recommendations" in lp_token_risk:
            recommendations.extend(lp_token_risk["recommendations"])
        
        # Remove duplicates while preserving order
        unique_recommendations = []
        for rec in recommendations:
            if rec not in unique_recommendations:
                unique_recommendations.append(rec)
        
        # Build comprehensive analysis
        return {
            "token_address": token_address,
            "overall_risk_level": overall_risk_level.name,
            "overall_risk_score": overall_risk_score,
            "total_liquidity_usd": liquidity_data.get("total_liquidity_usd", 0),
            "price_usd": liquidity_data.get("price_usd"),
            "dex_breakdown": liquidity_data.get("dex_breakdown", {}),
            "pool_count": liquidity_data.get("total_pool_count", 0),
            "risk_breakdown": {
                "rugpull_risk": {
                    "level": rugpull_risk.get("risk_level"),
                    "score": rugpull_risk.get("risk_score", 0.5),
                    "factors": rugpull_risk.get("risk_factors", {})
                },
                "lp_token_risk": {
                    "level": lp_token_risk.get("risk_level"),
                    "locked_lp_count": lp_token_risk.get("locked_lp_count", 0),
                    "unlocked_lp_count": lp_token_risk.get("unlocked_lp_count", 0),
                    "average_locked_percentage": lp_token_risk.get("average_locked_percentage", 0),
                    "has_concentration_risk": lp_token_risk.get("has_concentration_risk", False)
                },
                "liquidity_change": {
                    "liquidity_change_percent_7d": change_metrics.get("liquidity_change_percent", 0),
                    "liquidity_volatility": change_metrics.get("liquidity_volatility", 0),
                    "liquidity_trend": change_metrics.get("liquidity_trend")
                },
                "anomalies": {
                    "anomalies_detected": anomalies.get("anomalies_detected", 0),
                    "recent_anomalies": anomalies.get("anomalies", [])[:3]  # Include only 3 most recent anomalies
                }
            },
            "explanation": " ".join(explanations),
            "recommendations": unique_recommendations,
            "data_sources": {
                "liquidity_data": True,
                "rugpull_risk": True,
                "lp_token_risk": True,
                "historical_data": bool(change_metrics and not change_metrics.get("insufficient_data", False)),
                "anomaly_detection": bool(anomalies and not anomalies.get("insufficient_data", False))
            },
            "last_updated": int(time.time())
        }
    
    def _risk_level_to_score(self, risk_level: RiskLevel) -> float:
        """
        Convert risk level to score.
        
        Args:
            risk_level: Risk level enum
            
        Returns:
            float: Risk score (0-1)
        """
        risk_scores = {
            RiskLevel.LOW: 0.2,
            RiskLevel.MEDIUM: 0.5,
            RiskLevel.HIGH: 0.8,
            RiskLevel.CRITICAL: 1.0
        }
        return risk_scores.get(risk_level, 0.5)
    
    async def get_historical_liquidity_chart_data(self, token_address: str, days: int = 30) -> Dict[str, Any]:
        """
        Get data for liquidity history chart.
        
        Args:
            token_address: Token mint address
            days: Number of days of history to retrieve
            
        Returns:
            Dict: Chart data
        """
        try:
            # Get historical data
            history = await liquidity_history_tracker.get_liquidity_history(token_address, days)
            
            if not history:
                return {
                    "token_address": token_address,
                    "days": days,
                    "error": "No historical data available",
                    "data_points": 0,
                    "series": []
                }
            
            # Sort by timestamp (oldest to newest)
            history.sort(key=lambda x: x.get("timestamp", 0))
            
            # Extract data for chart
            timestamps = []
            liquidity_values = []
            volume_values = []
            price_values = []
            
            for entry in history:
                if "timestamp" in entry:
                    # Convert timestamp to Unix timestamp in milliseconds for charting libraries
                    ts = int(entry["timestamp"].timestamp() * 1000) if isinstance(entry["timestamp"], datetime) else 0
                    if ts:
                        timestamps.append(ts)
                        liquidity_values.append(entry.get("total_liquidity_usd", 0))
                        volume_values.append(entry.get("total_volume_24h", 0))
                        price_values.append(entry.get("price_usd", 0))
            
            # Create chart series
            series = [
                {
                    "name": "Total Liquidity (USD)",
                    "data": [[timestamps[i], liquidity_values[i]] for i in range(len(timestamps))]
                }
            ]
            
            # Add volume series if we have volume data
            if any(v > 0 for v in volume_values):
                series.append({
                    "name": "24h Volume (USD)",
                    "data": [[timestamps[i], volume_values[i]] for i in range(len(timestamps))]
                })
            
            # Add price series if we have price data
            if any(p > 0 for p in price_values):
                series.append({
                    "name": "Price (USD)",
                    "data": [[timestamps[i], price_values[i]] for i in range(len(timestamps))]
                })
            
            return {
                "token_address": token_address,
                "days": days,
                "data_points": len(timestamps),
                "start_date": history[0].get("timestamp") if history else None,
                "end_date": history[-1].get("timestamp") if history else None,
                "series": series
            }
            
        except Exception as e:
            logger.error(f"Error getting historical liquidity chart data for {token_address}: {e}", exc_info=True)
            return {
                "token_address": token_address,
                "days": days,
                "error": str(e),
                "data_points": 0,
                "series": []
            }


# Initialize the analyzer
liquidity_analyzer = LiquidityAnalyzer() 