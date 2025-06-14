"""
Circuit Breaker Pattern Implementation.
Provides fault tolerance for external service calls.
"""
import asyncio
import logging
import time
from enum import Enum
from typing import Callable, Any, Optional, Dict, TypeVar, Generic, List, Tuple
import functools
import random

logger = logging.getLogger(__name__)

T = TypeVar("T")

class CircuitState(Enum):
    """Possible states for a circuit breaker."""
    CLOSED = "closed"  # Normal operation, allowing requests
    OPEN = "open"      # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CircuitBreaker(Generic[T]):
    """
    Circuit breaker implementation for fault tolerance.
    
    The circuit breaker pattern prevents cascading failures and allows
    graceful degradation when external services are experiencing issues.
    """
    
    def __init__(
        self, 
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        half_open_success_threshold: int = 2,
        timeout: float = 10.0,
        exclude_exceptions: List[type] = None,
        fallback: Optional[Callable[..., T]] = None
    ):
        """
        Initialize a circuit breaker.
        
        Args:
            name: Identifier for this circuit breaker
            failure_threshold: Number of consecutive failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery (half-open)
            half_open_max_calls: Maximum calls allowed in half-open state
            half_open_success_threshold: Successes needed to close circuit
            timeout: Default timeout for operations in seconds
            exclude_exceptions: Exception types that won't count as failures
            fallback: Optional fallback function to call when circuit is open
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.half_open_success_threshold = half_open_success_threshold
        self.timeout = timeout
        self.exclude_exceptions = exclude_exceptions or []
        self.fallback = fallback
        
        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.last_state_change_time = time.time()
        self.half_open_calls = 0
        
        # Stats
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.rejected_calls = 0
        self.fallback_calls = 0
        self.response_times: List[float] = []
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function call or fallback
            
        Raises:
            Exception: If circuit is open and no fallback is provided
        """
        self.total_calls += 1
        
        # Check if circuit is open
        if await self._is_open():
            self.rejected_calls += 1
            logger.warning(f"Circuit {self.name} is open, rejecting call")
            if self.fallback:
                self.fallback_calls += 1
                return await self._call_fallback(*args, **kwargs)
            raise CircuitOpenError(f"Circuit {self.name} is open")
        
        # Handle half-open state
        if await self._is_half_open():
            if self.half_open_calls >= self.half_open_max_calls:
                self.rejected_calls += 1
                logger.warning(f"Circuit {self.name} is half-open and at max calls, rejecting")
                if self.fallback:
                    self.fallback_calls += 1
                    return await self._call_fallback(*args, **kwargs)
                raise CircuitOpenError(f"Circuit {self.name} is half-open and at max calls")
            
            async with self._lock:
                self.half_open_calls += 1
        
        # Execute the function with timing
        start_time = time.time()
        try:
            # Add timeout to prevent long-running calls
            result = await asyncio.wait_for(
                self._call_function(func, *args, **kwargs),
                timeout=self.timeout
            )
            
            # Record success
            execution_time = time.time() - start_time
            await self._record_success(execution_time)
            return result
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            await self._record_failure(CircuitTimeoutError("Operation timed out"), execution_time)
            if self.fallback:
                self.fallback_calls += 1
                return await self._call_fallback(*args, **kwargs)
            raise CircuitTimeoutError(f"Operation in circuit {self.name} timed out after {self.timeout}s")
            
        except Exception as e:
            execution_time = time.time() - start_time
            # Check if exception should be excluded
            if any(isinstance(e, exc_type) for exc_type in self.exclude_exceptions):
                logger.debug(f"Excluded exception in circuit {self.name}: {e}")
                # Don't count excluded exceptions as failures
                await self._record_success(execution_time)
                raise
                
            await self._record_failure(e, execution_time)
            if self.fallback:
                self.fallback_calls += 1
                return await self._call_fallback(*args, **kwargs)
            raise
    
    async def _call_function(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Call the target function, handling both async and sync functions."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    
    async def _call_fallback(self, *args, **kwargs) -> T:
        """Call the fallback function if provided."""
        if not self.fallback:
            raise ValueError("No fallback function provided")
            
        if asyncio.iscoroutinefunction(self.fallback):
            return await self.fallback(*args, **kwargs)
        else:
            return self.fallback(*args, **kwargs)
    
    async def _is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                # Transition to half-open
                async with self._lock:
                    if self.state == CircuitState.OPEN:
                        await self._transition_to_half_open()
                    return False
            return True
        return False
    
    async def _is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN
    
    async def _record_success(self, execution_time: float) -> None:
        """Record a successful operation."""
        self.successful_calls += 1
        self.response_times.append(execution_time)
        if len(self.response_times) > 100:
            self.response_times.pop(0)
        
        async with self._lock:
            if self.state == CircuitState.CLOSED:
                # Reset failure counter in closed state
                self.failure_count = 0
            elif self.state == CircuitState.HALF_OPEN:
                # In half-open state, count successes towards recovery
                self.success_count += 1
                if self.success_count >= self.half_open_success_threshold:
                    await self._transition_to_closed()
    
    async def _record_failure(self, exception: Exception, execution_time: float) -> None:
        """Record a failed operation."""
        self.failed_calls += 1
        self.last_failure_time = time.time()
        
        async with self._lock:
            self.failure_count += 1
            
            # Check if we need to open the circuit
            if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
                await self._transition_to_open()
            elif self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open state opens the circuit again
                await self._transition_to_open()
    
    async def _transition_to_open(self) -> None:
        """Transition to open state."""
        logger.warning(f"Circuit {self.name} transitioning to OPEN state after {self.failure_count} failures")
        self.state = CircuitState.OPEN
        self.last_state_change_time = time.time()
    
    async def _transition_to_half_open(self) -> None:
        """Transition to half-open state."""
        logger.info(f"Circuit {self.name} transitioning to HALF-OPEN state after {self.recovery_timeout}s")
        self.state = CircuitState.HALF_OPEN
        self.last_state_change_time = time.time()
        self.half_open_calls = 0
        self.success_count = 0
    
    async def _transition_to_closed(self) -> None:
        """Transition to closed state."""
        logger.info(f"Circuit {self.name} transitioning to CLOSED state after {self.success_count} successful calls")
        self.state = CircuitState.CLOSED
        self.last_state_change_time = time.time()
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "fallback_calls": self.fallback_calls,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "half_open_calls": self.half_open_calls,
            "last_failure_time": self.last_failure_time,
            "last_state_change_time": self.last_state_change_time,
            "avg_response_time_ms": avg_response_time * 1000,
        }
    
    def reset(self) -> None:
        """Reset the circuit breaker state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.last_state_change_time = time.time()
        self.half_open_calls = 0


class CircuitOpenError(Exception):
    """Exception raised when a circuit is open."""
    pass


class CircuitTimeoutError(Exception):
    """Exception raised when a circuit operation times out."""
    pass


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    _instance = None
    _breakers: Dict[str, CircuitBreaker] = {}
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super(CircuitBreakerRegistry, cls).__new__(cls)
        return cls._instance
    
    def get_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name."""
        return self._breakers.get(name)
    
    def register_breaker(self, breaker: CircuitBreaker) -> None:
        """Register a circuit breaker."""
        self._breakers[breaker.name] = breaker
    
    def create_breaker(
        self, 
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        half_open_success_threshold: int = 2,
        timeout: float = 10.0,
        exclude_exceptions: List[type] = None,
        fallback: Optional[Callable] = None
    ) -> CircuitBreaker:
        """Create and register a new circuit breaker."""
        breaker = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
            half_open_success_threshold=half_open_success_threshold,
            timeout=timeout,
            exclude_exceptions=exclude_exceptions,
            fallback=fallback
        )
        self.register_breaker(breaker)
        return breaker
    
    def get_all_breakers(self) -> Dict[str, CircuitBreaker]:
        """Get all registered circuit breakers."""
        return self._breakers.copy()
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        return {name: breaker.get_stats() for name, breaker in self._breakers.items()}


# Singleton instance
circuit_breaker_registry = CircuitBreakerRegistry()


def with_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    timeout: float = 10.0,
    fallback: Optional[Callable] = None
):
    """
    Decorator for protecting a function with a circuit breaker.
    
    Args:
        name: Circuit breaker name
        failure_threshold: Failures before opening circuit
        recovery_timeout: Seconds before half-open state
        timeout: Operation timeout in seconds
        fallback: Optional fallback function
        
    Returns:
        Decorated function
    """
    def decorator(func):
        registry = CircuitBreakerRegistry()
        breaker = registry.get_breaker(name)
        
        if not breaker:
            breaker = registry.create_breaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                timeout=timeout,
                fallback=fallback
            )
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.execute(func, *args, **kwargs)
        
        return wrapper
    
    return decorator