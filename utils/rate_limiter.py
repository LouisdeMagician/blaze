"""
Rate limiting implementation for API endpoints.
Supports IP-based, user-based, and adaptive rate limiting with configurable rules.
"""
import time
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple, Union, Set
from dataclasses import dataclass, field
from enum import Enum
import ipaddress
import hashlib
import random
from collections import deque

from src.utils.settings import (
    RATE_LIMIT_DEFAULT,
    RATE_LIMIT_BURST,
    RATE_LIMIT_WINDOW_SECONDS,
    RATE_LIMIT_USER_MULTIPLIER,
    RATE_LIMIT_MAX_TOKENS,
    RATE_LIMIT_TRUSTED_IPS,
    RATE_LIMIT_TRUSTED_API_KEYS,
    RATE_LIMIT_GEO_RESTRICTIONS,
    RATE_LIMIT_IP_BLACKLIST,
    RATE_LIMIT_IP_WHITELIST
)

logger = logging.getLogger(__name__)

class RateLimitType(Enum):
    """Types of rate limiting."""
    IP = "ip"
    USER = "user"
    ENDPOINT = "endpoint"
    GLOBAL = "global"
    ADAPTIVE = "adaptive"

class RateLimitTier(Enum):
    """Rate limit tiers for different user levels."""
    BASIC = "basic"       # Default tier
    PREMIUM = "premium"   # Paid tier with higher limits
    ENTERPRISE = "enterprise"  # Enterprise tier with highest limits
    TRUSTED = "trusted"   # Internal or trusted services with minimal limits
    BLOCKED = "blocked"   # Blocked users with zero limit

@dataclass
class RateLimitRule:
    """Rate limit rule configuration."""
    key: str  # Identifier for this rule (e.g., "api.v1.tokens.get")
    limit: int  # Requests per window
    window: int = RATE_LIMIT_WINDOW_SECONDS  # Window in seconds
    burst: int = RATE_LIMIT_BURST  # Burst allowance
    tier_multipliers: Dict[RateLimitTier, float] = field(default_factory=lambda: {
        RateLimitTier.BASIC: 1.0,
        RateLimitTier.PREMIUM: 3.0,
        RateLimitTier.ENTERPRISE: 10.0,
        RateLimitTier.TRUSTED: 100.0,
        RateLimitTier.BLOCKED: 0.0
    })
    types: List[RateLimitType] = field(default_factory=lambda: [RateLimitType.IP, RateLimitType.USER])
    cost_function: Optional[callable] = None  # Function to calculate request cost

@dataclass
class RateLimitCounter:
    """Rate limit counter for token bucket algorithm."""
    tokens: float  # Current token count
    last_refill: float  # Timestamp of last refill
    limit: int  # Maximum tokens
    window: int  # Refill window in seconds
    request_count: int = 0  # Total request count
    blocked_count: int = 0  # Count of blocked requests
    
    def refill(self, now: float) -> None:
        """
        Refill tokens based on time elapsed.
        
        Args:
            now: Current timestamp
        """
        if now <= self.last_refill:
            return
        
        elapsed = now - self.last_refill
        refill_amount = (elapsed / self.window) * self.limit
        self.tokens = min(self.limit, self.tokens + refill_amount)
        self.last_refill = now

@dataclass
class RequestMetadata:
    """Metadata about an API request for rate limiting."""
    ip: str
    user_id: Optional[str] = None
    api_key: Optional[str] = None
    endpoint: str = ""
    method: str = "GET"
    path: str = "/"
    tier: RateLimitTier = RateLimitTier.BASIC
    timestamp: float = field(default_factory=time.time)
    user_agent: str = ""
    request_size: int = 0
    geo_country: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)

class IPReputationStatus(Enum):
    """IP reputation status."""
    GOOD = "good"
    SUSPICIOUS = "suspicious"
    BAD = "bad"
    UNKNOWN = "unknown"

