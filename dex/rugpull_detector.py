"""
Rugpull risk detector for liquidity analysis.
Analyzes liquidity patterns and contract features to identify potential rugpull risks.
"""
import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta

from src.dex.dex_aggregator import dex_aggregator
from src.dex.liquidity_history_tracker import liquidity_history_tracker
from src.blockchain.solana_client import solana_client, SolanaClientError
from src.models.risk_level import RiskLevel

logger = logging.getLogger(__name__)

class RugpullDetector:
    """Detects rugpull risks based on liquidity analysis."""
    
    def __init__(self):
        """Initialize the rugpull detector."""
        self.high_risk_threshold = 0.7  # 70% score is high risk
        self.critical_risk_threshold = 0.85  # 85% score is critical risk
    
    async def analyze_rugpull_risk(self, token_address: str) -> Dict[str, Any]:
        """
        Analyze rugpull risk for a token.
        
        Args:
            token_address: Token mint address
            
        Returns:
            Dict: Rugpull risk analysis
        """
        try:
            # Get current liquidity data
            liquidity_data = await dex_aggregator.get_token_liquidity(token_address, force_refresh=False)
            
            # Get historical liquidity data
            historical_data = await liquidity_history_tracker.get_liquidity_history(token_address, days=30)
            
            # Get liquidity change metrics
            change_metrics = await liquidity_history_tracker.get_liquidity_change_metrics(token_address, days=7)
            
            # Get liquidity anomalies
            anomalies = await liquidity_history_tracker.detect_liquidity_anomalies(token_address, days=30)
            
            # Identify risk factors
            risk_factors = await self._identify_risk_factors(
                token_address, 
                liquidity_data, 
                historical_data, 
                change_metrics, 
                anomalies
            )
            
            # Calculate overall risk score
            risk_score = self._calculate_risk_score(risk_factors)
            
            # Determine risk level
            risk_level = self._determine_risk_level(risk_score)
            
            # Generate explanation
            explanation = self._generate_explanation(risk_factors, risk_score, liquidity_data)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(risk_factors, risk_score, liquidity_data)
            
            return {
                "token_address": token_address,
                "risk_score": risk_score,
                "risk_level": risk_level.name,
                "risk_factors": risk_factors,
                "explanation": explanation,
                "recommendations": recommendations,
                "total_liquidity_usd": liquidity_data.get("total_liquidity_usd", 0),
                "price_usd": liquidity_data.get("price_usd"),
                "liquidity_concentration": liquidity_data.get("liquidity_concentration", {}),
                "liquidity_change_7d": change_metrics.get("liquidity_change_percent", 0),
                "anomalies_detected": anomalies.get("anomalies_detected", 0),
                "last_updated": int(time.time())
            }
            
        except Exception as e:
            logger.error(f"Error analyzing rugpull risk for {token_address}: {e}", exc_info=True)
            return {
                "token_address": token_address,
                "risk_score": 0.5,  # Default to medium risk on error
                "risk_level": "MEDIUM",
                "error": str(e),
                "last_updated": int(time.time())
            }
    
    async def _identify_risk_factors(
        self, 
        token_address: str, 
        liquidity_data: Dict[str, Any], 
        historical_data: List[Dict[str, Any]], 
        change_metrics: Dict[str, Any], 
        anomalies: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Identify rugpull risk factors.
        
        Args:
            token_address: Token mint address
            liquidity_data: Current liquidity data
            historical_data: Historical liquidity data
            change_metrics: Liquidity change metrics
            anomalies: Detected liquidity anomalies
            
        Returns:
            Dict[str, float]: Risk factors with scores (0-1)
        """
        risk_factors = {}
        
        # Check if there's sufficient data
        if not liquidity_data or liquidity_data.get("total_liquidity_usd", 0) == 0:
            risk_factors["no_liquidity"] = 1.0
            return risk_factors
        
        # 1. Low liquidity risk
        total_liquidity = liquidity_data.get("total_liquidity_usd", 0)
        if total_liquidity < 5000:
            risk_factors["extremely_low_liquidity"] = 1.0
        elif total_liquidity < 20000:
            risk_factors["very_low_liquidity"] = 0.8
        elif total_liquidity < 100000:
            risk_factors["low_liquidity"] = 0.5
        
        # 2. Liquidity concentration risk
        concentration = liquidity_data.get("liquidity_concentration", {}).get("overall_concentration", 0)
        if concentration > 0.95:
            risk_factors["extreme_liquidity_concentration"] = 1.0
        elif concentration > 0.8:
            risk_factors["high_liquidity_concentration"] = 0.7
        
        # 3. Liquidity/Market Cap ratio risk (if price data is available)
        if liquidity_data.get("price_usd") and "market_cap" in liquidity_data:
            market_cap = liquidity_data.get("market_cap", 0)
            if market_cap > 0:
                liquidity_ratio = total_liquidity / market_cap
                if liquidity_ratio < 0.02:  # Less than 2% of market cap in liquidity
                    risk_factors["extremely_low_liquidity_ratio"] = 0.9
                elif liquidity_ratio < 0.05:  # Less than 5% of market cap in liquidity
                    risk_factors["low_liquidity_ratio"] = 0.6
        
        # 4. Recent liquidity changes
        liquidity_change = change_metrics.get("liquidity_change_percent", 0)
        if liquidity_change < -30:  # More than 30% decrease
            risk_factors["significant_liquidity_decrease"] = 0.8
        elif liquidity_change < -15:  # More than 15% decrease
            risk_factors["moderate_liquidity_decrease"] = 0.5
        
        # 5. Liquidity volatility
        volatility = change_metrics.get("liquidity_volatility", 0)
        if volatility > 30:  # Very high volatility
            risk_factors["extreme_liquidity_volatility"] = 0.8
        elif volatility > 15:  # High volatility
            risk_factors["high_liquidity_volatility"] = 0.5
        
        # 6. Recent anomalies
        recent_anomalies = anomalies.get("anomalies", [])
        drop_anomalies = [a for a in recent_anomalies if a.get("type") in ["drop", "sudden_decrease"]]
        if drop_anomalies:
            # Calculate the average size of drops
            avg_drop = sum(abs(a.get("percent_change", 0)) for a in drop_anomalies) / len(drop_anomalies)
            if avg_drop > 40:
                risk_factors["severe_liquidity_drops"] = 0.9
            elif avg_drop > 20:
                risk_factors["significant_liquidity_drops"] = 0.7
        
        # 7. Check for classic rugpull pattern: rapid rise followed by drop
        if historical_data and len(historical_data) >= 14:  # At least two weeks of data
            historical_data.sort(key=lambda x: x.get("timestamp", 0))
            
            # Check for rapid rise followed by drop
            first_week = historical_data[:7]
            second_week = historical_data[7:14]
            
            first_week_change = 0
            if first_week[0].get("total_liquidity_usd", 0) > 0:
                first_week_change = ((first_week[-1].get("total_liquidity_usd", 0) - 
                                      first_week[0].get("total_liquidity_usd", 0)) / 
                                     first_week[0].get("total_liquidity_usd", 0)) * 100
            
            second_week_change = 0
            if second_week[0].get("total_liquidity_usd", 0) > 0:
                second_week_change = ((second_week[-1].get("total_liquidity_usd", 0) - 
                                       second_week[0].get("total_liquidity_usd", 0)) / 
                                      second_week[0].get("total_liquidity_usd", 0)) * 100
            
            if first_week_change > 50 and second_week_change < -30:
                risk_factors["pump_and_dump_pattern"] = 0.9
            elif first_week_change > 30 and second_week_change < -15:
                risk_factors["potential_pump_and_dump"] = 0.6
        
        # 8. LP token holder analysis (if available)
        # This would require additional on-chain data about LP token holders
        # For now, we'll leave it as a placeholder
        
        # 9. Timelock verification (if available)
        # This would require additional on-chain data about contract timelock
        # For now, we'll leave it as a placeholder
        
        return risk_factors
    
    def _calculate_risk_score(self, risk_factors: Dict[str, float]) -> float:
        """
        Calculate overall risk score from risk factors.
        
        Args:
            risk_factors: Risk factors with scores
            
        Returns:
            float: Overall risk score (0-1)
        """
        if not risk_factors:
            return 0.3  # Default low-medium risk with no factors
        
        if "no_liquidity" in risk_factors:
            return 1.0  # No liquidity is maximum risk
        
        # Factor weights
        weights = {
            "extremely_low_liquidity": 0.25,
            "very_low_liquidity": 0.2,
            "low_liquidity": 0.15,
            "extreme_liquidity_concentration": 0.25,
            "high_liquidity_concentration": 0.15,
            "extremely_low_liquidity_ratio": 0.2,
            "low_liquidity_ratio": 0.1,
            "significant_liquidity_decrease": 0.2,
            "moderate_liquidity_decrease": 0.1,
            "extreme_liquidity_volatility": 0.15,
            "high_liquidity_volatility": 0.1,
            "severe_liquidity_drops": 0.25,
            "significant_liquidity_drops": 0.15,
            "pump_and_dump_pattern": 0.3,
            "potential_pump_and_dump": 0.2
        }
        
        # Calculate weighted score
        weighted_sum = sum(risk_factors[factor] * weights.get(factor, 0.1) for factor in risk_factors)
        max_possible_sum = sum(weights.get(factor, 0.1) for factor in risk_factors)
        
        if max_possible_sum > 0:
            return min(1.0, weighted_sum / max_possible_sum)
        else:
            return 0.3  # Default low-medium risk
    
    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """
        Determine risk level from risk score.
        
        Args:
            risk_score: Risk score (0-1)
            
        Returns:
            RiskLevel: Risk level enum
        """
        if risk_score >= self.critical_risk_threshold:
            return RiskLevel.CRITICAL
        elif risk_score >= self.high_risk_threshold:
            return RiskLevel.HIGH
        elif risk_score >= 0.4:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _generate_explanation(self, risk_factors: Dict[str, float], risk_score: float, 
                             liquidity_data: Dict[str, Any]) -> str:
        """
        Generate a human-readable explanation of the risk assessment.
        
        Args:
            risk_factors: Risk factors with scores
            risk_score: Overall risk score
            liquidity_data: Current liquidity data
            
        Returns:
            str: Human-readable explanation
        """
        if "no_liquidity" in risk_factors:
            return "This token has no detectable liquidity, which presents a maximum risk for trading."
        
        total_liquidity = liquidity_data.get("total_liquidity_usd", 0)
        
        explanation = f"This token has ${total_liquidity:,.2f} in total liquidity"
        
        if risk_score >= self.critical_risk_threshold:
            explanation += " and shows critical rugpull risk indicators."
        elif risk_score >= self.high_risk_threshold:
            explanation += " and shows high rugpull risk indicators."
        elif risk_score >= 0.4:
            explanation += " and shows moderate rugpull risk indicators."
        else:
            explanation += " and shows low rugpull risk indicators."
        
        # Add details about specific risk factors
        if "extremely_low_liquidity" in risk_factors or "very_low_liquidity" in risk_factors:
            explanation += " The token has very low liquidity, making it vulnerable to price manipulation and difficult to exit positions."
        
        if "extreme_liquidity_concentration" in risk_factors or "high_liquidity_concentration" in risk_factors:
            explanation += " Liquidity is highly concentrated, which increases vulnerability to sudden liquidity removal."
        
        if "significant_liquidity_decrease" in risk_factors:
            explanation += " There has been a significant decrease in liquidity recently, which could indicate ongoing liquidity removal."
        
        if "pump_and_dump_pattern" in risk_factors:
            explanation += " The token shows a classic pump-and-dump pattern in its liquidity history."
        
        return explanation
    
    def _generate_recommendations(self, risk_factors: Dict[str, float], risk_score: float, 
                                liquidity_data: Dict[str, Any]) -> List[str]:
        """
        Generate recommendations based on rugpull risk assessment.
        
        Args:
            risk_factors: Risk factors with scores
            risk_score: Overall risk score
            liquidity_data: Current liquidity data
            
        Returns:
            List[str]: List of recommendations
        """
        recommendations = []
        
        if "no_liquidity" in risk_factors:
            recommendations.append("Avoid trading as there is no detectable liquidity")
            recommendations.append("Contact the token team to understand if and when liquidity will be added")
            return recommendations
        
        # Add general recommendations based on risk level
        if risk_score >= self.critical_risk_threshold:
            recommendations.append("Exercise extreme caution - critical rugpull risk indicators detected")
            recommendations.append("Consider avoiding this token until risk factors are addressed")
        elif risk_score >= self.high_risk_threshold:
            recommendations.append("Exercise high caution - significant rugpull risk indicators detected")
            recommendations.append("Only trade with amounts you can afford to lose completely")
        
        # Add specific recommendations based on risk factors
        if "extremely_low_liquidity" in risk_factors or "very_low_liquidity" in risk_factors:
            recommendations.append("Be aware of high slippage and potential inability to exit positions due to low liquidity")
            recommendations.append("Use small position sizes to minimize slippage impact")
        
        if "extreme_liquidity_concentration" in risk_factors or "high_liquidity_concentration" in risk_factors:
            recommendations.append("Monitor for changes in the concentrated liquidity, as removal could happen quickly")
            recommendations.append("Look for tokens with more distributed liquidity pools")
        
        if "significant_liquidity_decrease" in risk_factors:
            recommendations.append("Watch for continued liquidity removal which could indicate a slow rugpull")
        
        if "pump_and_dump_pattern" in risk_factors:
            recommendations.append("Be extremely cautious as this token shows classic pump-and-dump patterns")
        
        # Add general safety recommendations
        total_liquidity = liquidity_data.get("total_liquidity_usd", 0)
        if total_liquidity > 0:
            # Suggest appropriate position sizes based on liquidity
            if total_liquidity < 10000:
                max_position = total_liquidity * 0.01  # 1% of liquidity
                recommendations.append(f"Limit individual trades to less than ${max_position:.2f} to minimize slippage")
            elif total_liquidity < 100000:
                max_position = total_liquidity * 0.02  # 2% of liquidity
                recommendations.append(f"Consider limiting individual trades to less than ${max_position:.2f} for better execution")
        
        # Add project research recommendation
        recommendations.append("Research the token team's background and project roadmap before investing")
        
        return recommendations


# Initialize the detector
rugpull_detector = RugpullDetector() 