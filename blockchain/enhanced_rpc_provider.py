��"""
Enhanced RPC Provider for Blaze Analyst.
Implements advanced reliability features including circuit breakers, exponential backoff,
adaptive retry, improved load balancing, and performance monitoring.
"""
import logging
import time
import threading
import random
import asyncio
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
import functools

import requests
from solana.rpc.api import Client as SolanaClient

from src.utils.circuit_breaker import CircuitBreaker, circuit_breaker_registry
from src.utils.settings import (
    RPC_ENDPOINT,
    FALLBACK_RPC_ENDPOINTS,
    RPC_MAX_RETRIES,
    RPC_BASE_RETRY_DELAY,
    RPC_MAX_RETRY_DELAY,
    RPC_JITTER_FACTOR,
    RPC_HEALTH_CHECK_INTERVAL,
    RPC_CIRCUIT_FAILURE_THRESHOLD,
    RPC_CIRCUIT_RECOVERY_TIMEOUT,
    RPC_CONNECTION_TIMEOUT,
    RPC_MAX_CAPACITY_PER_PROVIDER,
    RPC_LOAD_BALANCING_STRATEGY
)
from src.blockchain.rpc_provider import ProviderStatus, RPCProvider, ProviderManager

logger = logging.getLogger(__name__)

class EnhancedRPCProvider(RPCProvider):
    """Enhanced RPC provider with advanced reliability features."""
    
    def __init__(self, name: str, url: str, priority: int = 1, weight: int = 1, 
                 capacity: int = RPC_MAX_CAPACITY_PER_PROVIDER):
        """
        Initialize an enhanced RPC provider.
        
        Args:
            name: Provider name/identifier
            url: RPC endpoint URL
            priority: Provider priority (lower number = higher priority)
            weight: Provider weight for load balancing (higher = more requests)
            capacity: Maximum concurrent requests (capacity limit)
        """
        super().__init__(name, url, priority, weight)
        
        # Capacity tracking
        self.capacity = capacity
        self.current_load = 0
        self.load_lock = asyncio.Lock()
        
        # Method-specific stats
        self.method_stats = {}
        
        # Circuit breaker
        self.circuit_breaker = circuit_breaker_registry.create_breaker(
            name=f"rpc_provider_{name}",
            failure_threshold=RPC_CIRCUIT_FAILURE_THRESHOLD,
            recovery_timeout=RPC_CIRCUIT_RECOVERY_TIMEOUT,
            timeout=RPC_CONNECTION_TIMEOUT
        )
    
    async def is_at_capacity(self) -> bool:
        """Check if provider is at capacity."""
        async with self.load_lock:
            return self.current_load >= self.capacity
    
    async def increment_load(self) -> None:
        """Increment current load."""
        async with self.load_lock:
            self.current_load += 1
    
    async def decrement_load(self) -> None:
        """Decrement current load."""
        async with self.load_lock:
            self.current_load = max(0, self.current_load - 1)
    
    async def call_method(
        self, 
        method_name: str, 
        params: List[Any] = None, 
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Call an RPC method with circuit breaker protection and retry logic.
        
        Args:
            method_name: RPC method name
            params: Method parameters
            retry_count: Current retry count
            
        Returns:
            Dict: RPC response
            
        Raises:
            Exception: If the call fails after retries
        """
        # Check capacity before proceeding
        if await self.is_at_capacity():
            logger.warning(f"Provider {self.name} at capacity ({self.capacity}), rejecting {method_name}")
            raise RuntimeError(f"Provider {self.name} at capacity")
        
        # Increment load counter
        await self.increment_load()
        
        start_time = time.time()
        try:
            # Use circuit breaker to protect the call
            result = await self.circuit_breaker.execute(
                self._execute_rpc_call,
                method_name=method_name,
                params=params or []
            )
            
            # Record success
            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # Convert to ms
            
            self.record_response_time(response_time)
            self.record_success()
            
            return result
            
        except Exception as e:
            # Determine if we should retry
            should_retry = retry_count < RPC_MAX_RETRIES
            
            # Calculate retry delay with exponential backoff and jitter
            if should_retry:
                # Exponential backoff: delay = base_delay * (2 ^ retry_count)
                delay = RPC_BASE_RETRY_DELAY * (2 ** retry_count)
                # Add jitter to prevent thundering herd
                jitter = random.uniform(-RPC_JITTER_FACTOR, RPC_JITTER_FACTOR) * delay
                delay = min(delay + jitter, RPC_MAX_RETRY_DELAY)
                
                logger.warning(
                    f"Provider {self.name} call to {method_name} failed (retry {retry_count + 1}/{RPC_MAX_RETRIES}): {e}"
                    f" Will retry in {delay:.2f}s"
                )
                
                # Record failure for this attempt
                self.record_failure()
                
                # Wait before retry
                await asyncio.sleep(delay)
                
                # Recursive retry with incremented count
                return await self.call_method(method_name, params, retry_count + 1)
            
            # If we're out of retries, record the final failure and raise
            self.record_failure()
            
            logger.error(f"Provider {self.name} call to {method_name} failed after {RPC_MAX_RETRIES} retries: {e}")
            raise
            
        finally:
            # Ensure we always decrement the load counter
            await self.decrement_load()
    
    async def _execute_rpc_call(self, method_name: str, params: List[Any]) -> Dict[str, Any]:
        """
        Execute the actual RPC call.
        
        Args:
            method_name: RPC method name
            params: Method parameters
            
        Returns:
            Dict: RPC response
        """
        # Prepare JSON-RPC request
        payload = {
            "jsonrpc": "2.0",
            "id": random.randint(1, 10000),
            "method": method_name,
            "params": params or []
        }
        
        # Make the request
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(
            self.url, 
            json=payload, 
            headers=headers, 
            timeout=RPC_CONNECTION_TIMEOUT
        )
        
        # Check for HTTP errors
        response.raise_for_status()
        
        # Parse response
        result = response.json()
        
        # Check for JSON-RPC errors
        if "error" in result:
            error = result["error"]
            error_message = error.get("message", "Unknown JSON-RPC error")
            error_code = error.get("code", -1)
            raise RuntimeError(f"JSON-RPC error {error_code}: {error_message}")
        
        return result
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """
        Get detailed provider statistics.
        
        Returns:
            Dict: Detailed statistics
        """
        # Basic stats
        stats = {
            "name": self.name,
            "url": self.url,
            "priority": self.priority,
            "weight": self.weight,
            "status": self.status.value,
            "capacity": self.capacity,
            "current_load": self.current_load,
            "total_requests": self.request_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(1, self.request_count),
            "avg_response_time_ms": self.get_average_response_time(),
            "consecutive_successes": self.consecutive_successes,
            "consecutive_failures": self.consecutive_failures,
            "last_checked": self.last_checked,
            "last_successful_request": self.last_successful_request
        }
        
        # Circuit breaker stats
        circuit_stats = self.circuit_breaker.get_stats()
        stats["circuit_breaker"] = {
            "state": circuit_stats["state"],
            "failure_count": circuit_stats["failure_count"],
            "rejected_calls": circuit_stats["rejected_calls"],
            "successful_calls": circuit_stats["successful_calls"],
            "failed_calls": circuit_stats["failed_calls"]
        }
        
        return stats


class EnhancedProviderManager(ProviderManager):
    """Enhanced provider manager with advanced reliability features."""
    
    def __init__(self):
        """Initialize the enhanced provider manager."""
        super().__init__()
        self.provider_selection_metrics = {
            "strategy_counts": {
                "priority": 0,
                "round_robin": 0,
                "weighted": 0,
                "least_loaded": 0,
                "performance": 0
            },
            "provider_selections": {}
        }
    
    def _initialize_providers(self) -> None:
        """Initialize enhanced RPC providers from configuration."""
        # Add primary provider
        if RPC_ENDPOINT:
            self.add_enhanced_provider(
                "primary", 
                RPC_ENDPOINT, 
                priority=1, 
                weight=3
            )
        else:
            logger.warning("No primary RPC URL configured")
        
        # Add fallback providers
        for i, url in enumerate(FALLBACK_RPC_ENDPOINTS):
            if url:
                self.add_enhanced_provider(
                    f"fallback_{i+1}",
                    url,
                    priority=i+2,
                    weight=2
                )
    
    def add_enhanced_provider(
        self, 
        name: str, 
        url: str, 
        priority: int = 10, 
        weight: int = 1,
        capacity: int = RPC_MAX_CAPACITY_PER_PROVIDER
    ) -> None:
        """
        Add a new enhanced RPC provider.
        
        Args:
            name: Provider name/identifier
            url: RPC endpoint URL
            priority: Provider priority (lower = higher priority)
            weight: Provider weight for load balancing
            capacity: Maximum concurrent requests
        """
        with self.lock:
            if name in self.providers:
                logger.warning(f"Provider {name} already exists. Updating configuration.")
            
            self.providers[name] = EnhancedRPCProvider(name, url, priority, weight, capacity)
            logger.info(f"Added enhanced RPC provider: {name} ({url})")
            
            # Initialize selection metrics
            self.provider_selection_metrics["provider_selections"][name] = 0
    
    async def get_provider(self, strategy: str = RPC_LOAD_BALANCING_STRATEGY) -> RPCProvider:
        """
        Get an RPC provider using the specified selection strategy.
        
        Args:
            strategy: Provider selection strategy:
                     "priority" - Select highest priority healthy provider
                     "round_robin" - Round-robin selection among healthy providers
                     "weighted" - Weighted random selection
                     "least_loaded" - Select provider with least load
                     "performance" - Select provider with best performance
                     
        Returns:
            RPCProvider: Selected provider
            
        Raises:
            RuntimeError: If no healthy providers are available
        """
        with self.lock:
            # Update strategy metrics
            self.provider_selection_metrics["strategy_counts"][strategy] = \
                self.provider_selection_metrics["strategy_counts"].get(strategy, 0) + 1
            
            # Filter healthy providers
            healthy_providers = [p for p in self.providers.values() 
                               if p.is_healthy() and not p.is_rate_limited()]
            
            # Check for enhanced providers that are at capacity
            if all(isinstance(p, EnhancedRPCProvider) for p in healthy_providers):
                # Filter out providers at capacity
                available_providers = []
                for provider in healthy_providers:
                    # Need to cast to EnhancedRPCProvider for type checking
                    enhanced_provider = provider  # type: EnhancedRPCProvider
                    if not await enhanced_provider.is_at_capacity():
                        available_providers.append(provider)
                
                if available_providers:
                    healthy_providers = available_providers
            
            # If no healthy providers, try any provider not rate limited
            if not healthy_providers:
                logger.warning("No healthy providers available. Trying any available provider.")
                healthy_providers = [p for p in self.providers.values() if not p.is_rate_limited()]
            
            # If still no providers, raise error
            if not healthy_providers:
                raise RuntimeError("No available RPC providers")
            
            # Select provider based on strategy
            if strategy == "round_robin":
                # Simple round-robin: pick the next provider after the last used one
                if self.last_used in [p.name for p in healthy_providers]:
                    last_idx = next(i for i, p in enumerate(healthy_providers) if p.name == self.last_used)
                    provider = healthy_providers[(last_idx + 1) % len(healthy_providers)]
                else:
                    provider = healthy_providers[0]
                
            elif strategy == "weighted":
                # Weighted random selection
                weights = [p.weight for p in healthy_providers]
                total_weight = sum(weights)
                if total_weight == 0:
                    provider = random.choice(healthy_providers)
                else:
                    # Select based on weights
                    r = random.uniform(0, total_weight)
                    cumulative_weight = 0
                    for i, p in enumerate(healthy_providers):
                        cumulative_weight += p.weight
                        if r <= cumulative_weight:
                            provider = p
                            break
                    else:
                        provider = healthy_providers[-1]
            
            elif strategy == "least_loaded":
                # Select provider with least load
                if all(isinstance(p, EnhancedRPCProvider) for p in healthy_providers):
                    # Sort by current load (lowest first)
                    provider = min(healthy_providers, key=lambda p: p.current_load)
                else:
                    # Fallback to priority if not all providers are enhanced
                    provider = sorted(healthy_providers, key=lambda p: p.priority)[0]
            
            elif strategy == "performance":
                # Select provider with best performance (lowest average response time)
                provider = min(healthy_providers, key=lambda p: p.get_average_response_time() or float('inf'))
            
            else:  # Default to priority
                # Sort by priority and select highest priority (lowest number)
                provider = sorted(healthy_providers, key=lambda p: p.priority)[0]
            
            # Update last used provider
            self.last_used = provider.name
            
            # Update selection metrics
            self.provider_selection_metrics["provider_selections"][provider.name] = \
                self.provider_selection_metrics["provider_selections"].get(provider.name, 0) + 1
            
            # Increment request count for rate limiting
            provider.request_count += 1
            
            return provider
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """
        Get manager statistics.
        
        Returns:
            Dict: Manager statistics
        """
        stats = {
            "providers": {
                name: provider.get_detailed_stats() if isinstance(provider, EnhancedRPCProvider) 
                else {"name": name, "status": provider.status.value}
                for name, provider in self.providers.items()
            },
            "last_used": self.last_used,
            "provider_selection_metrics": self.provider_selection_metrics
        }
        
        return stats


class EnhancedSolanaProviderClient:
    """Enhanced client for interacting with Solana using the provider manager."""
    
    def __init__(self):
        """Initialize the enhanced Solana provider client."""
        self.provider_manager = EnhancedProviderManager()
        self.provider_manager.start_health_checks()
    
    def __del__(self):
        """Clean up resources on deletion."""
        self.provider_manager.stop_health_checks()
    
    async def call_method(
        self, 
        method_name: str, 
        params: List[Any] = None, 
        strategy: str = RPC_LOAD_BALANCING_STRATEGY
    ) -> Dict[str, Any]:
        """
        Call a Solana RPC method using the provider manager.
        
        Args:
            method_name: Name of the RPC method to call
            params: Parameters to pass to the method
            strategy: Provider selection strategy
            
        Returns:
            Dict: Result of the RPC call
            
        Raises:
            Exception: If all providers fail
        """
        # Get provider using specified strategy
        provider = await self.provider_manager.get_provider(strategy=strategy)
        
        if isinstance(provider, EnhancedRPCProvider):
            # Use enhanced provider's call_method
            try:
                return await provider.call_method(method_name, params)
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed for method {method_name}: {e}. Trying another provider.")
                
                # Mark provider as unhealthy temporarily
                provider.update_health(ProviderStatus.UNHEALTHY)
                
                # Try another provider
                try:
                    fallback_provider = await self.provider_manager.get_provider(strategy="priority")
                    if isinstance(fallback_provider, EnhancedRPCProvider):
                        return await fallback_provider.call_method(method_name, params)
                    else:
                        # Fallback to original implementation for non-enhanced providers
                        method = getattr(fallback_provider.client, method_name)
                        return method(*params) if params else method()
                except Exception as fallback_error:
                    raise Exception(f"All providers failed for method {method_name}. Error: {e}") from e
        else:
            # Fallback to original implementation for non-enhanced providers
            try:
                method = getattr(provider.client, method_name)
                result = method(*params) if params else method()
                
                # Record success
                provider.record_success()
                
                return result
            except Exception as e:
                # Record failure
                provider.record_failure()
                
                # Try another provider
                logger.warning(f"Provider {provider.name} failed for method {method_name}: {e}. Trying another provider.")
                
                # Remove current provider from consideration temporarily by marking it unhealthy
                provider.update_health(ProviderStatus.UNHEALTHY)
                
                # Retry with different provider
                try:
                    fallback_provider = await self.provider_manager.get_provider(strategy="priority")
                    method = getattr(fallback_provider.client, method_name)
                    result = method(*params) if params else method()
                    
                    # Record success for fallback
                    fallback_provider.record_success()
                    
                    return result
                except Exception as fallback_error:
                    # Record failure for fallback
                    fallback_provider.record_failure()
                    
                    # Propagate original error
                    raise Exception(f"All providers failed for method {method_name}. Error: {e}") from e
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """
        Get provider manager statistics.
        
        Returns:
            Dict: Manager statistics
        """
        return self.provider_manager.get_manager_stats()


# Singleton instance
enhanced_solana_provider = EnhancedSolanaProviderClient()
