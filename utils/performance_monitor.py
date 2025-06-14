"""
Performance monitoring module for Blaze Analyst.
Collects and reports metrics on various aspects of the system performance.
"""
import time
import logging
import asyncio
import functools
import os
import psutil
import platform
from typing import Dict, Any, List, Optional, Callable, Union, Set
from datetime import datetime
from enum import Enum
from collections import deque, defaultdict
import json
import statistics

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types of metrics that can be collected."""
    COUNTER = "counter"         # Increasing value (e.g., request count)
    GAUGE = "gauge"             # Current value (e.g., active connections)
    TIMER = "timer"             # Duration of events (e.g., request time)
    HISTOGRAM = "histogram"     # Distribution of values (e.g., response sizes)

class PerformanceMonitor:
    """
    Performance monitoring system.
    Collects metrics on various aspects of the system's performance.
    """
    
    def __init__(self):
        """Initialize the performance monitor."""
        # Metrics storage
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        
        # Timer metrics
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self.timer_count: Dict[str, int] = defaultdict(int)
        self.timer_sum: Dict[str, float] = defaultdict(float)
        self.timer_min: Dict[str, float] = {}
        self.timer_max: Dict[str, float] = {}
        
        # Histogram metrics
        self.histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Track metrics for snapshots
        self.all_metrics: Set[str] = set()
        self.metric_types: Dict[str, MetricType] = {}
        
        # Settings
        self.window_size = 100  # Number of values to keep for timers and histograms
        
        # Monitoring state
        self.started_at = time.time()
        self.last_snapshot_time = time.time()
        self.snapshot_interval = 60  # 1 minute
        self.snapshots: List[Dict[str, Any]] = []
        self.max_snapshots = 60  # Keep last 60 snapshots (1 hour at 1 minute interval)
        
        # System metrics
        self.collect_system_metrics = True
        
        # Background task
        self.snapshot_task = None
    
    async def start(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Start the performance monitor.
        
        Args:
            config: Configuration dictionary
        """
        if config:
            self.window_size = config.get("window_size", self.window_size)
            self.snapshot_interval = config.get("snapshot_interval", self.snapshot_interval)
            self.max_snapshots = config.get("max_snapshots", self.max_snapshots)
            self.collect_system_metrics = config.get("collect_system_metrics", self.collect_system_metrics)
        
        # Start snapshot task
        self.snapshot_task = asyncio.create_task(self._snapshot_loop())
        
        logger.info("Performance monitor started")
    
    async def stop(self) -> None:
        """Stop the performance monitor."""
        if self.snapshot_task:
            self.snapshot_task.cancel()
            try:
                await self.snapshot_task
            except asyncio.CancelledError:
                pass
            
            self.snapshot_task = None
        
        logger.info("Performance monitor stopped")
    
    def increment(self, name: str, value: int = 1) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            value: Value to increment by
        """
        self.counters[name] += value
        self.all_metrics.add(name)
        self.metric_types[name] = MetricType.COUNTER
    
    def set_gauge(self, name: str, value: float) -> None:
        """
        Set a gauge metric.
        
        Args:
            name: Metric name
            value: Gauge value
        """
        self.gauges[name] = value
        self.all_metrics.add(name)
        self.metric_types[name] = MetricType.GAUGE
    
    def record_timer(self, name: str, value: float) -> None:
        """
        Record a timer metric.
        
        Args:
            name: Metric name
            value: Timer value in seconds
        """
        self.all_metrics.add(name)
        self.metric_types[name] = MetricType.TIMER
        
        # Update timer stats
        self.timer_count[name] += 1
        self.timer_sum[name] += value
        
        # Update min/max
        if name not in self.timer_min or value < self.timer_min[name]:
            self.timer_min[name] = value
        
        if name not in self.timer_max or value > self.timer_max[name]:
            self.timer_max[name] = value
        
        # Add to rolling window
        self.timers[name].append(value)
        if len(self.timers[name]) > self.window_size:
            self.timers[name].pop(0)
    
    def record_histogram(self, name: str, value: float) -> None:
        """
        Record a histogram metric.
        
        Args:
            name: Metric name
            value: Value to record
        """
        self.histograms[name].append(value)
        self.all_metrics.add(name)
        self.metric_types[name] = MetricType.HISTOGRAM
    
    def time_function(self, name: str):
        """
        Decorator to time a function.
        
        Args:
            name: Timer name
            
        Returns:
            Callable: Decorated function
        """
        def decorator(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.time()
                try:
                    return await func(*args, **kwargs)
                finally:
                    duration = time.time() - start
                    self.record_timer(name, duration)
                    
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start = time.time()
                try:
                    return func(*args, **kwargs)
                finally:
                    duration = time.time() - start
                    self.record_timer(name, duration)
            
            # Choose the right wrapper based on the function type
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
            
        return decorator
    
    def get_timer_stats(self, name: str) -> Dict[str, float]:
        """
        Get statistics for a timer metric.
        
        Args:
            name: Timer name
            
        Returns:
            Dict: Timer statistics
        """
        if name not in self.timers or not self.timers[name]:
            return {
                "count": 0,
                "min": 0,
                "max": 0,
                "avg": 0,
                "sum": 0,
                "p50": 0,
                "p90": 0,
                "p95": 0,
                "p99": 0
            }
        
        values = sorted(self.timers[name])
        count = len(values)
        
        # Calculate percentiles
        p50_idx = int(count * 0.5)
        p90_idx = int(count * 0.9)
        p95_idx = int(count * 0.95)
        p99_idx = int(count * 0.99)
        
        return {
            "count": self.timer_count[name],
            "min": self.timer_min.get(name, 0),
            "max": self.timer_max.get(name, 0),
            "avg": self.timer_sum[name] / self.timer_count[name],
            "sum": self.timer_sum[name],
            "p50": values[p50_idx] if p50_idx < count else values[-1],
            "p90": values[p90_idx] if p90_idx < count else values[-1],
            "p95": values[p95_idx] if p95_idx < count else values[-1],
            "p99": values[p99_idx] if p99_idx < count else values[-1]
        }
    
    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """
        Get statistics for a histogram metric.
        
        Args:
            name: Histogram name
            
        Returns:
            Dict: Histogram statistics
        """
        if name not in self.histograms or not self.histograms[name]:
            return {
                "count": 0,
                "min": 0,
                "max": 0,
                "avg": 0,
                "median": 0,
                "stddev": 0
            }
        
        values = list(self.histograms[name])
        
        try:
            return {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": statistics.mean(values),
                "median": statistics.median(values),
                "stddev": statistics.stdev(values) if len(values) > 1 else 0
            }
        except Exception as e:
            logger.error(f"Error calculating histogram stats for {name}: {e}")
            return {
                "count": len(values),
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "avg": sum(values) / len(values) if values else 0,
                "median": 0,
                "stddev": 0
            }
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get all current metrics.
        
        Returns:
            Dict: All metrics
        """
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "uptime": time.time() - self.started_at,
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "timers": {name: self.get_timer_stats(name) for name in self.timers},
            "histograms": {name: self.get_histogram_stats(name) for name in self.histograms}
        }
        
        # Add system metrics if enabled
        if self.collect_system_metrics:
            metrics["system"] = self._collect_system_metrics()
        
        return metrics
    
    def get_snapshots(self) -> List[Dict[str, Any]]:
        """
        Get all metric snapshots.
        
        Returns:
            List[Dict]: List of metric snapshots
        """
        return self.snapshots
    
    def _collect_system_metrics(self) -> Dict[str, Any]:
        """
        Collect system-level metrics.
        
        Returns:
            Dict: System metrics
        """
        try:
            # Process metrics
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            cpu_percent = process.cpu_percent(interval=None)
            
            # System metrics
            sys_cpu = psutil.cpu_percent(interval=None)
            sys_mem = psutil.virtual_memory()
            sys_disk = psutil.disk_usage('/')
            
            return {
                "process": {
                    "memory_rss": mem_info.rss,
                    "memory_vms": mem_info.vms,
                    "cpu_percent": cpu_percent,
                    "threads": process.num_threads(),
                    "open_files": len(process.open_files()),
                    "connections": len(process.connections())
                },
                "system": {
                    "cpu_percent": sys_cpu,
                    "memory_percent": sys_mem.percent,
                    "memory_available": sys_mem.available,
                    "memory_total": sys_mem.total,
                    "disk_percent": sys_disk.percent,
                    "disk_free": sys_disk.free,
                    "disk_total": sys_disk.total
                },
                "platform": {
                    "system": platform.system(),
                    "release": platform.release(),
                    "python": platform.python_version()
                }
            }
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {}
    
    async def _snapshot_loop(self) -> None:
        """Periodically take snapshots of metrics."""
        while True:
            try:
                await asyncio.sleep(self.snapshot_interval)
                
                # Take snapshot
                metrics = self.get_current_metrics()
                self.snapshots.append(metrics)
                
                # Limit the number of snapshots
                while len(self.snapshots) > self.max_snapshots:
                    self.snapshots.pop(0)
                
                self.last_snapshot_time = time.time()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics snapshot loop: {e}")
                await asyncio.sleep(5)  # Shorter delay on error
    
    def export_metrics(self, format: str = "json") -> Union[str, Dict[str, Any]]:
        """
        Export current metrics in the specified format.
        
        Args:
            format: Export format ("json" or "dict")
            
        Returns:
            Union[str, Dict]: Metrics in the requested format
        """
        metrics = self.get_current_metrics()
        
        if format.lower() == "json":
            return json.dumps(metrics, indent=2)
        else:
            return metrics

# Create singleton instance
performance_monitor = PerformanceMonitor()

# Function decorators
def time_function(name: str):
    """
    Decorator to time a function.
    
    Args:
        name: Timer name
        
    Returns:
        Callable: Decorated function
    """
    return performance_monitor.time_function(name)

async def initialize_monitor(config: Optional[Dict[str, Any]] = None) -> None:
    """
    Initialize the performance monitor.
    
    Args:
        config: Configuration dictionary
    """
    await performance_monitor.start(config)

async def shutdown_monitor() -> None:
    """Shutdown the performance monitor."""
    await performance_monitor.stop() 