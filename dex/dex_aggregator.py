"""
DEX Aggregator for liquidity analysis.
Combines data from multiple DEXes to provide comprehensive liquidity information.
"""
import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime

from src.dex.raydium_client import raydium_client
from src.dex.orca_client import orca_client
from src.dex.jupiter_client import jupiter_client
from src.utils.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)

class DexAggregator:
    """Aggregator for DEX liquidity data from multiple sources."""
    
    def __init__(self):
        """Initialize the DEX aggregator."""
        self.clients = {
            "raydium": raydium_client,
            "orca": orca_client,
            "jupiter": jupiter_client
        }
        
        # Cache for aggregated data
        self.liquidity_cache = {}
        self.liquidity_last_updated = {}
        self.liquidity_cache_ttl = 300  # 5 minutes
    
    async def get_token_liquidity(self, token_address: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive liquidity data for a token from all DEXes.
        
        Args:
            token_address: Token mint address
            force_refresh: Force refresh cached data
            
        Returns:
            Dict: Aggregated liquidity data
        """
        now = time.time()
        
        # Check if we can use cached data
        if (not force_refresh and 
            token_address in self.liquidity_cache and 
            now - self.liquidity_last_updated.get(token_address, 0) < self.liquidity_cache_ttl):
            return self.liquidity_cache[token_address]
        
        # Fetch data from all DEXes concurrently
        tasks = []
        for name, client in self.clients.items():
            tasks.append(self._get_dex_liquidity(name, client, token_address))
        
        dex_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results, handling any exceptions
        dex_data = {}
        for i, result in enumerate(dex_results):
            dex_name = list(self.clients.keys())[i]
            if isinstance(result, Exception):
                logger.error(f"Error getting {dex_name} liquidity for {token_address}: {result}")
                dex_data[dex_name] = {
                    "error": str(result),
                    "token_address": token_address,
                    "source": dex_name
                }
            else:
                dex_data[dex_name] = result
        
        # Aggregate the data
        aggregated_data = self._aggregate_liquidity_data(token_address, dex_data)
        
        # Update cache
        self.liquidity_cache[token_address] = aggregated_data
        self.liquidity_last_updated[token_address] = now
        
        return aggregated_data
    
    async def _get_dex_liquidity(self, dex_name: str, client: Any, token_address: str) -> Dict[str, Any]:
        """
        Get liquidity data from a specific DEX.
        
        Args:
            dex_name: Name of the DEX
            client: DEX client instance
            token_address: Token mint address
            
        Returns:
            Dict: DEX-specific liquidity data
        """
        try:
            return await client.get_token_liquidity_data(token_address)
        except Exception as e:
            logger.error(f"Error getting {dex_name} liquidity for {token_address}: {e}", exc_info=True)
            return {
                "token_address": token_address,
                "error": str(e),
                "source": dex_name
            }
    
    def _aggregate_liquidity_data(self, token_address: str, dex_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate liquidity data from multiple DEXes.
        
        Args:
            token_address: Token mint address
            dex_data: Dict of DEX-specific liquidity data
            
        Returns:
            Dict: Aggregated liquidity data
        """
        # Initialize the aggregated data
        aggregated = {
            "token_address": token_address,
            "sources": list(dex_data.keys()),
            "total_liquidity_usd": 0,
            "total_volume_24h": 0,
            "total_pool_count": 0,
            "dex_breakdown": {},
            "slippage_samples": [],
            "liquidity_concentration": {
                "highest_concentration": 0,
                "dex_with_highest": "",
                "overall_concentration": 0
            },
            "pools": [],
            "last_updated": int(time.time())
        }
        
        # Extract token price from Jupiter if available
        if "jupiter" in dex_data and "price_usd" in dex_data["jupiter"]:
            aggregated["price_usd"] = dex_data["jupiter"].get("price_usd")
        
        # Calculate total liquidity across all DEXes
        total_liquidity = 0
        total_volume = 0
        pool_count = 0
        dex_liquidity = {}
        all_pools = []
        
        for dex_name, data in dex_data.items():
            # Skip if there was an error with this DEX
            if "error" in data:
                continue
            
            # Extract liquidity and volume
            dex_liquidity[dex_name] = data.get("total_liquidity_usd", 0)
            if dex_name == "jupiter" and "estimated_liquidity_usd" in data:
                dex_liquidity[dex_name] = data.get("estimated_liquidity_usd", 0)
                
            total_liquidity += dex_liquidity[dex_name]
            total_volume += data.get("total_volume_24h", 0)
            
            # Count pools
            if dex_name == "raydium":
                pool_count += data.get("pool_count", 0)
                all_pools.extend([{**p, "dex": "raydium"} for p in data.get("pools", [])])
            elif dex_name == "orca":
                pool_count += data.get("total_pool_count", 0)
                all_pools.extend([{**p, "dex": "orca", "type": "v2"} for p in data.get("v2_pools", [])])
                all_pools.extend([{**p, "dex": "orca", "type": "whirlpool"} for p in data.get("whirlpools", [])])
            elif dex_name == "jupiter":
                route_count = len(data.get("routes", []))
                pool_count += route_count
        
        aggregated["total_liquidity_usd"] = total_liquidity
        aggregated["total_volume_24h"] = total_volume
        aggregated["total_pool_count"] = pool_count
        aggregated["dex_breakdown"] = dex_liquidity
        aggregated["pools"] = all_pools
        
        # Calculate liquidity distribution
        if total_liquidity > 0:
            # Find DEX with highest liquidity
            highest_dex = max(dex_liquidity.items(), key=lambda x: x[1]) if dex_liquidity else ("", 0)
            aggregated["liquidity_concentration"]["highest_concentration"] = highest_dex[1] / total_liquidity if total_liquidity > 0 else 0
            aggregated["liquidity_concentration"]["dex_with_highest"] = highest_dex[0]
            
            # Find largest pool across all DEXes
            if all_pools:
                largest_pool = max(all_pools, key=lambda p: p.get("liquidity", 0))
                aggregated["liquidity_concentration"]["overall_concentration"] = largest_pool.get("liquidity", 0) / total_liquidity if total_liquidity > 0 else 0
                aggregated["liquidity_concentration"]["largest_pool"] = {
                    "dex": largest_pool.get("dex", "unknown"),
                    "pool_id": largest_pool.get("id", "unknown"),
                    "liquidity": largest_pool.get("liquidity", 0)
                }
        
        # Aggregate slippage/impact samples
        # Start with Jupiter's impact samples as they're cross-DEX
        if "jupiter" in dex_data and "impact_samples" in dex_data["jupiter"]:
            aggregated["slippage_samples"] = dex_data["jupiter"]["impact_samples"]
        # If no Jupiter data, use Raydium or Orca
        elif "raydium" in dex_data and "slippage_samples" in dex_data["raydium"]:
            aggregated["slippage_samples"] = dex_data["raydium"]["slippage_samples"]
        elif "orca" in dex_data and "impact_samples" in dex_data["orca"]:
            aggregated["slippage_samples"] = dex_data["orca"]["impact_samples"]
        
        # Add risk metrics
        aggregated["risk_metrics"] = self._calculate_risk_metrics(aggregated)
        
        return aggregated
    
    def _calculate_risk_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate risk metrics based on liquidity data.
        
        Args:
            data: Aggregated liquidity data
            
        Returns:
            Dict: Risk metrics
        """
        risk_metrics = {
            "low_liquidity": False,
            "very_low_liquidity": False,
            "extremely_low_liquidity": False,
            "high_concentration": False,
            "extreme_concentration": False,
            "high_slippage": False,
            "extreme_slippage": False,
            "overall_risk_score": 0  # 0-100 scale
        }
        
        # Liquidity thresholds
        total_liquidity = data.get("total_liquidity_usd", 0)
        if total_liquidity < 10000:
            risk_metrics["extremely_low_liquidity"] = True
        elif total_liquidity < 50000:
            risk_metrics["very_low_liquidity"] = True
        elif total_liquidity < 200000:
            risk_metrics["low_liquidity"] = True
        
        # Concentration risk
        concentration = data.get("liquidity_concentration", {}).get("overall_concentration", 0)
        if concentration > 0.9:
            risk_metrics["extreme_concentration"] = True
        elif concentration > 0.7:
            risk_metrics["high_concentration"] = True
        
        # Slippage risk for $10k trade
        slippage_samples = data.get("slippage_samples", [])
        high_value_slippage = next((s for s in slippage_samples if s.get("amount_usd") == 10000), None)
        
        if high_value_slippage:
            slippage = high_value_slippage.get("price_impact_percent", 0)
            if "slippage_percent" in high_value_slippage:
                slippage = high_value_slippage.get("slippage_percent", 0)
                
            if slippage > 15:
                risk_metrics["extreme_slippage"] = True
            elif slippage > 5:
                risk_metrics["high_slippage"] = True
        
        # Calculate overall risk score
        risk_score = 0
        
        # Liquidity factors
        if risk_metrics["extremely_low_liquidity"]:
            risk_score += 40
        elif risk_metrics["very_low_liquidity"]:
            risk_score += 25
        elif risk_metrics["low_liquidity"]:
            risk_score += 10
        
        # Concentration factors
        if risk_metrics["extreme_concentration"]:
            risk_score += 30
        elif risk_metrics["high_concentration"]:
            risk_score += 15
        
        # Slippage factors
        if risk_metrics["extreme_slippage"]:
            risk_score += 30
        elif risk_metrics["high_slippage"]:
            risk_score += 15
        
        risk_metrics["overall_risk_score"] = min(100, risk_score)
        
        return risk_metrics


# Initialize the aggregator
dex_aggregator = DexAggregator() 