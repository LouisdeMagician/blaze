"""
RPC Provider abstraction for Blaze Analyst.
Manages multiple Solana RPC providers with health checks and failover capabilities.
"""
import logging
import time
import threading
import random
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple

import requests
from solana.rpc.api import Client as SolanaClient

from config.config import config

logger = logging.getLogger(__name__)

class ProviderStatus(Enum):
    """Status of an RPC provider."""
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class RPCProvider:
    """Represents an individual RPC provider."""
    
    def __init__(self, name: str, url: str, priority: int = 1, weight: int = 1):
        """
        Initialize an RPC provider.
        
        Args:
            name: Provider name/identifier
            url: RPC endpoint URL
            priority: Provider priority (lower number = higher priority)
            weight: Provider weight for load balancing (higher = more requests)
        """
        self.name = name
        self.url = url
        self.priority = priority
        self.weight = weight
        self.status = ProviderStatus.UNKNOWN
        self.client = SolanaClient(url)
        
        # Health check metrics
        self.last_checked = 0
        self.last_successful_request = 0
        self.response_times = []  # Last 10 response times in ms
        self.error_count = 0
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        
        # Rate limiting
        self.request_count = 0
        self.last_reset = time.time()
    
    def update_health(self, status: ProviderStatus) -> None:
        """
        Update provider health status.
        
        Args:
            status: New provider status
        """
        if self.status != status:
            logger.info(f"Provider {self.name} status changed from {self.status.value} to {status.value}")
            self.status = status
    
    def record_response_time(self, response_time_ms: float) -> None:
        """
        Record a response time for the provider.
        
        Args:
            response_time_ms: Response time in milliseconds
        """
        self.response_times.append(response_time_ms)
        if len(self.response_times) > 10:
            self.response_times.pop(0)
    
    def get_average_response_time(self) -> float:
        """
        Get the average response time for the provider.
        
        Returns:
            float: Average response time in milliseconds, or 0 if no data
        """
        if not self.response_times:
            return 0
        return sum(self.response_times) / len(self.response_times)
    
    def is_healthy(self) -> bool:
        """
        Check if the provider is considered healthy.
        
        Returns:
            bool: True if provider is healthy, False otherwise
        """
        return self.status in [ProviderStatus.HEALTHY, ProviderStatus.DEGRADED]
    
    def record_success(self) -> None:
        """Record a successful request."""
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        self.last_successful_request = time.time()
        
        # Update status based on consecutive successes
        if self.consecutive_successes >= 3:
            if self.status == ProviderStatus.DEGRADED and self.consecutive_successes >= 5:
                self.update_health(ProviderStatus.HEALTHY)
            elif self.status == ProviderStatus.UNHEALTHY:
                self.update_health(ProviderStatus.DEGRADED)
            elif self.status == ProviderStatus.UNKNOWN:
                self.update_health(ProviderStatus.HEALTHY)
    
    def record_failure(self) -> None:
        """Record a failed request."""
        self.consecutive_successes = 0
        self.consecutive_failures += 1
        self.error_count += 1
        
        # Update status based on consecutive failures
        if self.consecutive_failures >= 3:
            if self.status == ProviderStatus.HEALTHY:
                self.update_health(ProviderStatus.DEGRADED)
            elif self.consecutive_failures >= 5:
                self.update_health(ProviderStatus.UNHEALTHY)
    
    def is_rate_limited(self) -> bool:
        """
        Check if provider is rate limited.
        
        Returns:
            bool: True if provider is rate limited, False otherwise
        """
        now = time.time()
        
        # Reset counter if window has passed (1 minute)
        if now - self.last_reset > 60:
            self.request_count = 0
            self.last_reset = now
            return False
        
        # Check if we're exceeding rate limit
        # This is a simple implementation - adjust based on provider limits
        return self.request_count > 50  # Example: 50 requests per minute