@dataclass
class IPReputationData:
    """IP reputation data."""
    ip: str
    status: IPReputationStatus = IPReputationStatus.UNKNOWN
    score: float = 0.0  # 0.0 to 100.0, higher is better
    suspicious_activity_count: int = 0
    last_check: float = field(default_factory=time.time)
    country: Optional[str] = None
    is_proxy: bool = False
    is_tor: bool = False
    is_vpn: bool = False
    is_datacenter: bool = False

class RateLimiter:
    """
    Rate limiter implementation with token bucket algorithm.
    Supports IP-based, user-based, endpoint-based, and adaptive rate limiting.
    """
    
    def __init__(self):
        """Initialize the rate limiter."""
        # Counters by key (ip, user_id, etc.)
        self.ip_counters: Dict[str, RateLimitCounter] = {}
        self.user_counters: Dict[str, RateLimitCounter] = {}
        self.endpoint_counters: Dict[str, RateLimitCounter] = {}
        self.global_counter: RateLimitCounter = RateLimitCounter(
            tokens=RATE_LIMIT_MAX_TOKENS,
            last_refill=time.time(),
            limit=RATE_LIMIT_MAX_TOKENS,
            window=RATE_LIMIT_WINDOW_SECONDS
        )
        
        # User tiers
        self.user_tiers: Dict[str, RateLimitTier] = {}
        
        # IP reputation tracking
        self.ip_reputation: Dict[str, IPReputationData] = {}
        
        # Recent requests for pattern detection (sliding window)
        self.recent_requests: deque = deque(maxlen=1000)
        
        # Load restriction lists
        self.trusted_ips: Set[str] = set(RATE_LIMIT_TRUSTED_IPS)
        self.trusted_api_keys: Set[str] = set(RATE_LIMIT_TRUSTED_API_KEYS)
        self.ip_blacklist: Set[str] = set(RATE_LIMIT_IP_BLACKLIST)
        self.ip_whitelist: Set[str] = set(RATE_LIMIT_IP_WHITELIST)
        self.geo_restrictions: Dict[str, bool] = RATE_LIMIT_GEO_RESTRICTIONS
        
        # Rules by endpoint
        self.rules: Dict[str, RateLimitRule] = {}
        self.default_rule = RateLimitRule(
            key="default",
            limit=RATE_LIMIT_DEFAULT,
            window=RATE_LIMIT_WINDOW_SECONDS,
            burst=RATE_LIMIT_BURST
        )
        
        # Statistics
        self.total_requests = 0
        self.allowed_requests = 0
        self.blocked_requests = 0
        self.adaptive_limit_adjustments = 0
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    def add_rule(self, rule: RateLimitRule) -> None:
        """
        Add a rate limit rule.
        
        Args:
            rule: Rate limit rule
        """
        self.rules[rule.key] = rule
        logger.info(f"Added rate limit rule for {rule.key}: {rule.limit} requests per {rule.window}s")
    
    def set_user_tier(self, user_id: str, tier: RateLimitTier) -> None:
        """
        Set rate limit tier for a user.
        
        Args:
            user_id: User ID
            tier: Rate limit tier
        """
        self.user_tiers[user_id] = tier
        logger.info(f"Set rate limit tier for user {user_id} to {tier.value}")
    
    def get_user_tier(self, user_id: Optional[str], api_key: Optional[str] = None) -> RateLimitTier:
        """
        Get rate limit tier for a user.
        
        Args:
            user_id: User ID
            api_key: API key
            
        Returns:
            RateLimitTier: User's rate limit tier
        """
        # Check if API key is trusted
        if api_key and api_key in self.trusted_api_keys:
            return RateLimitTier.TRUSTED
        
        # Check user tier
        if user_id and user_id in self.user_tiers:
            return self.user_tiers[user_id]
        
        # Default to basic tier
        return RateLimitTier.BASIC
    
    async def check_ip_restrictions(self, ip: str, country: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check IP-based restrictions.
        
        Args:
            ip: IP address
            country: Country code
            
        Returns:
            Tuple[bool, str]: (allowed, reason)
        """
        # Check whitelist (always allow if on whitelist)
        if ip in self.ip_whitelist or self._is_ip_in_cidr_list(ip, self.ip_whitelist):
            return True, "IP on whitelist"
        
        # Check blacklist (always block if on blacklist)
        if ip in self.ip_blacklist or self._is_ip_in_cidr_list(ip, self.ip_blacklist):
            await self._update_ip_reputation(ip, suspicious=True)
            return False, "IP on blacklist"
        
        # Check geo restrictions
        if country and self.geo_restrictions.get(country) is False:
            await self._update_ip_reputation(ip, suspicious=True)
            return False, f"Country {country} is restricted"
        
        # Check IP reputation
        reputation = self._get_ip_reputation(ip)
        if reputation.status == IPReputationStatus.BAD:
            return False, "IP has bad reputation"
        
        # All checks passed
        return True, "IP allowed"
    
    def _is_ip_in_cidr_list(self, ip: str, cidr_list: Set[str]) -> bool:
        """
        Check if IP is in a list of CIDR ranges.
        
        Args:
            ip: IP address
            cidr_list: List of IP/CIDR entries
            
        Returns:
            bool: True if IP is in the CIDR list
        """
        try:
            ip_obj = ipaddress.ip_address(ip)
            for cidr in cidr_list:
                if "/" in cidr:  # CIDR notation
                    if ip_obj in ipaddress.ip_network(cidr, strict=False):
                        return True
                else:  # Single IP
                    if ip == cidr:
                        return True
            return False
        except ValueError:
            return False
    
    def _get_ip_reputation(self, ip: str) -> IPReputationData:
        """
        Get IP reputation data.
        
        Args:
            ip: IP address
            
        Returns:
            IPReputationData: IP reputation data
        """
        if ip not in self.ip_reputation:
            self.ip_reputation[ip] = IPReputationData(ip=ip)
        return self.ip_reputation[ip]
    
    async def _update_ip_reputation(self, ip: str, suspicious: bool = False) -> None:
        """
        Update IP reputation data.
        
        Args:
            ip: IP address
            suspicious: Whether activity is suspicious
        """
        async with self._lock:
            reputation = self._get_ip_reputation(ip)
            reputation.last_check = time.time()
            
            if suspicious:
                reputation.suspicious_activity_count += 1
            
            # Update status based on suspicious activity count
            if reputation.suspicious_activity_count >= 10:
                reputation.status = IPReputationStatus.BAD
                reputation.score = max(0.0, reputation.score - 10.0)
            elif reputation.suspicious_activity_count >= 3:
                reputation.status = IPReputationStatus.SUSPICIOUS
                reputation.score = max(20.0, reputation.score - 5.0)
            else:
                # Slowly improve reputation for IPs with good behavior
                reputation.score = min(100.0, reputation.score + 0.1)
                if reputation.score > 80.0:
                    reputation.status = IPReputationStatus.GOOD
    
    def _get_counter(self, key: str, limit: int, window: int, counter_type: str) -> RateLimitCounter:
        """
        Get or create a rate limit counter.
        
        Args:
            key: Counter key
            limit: Rate limit
            window: Window in seconds
            counter_type: Counter type
            
        Returns:
            RateLimitCounter: Rate limit counter
        """
        counters = getattr(self, f"{counter_type}_counters", {})
        if key not in counters:
            counters[key] = RateLimitCounter(
                tokens=limit,
                last_refill=time.time(),
                limit=limit,
                window=window
            )
        return counters[key]
    
    def _get_rule_for_endpoint(self, endpoint: str) -> RateLimitRule:
        """
        Get rate limit rule for an endpoint.
        
        Args:
            endpoint: API endpoint path
            
        Returns:
            RateLimitRule: Rate limit rule
        """
        # Check for exact match
        if endpoint in self.rules:
            return self.rules[endpoint]
        
        # Check for pattern match (e.g., "api.v1.tokens.*")
        parts = endpoint.split(".")
        for i in range(len(parts), 0, -1):
            pattern = ".".join(parts[:i]) + ".*"
            if pattern in self.rules:
                return self.rules[pattern]
        
        # Use default rule
        return self.default_rule
    
    def _calculate_effective_limit(self, rule: RateLimitRule, tier: RateLimitTier) -> int:
        """
        Calculate effective rate limit based on rule and tier.
        
        Args:
            rule: Rate limit rule
            tier: User tier
            
        Returns:
            int: Effective rate limit
        """
        multiplier = rule.tier_multipliers.get(tier, 1.0)
        return int(rule.limit * multiplier)
    
    async def check_rate_limit(self, metadata: RequestMetadata) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if a request is allowed based on rate limits.
        
        Args:
            metadata: Request metadata
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (allowed, rate_limit_info)
        """
        self.total_requests += 1
        now = time.time()
        
        # Add to recent requests for pattern detection
        self.recent_requests.append(metadata)
        
        # Get user tier
        tier = self.get_user_tier(metadata.user_id, metadata.api_key)
        metadata.tier = tier
        
        # Check IP restrictions
        ip_allowed, ip_reason = await self.check_ip_restrictions(metadata.ip, metadata.geo_country)
        if not ip_allowed:
            self.blocked_requests += 1
            return False, {"allowed": False, "reason": ip_reason, "tier": tier.value}
        
        # Check if trusted (bypass rate limits)
        if tier == RateLimitTier.TRUSTED or metadata.ip in self.trusted_ips:
            self.allowed_requests += 1
            return True, {"allowed": True, "tier": tier.value, "limit": "unlimited"}
        
        # Check if blocked tier
        if tier == RateLimitTier.BLOCKED:
            self.blocked_requests += 1
            return False, {"allowed": False, "reason": "User is blocked", "tier": tier.value}
        
        # Get rule for endpoint
        rule = self._get_rule_for_endpoint(metadata.endpoint)
        
        # Calculate effective limit
        effective_limit = self._calculate_effective_limit(rule, tier)
        effective_window = rule.window
        
        # Determine request cost (default is 1)
        request_cost = 1.0
        if rule.cost_function:
            request_cost = rule.cost_function(metadata)
        
        # Track all applicable rate limits
        limit_results = []
        
        # Endpoint limit
        if RateLimitType.ENDPOINT in rule.types:
            endpoint_key = metadata.endpoint
            endpoint_counter = self._get_counter(endpoint_key, effective_limit, effective_window, "endpoint")
            
            async with self._lock:
                endpoint_counter.refill(now)
                if endpoint_counter.tokens >= request_cost:
                    endpoint_counter.tokens -= request_cost
                    endpoint_counter.request_count += 1
                    endpoint_allowed = True
                else:
                    endpoint_counter.blocked_count += 1
                    endpoint_allowed = False
                
                limit_results.append(("endpoint", endpoint_allowed, endpoint_counter))
        
        # IP limit
        if RateLimitType.IP in rule.types:
            ip_key = metadata.ip
            ip_counter = self._get_counter(ip_key, effective_limit, effective_window, "ip")
            
            async with self._lock:
                ip_counter.refill(now)
                if ip_counter.tokens >= request_cost:
                    ip_counter.tokens -= request_cost
                    ip_counter.request_count += 1
                    ip_allowed = True
                else:
                    ip_counter.blocked_count += 1
                    ip_allowed = False
                    # Update IP reputation for excessive requests
                    await self._update_ip_reputation(metadata.ip, suspicious=True)
                
                limit_results.append(("ip", ip_allowed, ip_counter))
        
        # User limit (if user_id is available)
        if RateLimitType.USER in rule.types and metadata.user_id:
            user_key = metadata.user_id
            user_multiplier = RATE_LIMIT_USER_MULTIPLIER.get(tier.value, 1.0)
            user_limit = int(effective_limit * user_multiplier)
            user_counter = self._get_counter(user_key, user_limit, effective_window, "user")
            
            async with self._lock:
                user_counter.refill(now)
                if user_counter.tokens >= request_cost:
                    user_counter.tokens -= request_cost
                    user_counter.request_count += 1
                    user_allowed = True
                else:
                    user_counter.blocked_count += 1
                    user_allowed = False
                
                limit_results.append(("user", user_allowed, user_counter))
        
        # Global limit
        if RateLimitType.GLOBAL in rule.types:
            async with self._lock:
                self.global_counter.refill(now)
                if self.global_counter.tokens >= request_cost:
                    self.global_counter.tokens -= request_cost
                    self.global_counter.request_count += 1
                    global_allowed = True
                else:
                    self.global_counter.blocked_count += 1
                    global_allowed = False
                
                limit_results.append(("global", global_allowed, self.global_counter))
        
        # Check if any limit was exceeded
        allowed = all(result[1] for result in limit_results)
        
        # Build response
        response = {
            "allowed": allowed,
            "tier": tier.value,
            "limit": effective_limit,
            "window": effective_window,
            "limits": {}
        }
        
        for limit_type, limit_allowed, counter in limit_results:
            response["limits"][limit_type] = {
                "allowed": limit_allowed,
                "remaining": int(counter.tokens),
                "limit": counter.limit,
                "reset": int(now + (counter.window - ((now - counter.last_refill) % counter.window)))
            }
        
        # Update allowed/blocked counts
        if allowed:
            self.allowed_requests += 1
        else:
            self.blocked_requests += 1
            # Find the first limit that was exceeded
            for limit_type, limit_allowed, _ in limit_results:
                if not limit_allowed:
                    response["reason"] = f"{limit_type.capitalize()} rate limit exceeded"
                    break
        
        # Generate rate limit headers
        headers = {
            "X-RateLimit-Limit": str(effective_limit),
            "X-RateLimit-Remaining": str(int(min(counter.tokens for _, _, counter in limit_results))),
            "X-RateLimit-Reset": str(int(now + (effective_window - ((now - min(counter.last_refill for _, _, counter in limit_results)) % effective_window)))),
            "X-RateLimit-Resource": ", ".join(limit_type for limit_type, _, _ in limit_results)
        }
        response["headers"] = headers
        
        return allowed, response
    
    async def update_adaptive_limits(self) -> None:
        """
        Update adaptive rate limits based on traffic patterns.
        This should be called periodically to adjust limits.
        """
        now = time.time()
        
        # Calculate traffic metrics
        total_traffic = sum(counter.request_count for counter in self.ip_counters.values())
        blocked_traffic = sum(counter.blocked_count for counter in self.ip_counters.values())
        
        # Skip adjustment if not enough traffic
        if total_traffic < 100:
            return
        
        block_ratio = blocked_traffic / max(1, total_traffic)
        
        # Adjust global limit based on block ratio
        async with self._lock:
            if block_ratio > 0.2:  # Too many blocks
                # Increase limit to reduce blocks
                new_limit = int(self.global_counter.limit * 1.1)
                logger.info(f"Increasing global rate limit to {new_limit} (block ratio: {block_ratio:.2f})")
                self.global_counter.limit = new_limit
                self.adaptive_limit_adjustments += 1
            elif block_ratio < 0.05 and self.global_counter.limit > RATE_LIMIT_DEFAULT:
                # Decrease limit if very few blocks
                new_limit = max(RATE_LIMIT_DEFAULT, int(self.global_counter.limit * 0.95))
                logger.info(f"Decreasing global rate limit to {new_limit} (block ratio: {block_ratio:.2f})")
                self.global_counter.limit = new_limit
                self.adaptive_limit_adjustments += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics.
        
        Returns:
            Dict[str, Any]: Rate limiter statistics
        """
        block_ratio = self.blocked_requests / max(1, self.total_requests)
        
        return {
            "total_requests": self.total_requests,
            "allowed_requests": self.allowed_requests,
            "blocked_requests": self.blocked_requests,
            "block_ratio": block_ratio,
            "ip_counters": len(self.ip_counters),
            "user_counters": len(self.user_counters),
            "endpoint_counters": len(self.endpoint_counters),
            "global_limit": self.global_counter.limit,
            "global_tokens": self.global_counter.tokens,
            "adaptive_adjustments": self.adaptive_limit_adjustments,
            "blacklist_size": len(self.ip_blacklist),
            "whitelist_size": len(self.ip_whitelist),
            "trusted_ips": len(self.trusted_ips),
            "rules": len(self.rules)
        }

# Singleton instance
rate_limiter = RateLimiter() 