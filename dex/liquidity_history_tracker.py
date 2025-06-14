"""
Historical liquidity tracker for time-series analysis.
Tracks token liquidity over time to detect trends and anomalies.
"""
import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
import numpy as np
from pymongo import DESCENDING

from src.dex.dex_aggregator import dex_aggregator
from src.services.database_service import database_service

logger = logging.getLogger(__name__)

class LiquidityHistoryTracker:
    """Tracks and analyzes historical liquidity data for tokens."""
    
    def __init__(self):
        """Initialize the liquidity history tracker."""
        self.db = database_service.get_database()
        self.liquidity_history_collection = self.db["liquidity_history"]
        self.initialized = False
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Ensure necessary indexes are created."""
        try:
            # Create indexes for efficient queries
            self.liquidity_history_collection.create_index([("token_address", 1), ("timestamp", -1)])
            self.liquidity_history_collection.create_index([("token_address", 1), ("dex", 1), ("timestamp", -1)])
            
            # TTL index to automatically remove old data (90 days)
            self.liquidity_history_collection.create_index("timestamp", expireAfterSeconds=7776000)
            
            self.initialized = True
            
        except Exception as e:
            logger.error(f"Error creating indexes for liquidity history: {e}", exc_info=True)
    
    async def record_liquidity_snapshot(self, token_address: str) -> Dict[str, Any]:
        """
        Record current liquidity data as a snapshot.
        
        Args:
            token_address: Token mint address
            
        Returns:
            Dict: Recorded snapshot data
        """
        try:
            # Get current liquidity data
            liquidity_data = await dex_aggregator.get_token_liquidity(token_address, force_refresh=True)
            
            # Create snapshot timestamp
            now = datetime.utcnow()
            
            # Extract key metrics for the snapshot
            snapshot = {
                "token_address": token_address,
                "timestamp": now,
                "total_liquidity_usd": liquidity_data.get("total_liquidity_usd", 0),
                "total_volume_24h": liquidity_data.get("total_volume_24h", 0),
                "total_pool_count": liquidity_data.get("total_pool_count", 0),
                "price_usd": liquidity_data.get("price_usd"),
                "dex_breakdown": liquidity_data.get("dex_breakdown", {}),
                "liquidity_concentration": liquidity_data.get("liquidity_concentration", {}),
                "slippage_samples": liquidity_data.get("slippage_samples", []),
                "risk_metrics": liquidity_data.get("risk_metrics", {})
            }
            
            # Save the snapshot to the database
            result = await self.liquidity_history_collection.insert_one(snapshot)
            
            # Also save DEX-specific snapshots
            for dex_name, dex_data in liquidity_data.get("dex_breakdown", {}).items():
                dex_snapshot = {
                    "token_address": token_address,
                    "dex": dex_name,
                    "timestamp": now,
                    "liquidity_usd": dex_data,
                    "pool_count": len([p for p in liquidity_data.get("pools", []) if p.get("dex") == dex_name])
                }
                await self.liquidity_history_collection.insert_one(dex_snapshot)
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error recording liquidity snapshot for {token_address}: {e}", exc_info=True)
            return {
                "token_address": token_address,
                "timestamp": datetime.utcnow(),
                "error": str(e),
                "total_liquidity_usd": 0
            }
    
    async def get_liquidity_history(self, token_address: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get historical liquidity data for a token.
        
        Args:
            token_address: Token mint address
            days: Number of days of history to retrieve
            
        Returns:
            List[Dict]: List of historical liquidity data points
        """
        try:
            # Calculate start date
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Query for historical data
            cursor = self.liquidity_history_collection.find(
                {"token_address": token_address, "timestamp": {"$gte": start_date}}
            ).sort("timestamp", DESCENDING)
            
            # Convert cursor to list
            history = await cursor.to_list(length=None)
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting liquidity history for {token_address}: {e}", exc_info=True)
            return []
    
    async def get_liquidity_change_metrics(self, token_address: str, days: int = 7) -> Dict[str, Any]:
        """
        Calculate liquidity change metrics over a period.
        
        Args:
            token_address: Token mint address
            days: Number of days to analyze
            
        Returns:
            Dict: Liquidity change metrics
        """
        try:
            # Get historical data
            history = await self.get_liquidity_history(token_address, days)
            
            if not history or len(history) < 2:
                return {
                    "token_address": token_address,
                    "days_analyzed": days,
                    "insufficient_data": True,
                    "liquidity_change_percent": 0,
                    "volume_change_percent": 0,
                    "price_change_percent": 0,
                    "volatility": 0
                }
            
            # Sort by timestamp (newest to oldest)
            history.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            
            # Calculate changes
            latest = history[0]
            oldest = history[-1]
            
            # Extract metrics
            latest_liquidity = latest.get("total_liquidity_usd", 0)
            oldest_liquidity = oldest.get("total_liquidity_usd", 0)
            
            latest_volume = latest.get("total_volume_24h", 0)
            oldest_volume = oldest.get("total_volume_24h", 0)
            
            latest_price = latest.get("price_usd", 0)
            oldest_price = oldest.get("price_usd", 0)
            
            # Calculate percent changes
            liquidity_change_percent = 0
            if oldest_liquidity > 0:
                liquidity_change_percent = ((latest_liquidity - oldest_liquidity) / oldest_liquidity) * 100
            
            volume_change_percent = 0
            if oldest_volume > 0:
                volume_change_percent = ((latest_volume - oldest_volume) / oldest_volume) * 100
            
            price_change_percent = 0
            if oldest_price and oldest_price > 0:
                price_change_percent = ((latest_price - oldest_price) / oldest_price) * 100
            
            # Calculate volatility (standard deviation of percent changes)
            daily_changes = []
            for i in range(1, len(history)):
                prev_liquidity = history[i].get("total_liquidity_usd", 0)
                curr_liquidity = history[i-1].get("total_liquidity_usd", 0)
                
                if prev_liquidity > 0:
                    percent_change = ((curr_liquidity - prev_liquidity) / prev_liquidity) * 100
                    daily_changes.append(percent_change)
            
            volatility = 0
            if daily_changes:
                volatility = np.std(daily_changes)
            
            return {
                "token_address": token_address,
                "days_analyzed": days,
                "data_points": len(history),
                "start_date": oldest.get("timestamp"),
                "end_date": latest.get("timestamp"),
                "latest_liquidity_usd": latest_liquidity,
                "oldest_liquidity_usd": oldest_liquidity,
                "liquidity_change_percent": liquidity_change_percent,
                "volume_change_percent": volume_change_percent,
                "price_change_percent": price_change_percent,
                "liquidity_volatility": volatility,
                "liquidity_trend": "increasing" if liquidity_change_percent > 5 else
                                   "decreasing" if liquidity_change_percent < -5 else "stable"
            }
            
        except Exception as e:
            logger.error(f"Error calculating liquidity change metrics for {token_address}: {e}", exc_info=True)
            return {
                "token_address": token_address,
                "days_analyzed": days,
                "error": str(e),
                "liquidity_change_percent": 0
            }
    
    async def detect_liquidity_anomalies(self, token_address: str, days: int = 30) -> Dict[str, Any]:
        """
        Detect anomalies in liquidity data.
        
        Args:
            token_address: Token mint address
            days: Number of days to analyze
            
        Returns:
            Dict: Detected anomalies
        """
        try:
            # Get historical data
            history = await self.get_liquidity_history(token_address, days)
            
            if not history or len(history) < 7:  # Need at least a week of data
                return {
                    "token_address": token_address,
                    "days_analyzed": days,
                    "insufficient_data": True,
                    "anomalies": []
                }
            
            # Sort by timestamp (oldest to newest)
            history.sort(key=lambda x: x.get("timestamp", 0))
            
            # Extract liquidity values
            liquidity_values = [entry.get("total_liquidity_usd", 0) for entry in history]
            timestamps = [entry.get("timestamp") for entry in history]
            
            # Calculate rolling mean and standard deviation
            window = min(7, len(liquidity_values) // 2)  # Use 7 days or half the data points
            rolling_mean = []
            rolling_std = []
            
            for i in range(len(liquidity_values)):
                if i < window:
                    # Not enough data for window, use all available
                    window_values = liquidity_values[:i+1]
                else:
                    # Use sliding window
                    window_values = liquidity_values[i-window:i+1]
                
                rolling_mean.append(np.mean(window_values))
                rolling_std.append(np.std(window_values) if len(window_values) > 1 else 0)
            
            # Detect anomalies (values outside 3 standard deviations)
            anomalies = []
            for i in range(window, len(liquidity_values)):
                if rolling_std[i] > 0:
                    z_score = abs((liquidity_values[i] - rolling_mean[i]) / rolling_std[i])
                    
                    if z_score > 3:
                        # This is an anomaly
                        percent_change = 0
                        if liquidity_values[i-1] > 0:
                            percent_change = ((liquidity_values[i] - liquidity_values[i-1]) / liquidity_values[i-1]) * 100
                        
                        anomalies.append({
                            "timestamp": timestamps[i],
                            "liquidity_usd": liquidity_values[i],
                            "expected_liquidity": rolling_mean[i],
                            "percent_change": percent_change,
                            "z_score": z_score,
                            "type": "spike" if liquidity_values[i] > rolling_mean[i] else "drop"
                        })
            
            # Detect sudden large changes (day-to-day)
            for i in range(1, len(liquidity_values)):
                if liquidity_values[i-1] > 0:
                    percent_change = ((liquidity_values[i] - liquidity_values[i-1]) / liquidity_values[i-1]) * 100
                    
                    # Consider >30% daily change as anomalous
                    if abs(percent_change) > 30:
                        # Check if this anomaly is already recorded
                        if not any(a.get("timestamp") == timestamps[i] for a in anomalies):
                            anomalies.append({
                                "timestamp": timestamps[i],
                                "liquidity_usd": liquidity_values[i],
                                "previous_liquidity": liquidity_values[i-1],
                                "percent_change": percent_change,
                                "type": "sudden_increase" if percent_change > 0 else "sudden_decrease"
                            })
            
            # Sort anomalies by timestamp (newest first)
            anomalies.sort(key=lambda x: x.get("timestamp"), reverse=True)
            
            return {
                "token_address": token_address,
                "days_analyzed": days,
                "data_points": len(history),
                "anomalies_detected": len(anomalies),
                "anomalies": anomalies
            }
            
        except Exception as e:
            logger.error(f"Error detecting liquidity anomalies for {token_address}: {e}", exc_info=True)
            return {
                "token_address": token_address,
                "days_analyzed": days,
                "error": str(e),
                "anomalies": []
            }


# Initialize tracker
liquidity_history_tracker = LiquidityHistoryTracker() 