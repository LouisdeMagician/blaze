"""
LP token tracker for liquidity analysis.
Analyzes LP token distribution, holders, and lock status.
"""
import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime

from src.blockchain.solana_client import solana_client, SolanaClientError
from src.dex.dex_aggregator import dex_aggregator
from src.utils.token_utils import is_token_program

logger = logging.getLogger(__name__)

class LpTokenTracker:
    """Tracks and analyzes LP token data."""
    
    def __init__(self):
        """Initialize the LP token tracker."""
        self.lp_token_cache = {}
        self.lp_token_cache_ttl = 3600  # 1 hour
        self.lp_token_cache_time = {}
    
    async def get_lp_tokens_for_token(self, token_address: str) -> List[Dict[str, Any]]:
        """
        Get all LP tokens associated with a token.
        
        Args:
            token_address: Token mint address
            
        Returns:
            List[Dict]: List of LP tokens
        """
        try:
            # Get token liquidity data from DEX aggregator
            liquidity_data = await dex_aggregator.get_token_liquidity(token_address)
            
            # Extract pools
            pools = liquidity_data.get("pools", [])
            
            # Extract LP token addresses
            lp_tokens = []
            for pool in pools:
                if "lp_token" in pool:
                    lp_token_address = pool.get("lp_token")
                    
                    # Skip if this LP token is already in the list
                    if any(lp.get("address") == lp_token_address for lp in lp_tokens):
                        continue
                    
                    # Get LP token data
                    lp_token_data = await self.get_lp_token_data(lp_token_address, pool)
                    lp_tokens.append(lp_token_data)
            
            return lp_tokens
            
        except Exception as e:
            logger.error(f"Error getting LP tokens for {token_address}: {e}", exc_info=True)
            return []
    
    async def get_lp_token_data(self, lp_token_address: str, pool_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get data for an LP token.
        
        Args:
            lp_token_address: LP token mint address
            pool_data: Optional pool data if available
            
        Returns:
            Dict: LP token data
        """
        # Check cache
        now = time.time()
        if (lp_token_address in self.lp_token_cache and 
            now - self.lp_token_cache_time.get(lp_token_address, 0) < self.lp_token_cache_ttl):
            return self.lp_token_cache[lp_token_address]
        
        try:
            # Get LP token data from blockchain
            token_info = await solana_client.get_token_info(lp_token_address)
            
            if not token_info:
                return {
                    "address": lp_token_address,
                    "valid": False,
                    "error": "LP token not found"
                }
            
            # Build basic LP token data
            lp_data = {
                "address": lp_token_address,
                "valid": True,
                "dex": pool_data.get("dex", "unknown") if pool_data else "unknown",
                "pool_id": pool_data.get("id") if pool_data else None,
                "token_a": pool_data.get("token_a", pool_data.get("base_token")) if pool_data else None,
                "token_b": pool_data.get("token_b", pool_data.get("quote_token")) if pool_data else None,
                "token_a_name": pool_data.get("token_a_name", pool_data.get("base_token_name")) if pool_data else None,
                "token_b_name": pool_data.get("token_b_name", pool_data.get("quote_token_name")) if pool_data else None,
                "supply": token_info.get("supply", 0),
                "decimals": token_info.get("decimals", 0),
                "holders": await self._get_top_holders(lp_token_address),
                "lock_status": await self._check_lock_status(lp_token_address),
                "last_updated": int(now)
            }
            
            # Update cache
            self.lp_token_cache[lp_token_address] = lp_data
            self.lp_token_cache_time[lp_token_address] = now
            
            return lp_data
            
        except Exception as e:
            logger.error(f"Error getting LP token data for {lp_token_address}: {e}", exc_info=True)
            return {
                "address": lp_token_address,
                "valid": False,
                "error": str(e)
            }
    
    async def _get_top_holders(self, lp_token_address: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get top holders of an LP token.
        
        Args:
            lp_token_address: LP token mint address
            limit: Number of top holders to return
            
        Returns:
            List[Dict]: List of top holders
        """
        try:
            # Get token holders
            # This is a simplified implementation - in a real system, we'd use more comprehensive data
            holders = await solana_client.get_token_largest_accounts(lp_token_address)
            
            if not holders or "value" not in holders:
                return []
            
            # Get top holders
            top_holders = []
            total_supply = 0
            
            # Calculate total supply from holder balances
            for holder in holders.get("value", []):
                total_supply += int(holder.get("amount", "0"))
            
            # Format holder data
            for i, holder in enumerate(holders.get("value", [])[:limit]):
                address = holder.get("address", "")
                amount = int(holder.get("amount", "0"))
                
                # Calculate percentage
                percentage = 0
                if total_supply > 0:
                    percentage = (amount / total_supply) * 100
                
                # Determine if holder is a smart contract
                is_program = await is_token_program(address)
                
                top_holders.append({
                    "address": address,
                    "amount": amount,
                    "percentage": percentage,
                    "is_program": is_program,
                    "rank": i + 1
                })
            
            return top_holders
            
        except Exception as e:
            logger.error(f"Error getting top holders for LP token {lp_token_address}: {e}", exc_info=True)
            return []
    
    async def _check_lock_status(self, lp_token_address: str) -> Dict[str, Any]:
        """
        Check if LP token is locked.
        
        Args:
            lp_token_address: LP token mint address
            
        Returns:
            Dict: Lock status information
        """
        try:
            # Get top holders
            holders = await self._get_top_holders(lp_token_address, limit=3)
            
            # Check if any top holders are known locker programs
            known_lockers = {
                "7ujX6typx7wnrMPb1jKQHBVEJ5tpA344CvMkrYxKhRmE": "Solana Token Locker",
                "CLoKRISQMhGnrg8pyPXkjMFrqaLwbs7cCdWxYZTyuGy": "SeaPad Locker",
                "LiquC3FSR3nxumJURkBGw7r6z8gZP3PNd1TeTkfHYBN": "Liqlab Locker"
                # Add more known locker programs as needed
            }
            
            # Check if any top holders are known lockers
            locked_in = []
            total_locked_percentage = 0
            
            for holder in holders:
                if holder.get("is_program", False):
                    address = holder.get("address", "")
                    if address in known_lockers:
                        locked_in.append({
                            "locker": known_lockers[address],
                            "address": address,
                            "percentage": holder.get("percentage", 0)
                        })
                        total_locked_percentage += holder.get("percentage", 0)
            
            # Determine overall lock status
            is_locked = len(locked_in) > 0
            lock_confidence = "high" if total_locked_percentage > 70 else "medium" if total_locked_percentage > 30 else "low"
            
            return {
                "is_locked": is_locked,
                "locked_percentage": total_locked_percentage,
                "locked_in": locked_in,
                "confidence": lock_confidence if is_locked else "unknown"
            }
            
        except Exception as e:
            logger.error(f"Error checking lock status for LP token {lp_token_address}: {e}", exc_info=True)
            return {
                "is_locked": False,
                "locked_percentage": 0,
                "locked_in": [],
                "confidence": "unknown",
                "error": str(e)
            }
    
    async def analyze_lp_token_risk(self, token_address: str) -> Dict[str, Any]:
        """
        Analyze LP token risk for a token.
        
        Args:
            token_address: Token mint address
            
        Returns:
            Dict: LP token risk analysis
        """
        try:
            # Get all LP tokens for the token
            lp_tokens = await self.get_lp_tokens_for_token(token_address)
            
            if not lp_tokens:
                return {
                    "token_address": token_address,
                    "risk_level": "CRITICAL",
                    "lp_tokens_found": 0,
                    "explanation": "No LP tokens found for this token, indicating no verifiable liquidity.",
                    "last_updated": int(time.time())
                }
            
            # Calculate total locked percentage across all LP tokens
            total_percentage = sum(lp.get("lock_status", {}).get("locked_percentage", 0) for lp in lp_tokens)
            avg_percentage = total_percentage / len(lp_tokens) if lp_tokens else 0
            
            # Count locked and unlocked LP tokens
            locked_count = sum(1 for lp in lp_tokens if lp.get("lock_status", {}).get("is_locked", False))
            unlocked_count = len(lp_tokens) - locked_count
            
            # Determine concentration risk
            has_concentration_risk = False
            high_concentration_dex = None
            
            if lp_tokens:
                # Group by DEX
                dex_counts = {}
                for lp in lp_tokens:
                    dex = lp.get("dex", "unknown")
                    dex_counts[dex] = dex_counts.get(dex, 0) + 1
                
                # Check if one DEX has all or most LP tokens
                if len(dex_counts) == 1:
                    has_concentration_risk = True
                    high_concentration_dex = list(dex_counts.keys())[0]
                else:
                    # Check if one DEX has > 90% of the LP tokens
                    most_common_dex = max(dex_counts.items(), key=lambda x: x[1])
                    if most_common_dex[1] / len(lp_tokens) > 0.9:
                        has_concentration_risk = True
                        high_concentration_dex = most_common_dex[0]
            
            # Determine risk level
            risk_level = "LOW"
            if not lp_tokens:
                risk_level = "CRITICAL"
            elif unlocked_count > locked_count and len(lp_tokens) > 1:
                risk_level = "HIGH"
            elif avg_percentage < 30:
                risk_level = "HIGH"
            elif avg_percentage < 70:
                risk_level = "MEDIUM"
            
            # Generate explanation
            explanation = f"Found {len(lp_tokens)} LP tokens for this token. "
            
            if locked_count > 0:
                explanation += f"{locked_count} of them are locked ({avg_percentage:.1f}% of total LP on average). "
            else:
                explanation += "None of them appear to be locked, which presents a liquidity risk. "
            
            if has_concentration_risk:
                explanation += f"Liquidity is concentrated in {high_concentration_dex} pools, increasing risk. "
            
            # Generate recommendations
            recommendations = []
            
            if not lp_tokens:
                recommendations.append("Verify if this token has actual liquidity pools")
            elif unlocked_count > 0:
                recommendations.append(f"Be cautious as {unlocked_count} LP tokens are not locked")
                recommendations.append("Monitor for any sudden liquidity removal")
            
            if avg_percentage < 50:
                recommendations.append("Consider projects with higher percentages of locked LP")
            
            if has_concentration_risk:
                recommendations.append(f"Be aware that liquidity is concentrated in {high_concentration_dex}")
                recommendations.append("Projects with liquidity across multiple DEXes reduce rug risk")
            
            return {
                "token_address": token_address,
                "risk_level": risk_level,
                "lp_tokens_found": len(lp_tokens),
                "locked_lp_count": locked_count,
                "unlocked_lp_count": unlocked_count,
                "average_locked_percentage": avg_percentage,
                "has_concentration_risk": has_concentration_risk,
                "high_concentration_dex": high_concentration_dex if has_concentration_risk else None,
                "explanation": explanation,
                "recommendations": recommendations,
                "lp_tokens": lp_tokens,
                "last_updated": int(time.time())
            }
            
        except Exception as e:
            logger.error(f"Error analyzing LP token risk for {token_address}: {e}", exc_info=True)
            return {
                "token_address": token_address,
                "risk_level": "MEDIUM",  # Default to medium risk on error
                "error": str(e),
                "last_updated": int(time.time())
            }


# Initialize the tracker
lp_token_tracker = LpTokenTracker() 