class ProviderManager:
    """Manages multiple RPC providers with health checks and failover."""
    
    def __init__(self):
        """Initialize the provider manager."""
        self.providers: Dict[str, RPCProvider] = {}
        self.last_used = None
        self.lock = threading.Lock()
        self.health_check_interval = 30  # seconds
        self.health_check_thread = None
        self.running = False
        
        # Initialize providers
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Initialize RPC providers from configuration."""
        # Add primary provider
        primary_url = config['solana']['rpc_url']
        if primary_url:
            self.add_provider("primary", primary_url, priority=1, weight=3)
        else:
            logger.warning("No primary RPC URL configured")
        
        # Add backup provider if available
        backup_url = config['solana']['backup_rpc_url']
        if backup_url:
            self.add_provider("backup", backup_url, priority=2, weight=1)
        
        # Add additional providers from config (if any)
        additional_providers = config.get('solana', {}).get('additional_providers', [])
        for i, provider in enumerate(additional_providers):
            if 'url' in provider:
                self.add_provider(
                    provider.get('name', f"provider_{i+3}"),
                    provider['url'],
                    priority=provider.get('priority', i+3),
                    weight=provider.get('weight', 1)
                )
    
    def add_provider(self, name: str, url: str, priority: int = 10, weight: int = 1) -> None:
        """
        Add a new RPC provider.
        
        Args:
            name: Provider name/identifier
            url: RPC endpoint URL
            priority: Provider priority (lower = higher priority)
            weight: Provider weight for load balancing
        """
        with self.lock:
            if name in self.providers:
                logger.warning(f"Provider {name} already exists. Updating configuration.")
            
            self.providers[name] = RPCProvider(name, url, priority, weight)
            logger.info(f"Added RPC provider: {name} ({url})")
    
    def remove_provider(self, name: str) -> None:
        """
        Remove an RPC provider.
        
        Args:
            name: Provider name/identifier
        """
        with self.lock:
            if name in self.providers:
                del self.providers[name]
                logger.info(f"Removed RPC provider: {name}")
    
    def get_provider(self, strategy: str = "priority") -> RPCProvider:
        """
        Get an RPC provider using the specified selection strategy.
        
        Args:
            strategy: Provider selection strategy:
                     "priority" - Select highest priority healthy provider
                     "round_robin" - Round-robin selection among healthy providers
                     "weighted" - Weighted random selection
                     
        Returns:
            RPCProvider: Selected provider
            
        Raises:
            RuntimeError: If no healthy providers are available
        """
        with self.lock:
            # Filter healthy providers
            healthy_providers = [p for p in self.providers.values() if p.is_healthy() and not p.is_rate_limited()]
            
            # If no healthy providers, try any provider not rate limited
            if not healthy_providers:
                logger.warning("No healthy providers available. Trying any available provider.")
                healthy_providers = [p for p in self.providers.values() if not p.is_rate_limited()]
            
            # If still no providers, raise error
            if not healthy_providers:
                raise RuntimeError("No available RPC providers")
            
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
            
            else:  # Default to priority
                # Sort by priority and select highest priority (lowest number)
                provider = sorted(healthy_providers, key=lambda p: p.priority)[0]
            
            # Update last used provider
            self.last_used = provider.name
            
            # Increment request count for rate limiting
            provider.request_count += 1
            
            return provider
    
    def start_health_checks(self) -> None:
        """Start the health check background thread."""
        if self.running:
            return
        
        self.running = True
        self.health_check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.health_check_thread.start()
        logger.info("Started RPC provider health check thread")
    
    def stop_health_checks(self) -> None:
        """Stop the health check background thread."""
        self.running = False
        if self.health_check_thread:
            self.health_check_thread.join(timeout=1.0)
            self.health_check_thread = None
        logger.info("Stopped RPC provider health check thread")
    
    def _health_check_loop(self) -> None:
        """Background loop for periodic health checks."""
        while self.running:
            try:
                self._check_all_providers()
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
            
            # Sleep until next check interval
            for _ in range(self.health_check_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def _check_all_providers(self) -> None:
        """Check health of all providers."""
        for name, provider in list(self.providers.items()):
            try:
                self._check_provider_health(provider)
            except Exception as e:
                logger.error(f"Error checking health of provider {name}: {e}")
    
    def _check_provider_health(self, provider: RPCProvider) -> None:
        """
        Check health of a specific provider.
        
        Args:
            provider: Provider to check
        """
        provider.last_checked = time.time()
        
        try:
            # Simple health check: get recent block hash
            start_time = time.time()
            response = provider.client.get_recent_blockhash()
            end_time = time.time()
            
            # Calculate response time in milliseconds
            response_time_ms = (end_time - start_time) * 1000
            
            # Check if response contains expected data
            if 'result' in response and 'value' in response['result']:
                # Record metrics
                provider.record_response_time(response_time_ms)
                provider.record_success()
                
                # Evaluate health based on response time
                avg_response_time = provider.get_average_response_time()
                if avg_response_time > 500:  # More than 500ms average response time
                    provider.update_health(ProviderStatus.DEGRADED)
                
                logger.debug(f"Provider {provider.name} is healthy. Response time: {response_time_ms:.2f}ms")
            else:
                # Invalid response
                provider.record_failure()
                logger.warning(f"Provider {provider.name} returned invalid response")
        
        except Exception as e:
            provider.record_failure()
            logger.warning(f"Provider {provider.name} health check failed: {e}")


class SolanaProviderClient:
    """Client for interacting with Solana using the provider manager."""
    
    def __init__(self):
        """Initialize the Solana provider client."""
        self.provider_manager = ProviderManager()
        self.provider_manager.start_health_checks()
    
    def __del__(self):
        """Clean up resources on deletion."""
        self.provider_manager.stop_health_checks()
    
    def call_method(self, method_name: str, *args, **kwargs) -> Dict:
        """
        Call a Solana RPC method using the provider manager.
        
        Args:
            method_name: Name of the RPC method to call
            *args: Arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method
            
        Returns:
            Dict: Result of the RPC call
            
        Raises:
            Exception: If all providers fail
        """
        # Get provider using round-robin strategy for load balancing
        provider = self.provider_manager.get_provider(strategy="round_robin")
        
        try:
            # Get the method to call
            method = getattr(provider.client, method_name)
            
            # Call the method
            start_time = time.time()
            result = method(*args, **kwargs)
            end_time = time.time()
            
            # Record metrics
            response_time_ms = (end_time - start_time) * 1000
            provider.record_response_time(response_time_ms)
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
                fallback_provider = self.provider_manager.get_provider(strategy="priority")
                method = getattr(fallback_provider.client, method_name)
                result = method(*args, **kwargs)
                
                # Record success for fallback
                fallback_provider.record_success()
                
                return result
            except Exception as fallback_error:
                # Record failure for fallback
                fallback_provider.record_failure()
                
                # Propagate original error
                raise Exception(f"All providers failed for method {method_name}. Original error: {e}") from e


# Singleton instance
solana_provider = SolanaProviderClient() 