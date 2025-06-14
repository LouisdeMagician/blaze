"""
Connection pool for external API requests.
Implements connection pooling, request queuing, and monitoring.
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Awaitable, Tuple
from datetime import datetime
from enum import Enum
import aiohttp
from dataclasses import dataclass, field
from asyncio import Queue, Lock

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    """Connection states."""
    IDLE = "idle"
    BUSY = "busy"
    CLOSED = "closed"
    UNHEALTHY = "unhealthy"

@dataclass
class Connection:
    """Connection class for tracking state and health."""
    id: str
    session: aiohttp.ClientSession
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    state: ConnectionState = ConnectionState.IDLE
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_request_time: float = 0
    
    def get_avg_response_time(self) -> float:
        """Get average response time."""
        if self.total_requests == 0:
            return 0
        return self.total_request_time / self.total_requests
    
    def get_error_rate(self) -> float:
        """Get error rate."""
        if self.total_requests == 0:
            return 0
        return self.failed_requests / self.total_requests

@dataclass
class Request:
    """Request class for queuing."""
    id: str
    method: str
    url: str
    callback: Callable[[Optional[Dict], Optional[Exception]], Awaitable[None]]
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    timestamp: float = field(default_factory=time.time)
    timeout: Optional[float] = None

class ConnectionPool:
    """Connection pool for external API requests."""
    
    def __init__(self, name: str, base_url: str = None):
        """
        Initialize the connection pool.
        
        Args:
            name: Pool name
            base_url: Base URL for API requests
        """
        self.name = name
        self.base_url = base_url
        
        # Pool settings
        self.min_connections = 2
        self.max_connections = 10
        self.max_requests_per_connection = 1000
        self.connection_timeout = 30  # seconds
        self.connection_ttl = 3600  # 1 hour
        self.queue_timeout = 30  # seconds
        self.health_check_interval = 300  # 5 minutes
        
        # Connection pool
        self.connections: Dict[str, Connection] = {}
        self.available_connections: List[str] = []
        self.connection_lock = Lock()
        
        # Request queue
        self.request_queue = Queue()
        self.request_waiting_count = 0
        
        # Metrics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_queued_requests = 0
        self.total_queue_time = 0
        self.total_request_time = 0
        self.created_at = time.time()
        
        # Background tasks
        self.queue_processor_task = None
        self.health_check_task = None
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the connection pool with configuration.
        
        Args:
            config: Configuration dictionary
        """
        # Configure pool
        if config:
            self.min_connections = config.get("min_connections", self.min_connections)
            self.max_connections = config.get("max_connections", self.max_connections)
            self.max_requests_per_connection = config.get("max_requests_per_connection", self.max_requests_per_connection)
            self.connection_timeout = config.get("connection_timeout", self.connection_timeout)
            self.connection_ttl = config.get("connection_ttl", self.connection_ttl)
            self.queue_timeout = config.get("queue_timeout", self.queue_timeout)
            self.health_check_interval = config.get("health_check_interval", self.health_check_interval)
        
        # Initialize connections
        for i in range(self.min_connections):
            await self._create_connection()
        
        # Start background tasks
        self.queue_processor_task = asyncio.create_task(self._process_queue())
        self.health_check_task = asyncio.create_task(self._periodic_health_check())
        
        logger.info(f"Initialized connection pool '{self.name}' with {self.min_connections} connections")
    
    async def shutdown(self) -> None:
        """Shutdown the connection pool."""
        # Cancel background tasks
        if self.queue_processor_task:
            self.queue_processor_task.cancel()
        
        if self.health_check_task:
            self.health_check_task.cancel()
        
        # Close all connections
        for conn_id, conn in self.connections.items():
            await self._close_connection(conn_id)
        
        logger.info(f"Shutdown connection pool '{self.name}'")
    
    async def request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """
        Make an HTTP request through the connection pool.
        
        Args:
            method: HTTP method
            url: URL path (will be combined with base_url if not absolute)
            **kwargs: Additional arguments for the request
            
        Returns:
            Dict: Response data
        """
        self.total_requests += 1
        request_id = f"req_{self.total_requests}"
        
        # Prepare URL
        if self.base_url and not url.startswith(("http://", "https://")):
            full_url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
        else:
            full_url = url
        
        # Create future for the response
        future = asyncio.Future()
        
        # Create request
        request = Request(
            id=request_id,
            method=method,
            url=full_url,
            callback=lambda result, error: self._handle_response(future, result, error),
            kwargs=kwargs,
            priority=kwargs.pop("priority", 0) if kwargs else 0,
            timeout=kwargs.pop("timeout", self.connection_timeout) if kwargs else self.connection_timeout
        )
        
        # Queue the request
        queue_start = time.time()
        self.total_queued_requests += 1
        self.request_waiting_count += 1
        await self.request_queue.put(request)
        
        try:
            # Wait for response
            result = await asyncio.wait_for(future, request.timeout)
            self.successful_requests += 1
            return result
        except asyncio.TimeoutError:
            self.failed_requests += 1
            logger.warning(f"Request {request_id} timed out after {request.timeout}s")
            raise TimeoutError(f"Request timed out after {request.timeout}s")
        except Exception as e:
            self.failed_requests += 1
            logger.error(f"Request {request_id} failed: {e}")
            raise
        finally:
            self.request_waiting_count -= 1
            queue_time = time.time() - queue_start
            self.total_queue_time += queue_time
    
    async def _handle_response(self, future: asyncio.Future, result: Optional[Dict], error: Optional[Exception]) -> None:
        """Handle the response from a request."""
        if future.done():
            return
        
        if error:
            future.set_exception(error)
        else:
            future.set_result(result)
    
    async def _process_queue(self) -> None:
        """Process the request queue."""
        while True:
            try:
                # Get request from queue
                request = await self.request_queue.get()
                
                # Try to get an available connection
                conn_id = await self._get_available_connection()
                
                if conn_id:
                    # Execute request
                    asyncio.create_task(self._execute_request(conn_id, request))
                else:
                    # No connection available, requeue the request
                    await self.request_queue.put(request)
                    await asyncio.sleep(0.1)  # Small delay to prevent high CPU usage
                
                self.request_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing request queue: {e}", exc_info=True)
                await asyncio.sleep(1)  # Delay to prevent high CPU usage on errors
    
    async def _execute_request(self, conn_id: str, request: Request) -> None:
        """
        Execute a request using a connection.
        
        Args:
            conn_id: Connection ID
            request: Request to execute
        """
        conn = self.connections[conn_id]
        conn.state = ConnectionState.BUSY
        conn.last_used_at = time.time()
        conn.total_requests += 1
        
        start_time = time.time()
        
        try:
            # Execute request
            async with getattr(conn.session, request.method.lower())(
                request.url, **request.kwargs
            ) as response:
                # Read response
                response_data = await response.json()
                
                # Update connection
                conn.successful_requests += 1
                
                # Call callback
                await request.callback(response_data, None)
        except Exception as e:
            # Update connection
            conn.failed_requests += 1
            
            # Call callback with error
            await request.callback(None, e)
            
            logger.error(f"Request {request.id} failed: {e}")
        finally:
            # Update metrics
            request_time = time.time() - start_time
            conn.total_request_time += request_time
            self.total_request_time += request_time
            
            # Make connection available again
            if conn.total_requests >= self.max_requests_per_connection:
                # Connection reached max requests, close it
                await self._close_connection(conn_id)
                await self._create_connection()
            else:
                # Make connection available again
                conn.state = ConnectionState.IDLE
                async with self.connection_lock:
                    self.available_connections.append(conn_id)
    
    async def _get_available_connection(self) -> Optional[str]:
        """
        Get an available connection.
        
        Returns:
            Optional[str]: Connection ID or None if no connection available
        """
        async with self.connection_lock:
            if self.available_connections:
                # Get first available connection
                conn_id = self.available_connections.pop(0)
                return conn_id
            elif len(self.connections) < self.max_connections:
                # Create new connection
                new_conn_id = await self._create_connection()
                if new_conn_id and new_conn_id in self.available_connections:
                    self.available_connections.remove(new_conn_id)
                return new_conn_id
            
            return None
    
    async def _create_connection(self) -> Optional[str]:
        """
        Create a new connection.
        
        Returns:
            Optional[str]: Connection ID or None if creation failed
        """
        try:
            conn_id = f"conn_{self.name}_{len(self.connections) + 1}"
            
            # Create session
            timeout = aiohttp.ClientTimeout(total=self.connection_timeout)
            session = aiohttp.ClientSession(timeout=timeout)
            
            # Create connection
            conn = Connection(
                id=conn_id,
                session=session
            )
            
            # Add to pool
            self.connections[conn_id] = conn
            
            async with self.connection_lock:
                self.available_connections.append(conn_id)
            
            logger.debug(f"Created new connection {conn_id}")
            return conn_id
        except Exception as e:
            logger.error(f"Failed to create connection: {e}", exc_info=True)
            return None
    
    async def _close_connection(self, conn_id: str) -> None:
        """
        Close a connection.
        
        Args:
            conn_id: Connection ID
        """
        if conn_id in self.connections:
            conn = self.connections[conn_id]
            
            try:
                # Close session
                await conn.session.close()
                
                # Update state
                conn.state = ConnectionState.CLOSED
                
                # Remove from available connections
                async with self.connection_lock:
                    if conn_id in self.available_connections:
                        self.available_connections.remove(conn_id)
                
                # Remove from pool
                del self.connections[conn_id]
                
                logger.debug(f"Closed connection {conn_id}")
            except Exception as e:
                logger.error(f"Error closing connection {conn_id}: {e}", exc_info=True)
    
    async def _check_connection_health(self, conn_id: str) -> bool:
        """
        Check if a connection is healthy.
        
        Args:
            conn_id: Connection ID
            
        Returns:
            bool: True if healthy, False otherwise
        """
        if conn_id not in self.connections:
            return False
        
        conn = self.connections[conn_id]
        
        # Check if connection is too old
        if time.time() - conn.created_at > self.connection_ttl:
            logger.debug(f"Connection {conn_id} is too old, marking as unhealthy")
            conn.state = ConnectionState.UNHEALTHY
            return False
        
        # Check error rate
        error_rate = conn.get_error_rate()
        if error_rate > 0.3 and conn.total_requests > 10:  # 30% error rate after 10 requests
            logger.warning(f"Connection {conn_id} has high error rate ({error_rate:.2%}), marking as unhealthy")
            conn.state = ConnectionState.UNHEALTHY
            return False
        
        return True
    
    async def _periodic_health_check(self) -> None:
        """Periodically check the health of connections."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                unhealthy_connections = []
                
                # Check all connections
                for conn_id in list(self.connections.keys()):
                    if not await self._check_connection_health(conn_id):
                        unhealthy_connections.append(conn_id)
                
                # Close unhealthy connections
                for conn_id in unhealthy_connections:
                    await self._close_connection(conn_id)
                
                # Create new connections if needed
                while len(self.connections) < self.min_connections:
                    await self._create_connection()
                
                logger.debug(f"Health check completed. Connections: {len(self.connections)}, " +
                           f"Available: {len(self.available_connections)}, " +
                           f"Unhealthy: {len(unhealthy_connections)}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check: {e}", exc_info=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics.
        
        Returns:
            Dict: Connection pool stats
        """
        now = time.time()
        uptime = now - self.created_at
        
        # Calculate metrics
        avg_queue_time = self.total_queue_time / self.total_queued_requests if self.total_queued_requests > 0 else 0
        avg_request_time = self.total_request_time / self.total_requests if self.total_requests > 0 else 0
        success_rate = self.successful_requests / self.total_requests if self.total_requests > 0 else 0
        
        return {
            "name": self.name,
            "uptime": uptime,
            "connections": {
                "total": len(self.connections),
                "available": len(self.available_connections),
                "min": self.min_connections,
                "max": self.max_connections
            },
            "requests": {
                "total": self.total_requests,
                "successful": self.successful_requests,
                "failed": self.failed_requests,
                "success_rate": success_rate
            },
            "queue": {
                "current_size": self.request_queue.qsize(),
                "waiting": self.request_waiting_count,
                "total_queued": self.total_queued_requests
            },
            "timing": {
                "avg_queue_time": avg_queue_time,
                "avg_request_time": avg_request_time,
                "total_queue_time": self.total_queue_time,
                "total_request_time": self.total_request_time
            },
            "connections_detail": [
                {
                    "id": conn.id,
                    "state": conn.state.value,
                    "age": now - conn.created_at,
                    "last_used": now - conn.last_used_at if conn.last_used_at else None,
                    "requests": conn.total_requests,
                    "success_rate": conn.successful_requests / conn.total_requests if conn.total_requests > 0 else 0,
                    "avg_response_time": conn.get_avg_response_time()
                }
                for conn in list(self.connections.values())[:10]  # Show at most 10 connections
            ]
        }

# Create a registry for connection pools
connection_pools: Dict[str, ConnectionPool] = {}

def get_connection_pool(name: str, base_url: str = None) -> ConnectionPool:
    """
    Get or create a connection pool.
    
    Args:
        name: Pool name
        base_url: Base URL for API requests
        
    Returns:
        ConnectionPool: Connection pool
    """
    if name not in connection_pools:
        connection_pools[name] = ConnectionPool(name, base_url)
    
    return connection_pools[name]

async def initialize_pools(config: Dict[str, Any]) -> None:
    """
    Initialize all connection pools.
    
    Args:
        config: Configuration dictionary with pools configuration
    """
    if not config:
        return
    
    pools_config = config.get("pools", {})
    for pool_name, pool_config in pools_config.items():
        base_url = pool_config.get("base_url")
        pool = get_connection_pool(pool_name, base_url)
        await pool.initialize(pool_config)
    
    logger.info(f"Initialized {len(pools_config)} connection pools")

async def shutdown_pools() -> None:
    """Shutdown all connection pools."""
    for pool in connection_pools.values():
        await pool.shutdown()
    
    logger.info(f"Shutdown {len(connection_pools)} connection pools") 