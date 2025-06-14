"""
Performance metrics dashboard for Blaze Analyst.
Provides visualization and reporting of system performance metrics.
"""
import logging
import time
import json
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import statistics

from src.utils.performance_monitor import PerformanceMonitor, performance_monitor
from src.services.cache_service import memory_cache

logger = logging.getLogger(__name__)

class PerformanceDashboard:
    """
    Dashboard for visualizing and reporting system performance metrics.
    Uses data from the PerformanceMonitor to generate reports and visualizations.
    """
    
    def __init__(self, monitor: Optional[PerformanceMonitor] = None):
        """
        Initialize the performance dashboard.
        
        Args:
            monitor: Performance monitor instance (uses global singleton if None)
        """
        self.monitor = monitor or performance_monitor
        
        # Dashboard configuration
        self.report_ttl = 300  # 5 minutes
        self.dashboard_data_ttl = 600  # 10 minutes
        self.metric_history_size = 60  # Keep 60 data points
        
        # Metric history
        self.metric_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # Background tasks
        self.collection_task = None
        self.dashboard_last_updated = 0
    
    async def start(self) -> None:
        """Start the dashboard data collection."""
        # Start collection task if not running
        if not self.collection_task:
            self.collection_task = asyncio.create_task(self._collection_loop())
            logger.info("Performance dashboard started")
    
    async def stop(self) -> None:
        """Stop the dashboard data collection."""
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
            
            self.collection_task = None
            logger.info("Performance dashboard stopped")
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get dashboard data with metrics and visualizations.
        
        Returns:
            Dict: Dashboard data
        """
        # Check cache first
        cache_key = "performance_dashboard_data"
        cached_data = await memory_cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # If no cached data or too old, generate new data
        current_time = time.time()
        if current_time - self.dashboard_last_updated > self.dashboard_data_ttl:
            await self._update_dashboard_data()
        
        # Get the latest metrics
        current_metrics = self.monitor.get_current_metrics()
        
        # Get stored historical data
        history = {}
        for metric_name, metric_data in self.metric_history.items():
            history[metric_name] = metric_data
        
        # Create dashboard data
        dashboard_data = {
            "current_metrics": current_metrics,
            "history": history,
            "system_info": self._get_system_info(),
            "timestamp": current_time,
            "uptime_seconds": current_time - self.monitor.started_at
        }
        
        # Cache the data
        await memory_cache.set(cache_key, dashboard_data, self.report_ttl)
        
        return dashboard_data
    
    async def get_performance_report(self) -> Dict[str, Any]:
        """
        Generate a performance report with key metrics and insights.
        
        Returns:
            Dict: Performance report
        """
        # Check cache first
        cache_key = "performance_report"
        cached_report = await memory_cache.get(cache_key)
        if cached_report:
            return cached_report
        
        # Get dashboard data
        dashboard_data = await self.get_dashboard_data()
        
        # Extract key metrics
        current_metrics = dashboard_data["current_metrics"]
        
        # Generate insights
        insights = []
        
        # API performance insights
        if "api_request_time" in self.monitor.timers:
            api_stats = self.monitor.get_timer_stats("api_request_time")
            
            if api_stats["p95"] > 1.0:  # More than 1 second for p95
                insights.append({
                    "type": "warning",
                    "message": f"API response times are high (p95: {api_stats['p95']:.2f}s)",
                    "metric": "api_request_time"
                })
            elif api_stats["p95"] < 0.1:  # Less than 100ms for p95
                insights.append({
                    "type": "positive",
                    "message": f"API response times are excellent (p95: {api_stats['p95'] * 1000:.0f}ms)",
                    "metric": "api_request_time"
                })
        
        # Cache performance insights
        if "cache_hit_rate" in current_metrics:
            hit_rate = current_metrics["cache_hit_rate"]
            if hit_rate < 50:
                insights.append({
                    "type": "warning",
                    "message": f"Cache hit rate is low ({hit_rate:.1f}%)",
                    "metric": "cache_hit_rate"
                })
            elif hit_rate > 85:
                insights.append({
                    "type": "positive",
                    "message": f"Cache hit rate is excellent ({hit_rate:.1f}%)",
                    "metric": "cache_hit_rate"
                })
        
        # Blockchain client insights
        if "blockchain_request_errors" in current_metrics and "blockchain_requests" in current_metrics:
            total_requests = current_metrics["blockchain_requests"]
            errors = current_metrics["blockchain_request_errors"]
            
            if total_requests > 0:
                error_rate = (errors / total_requests) * 100
                if error_rate > 5:
                    insights.append({
                        "type": "critical",
                        "message": f"High blockchain request error rate ({error_rate:.1f}%)",
                        "metric": "blockchain_request_errors"
                    })
        
        # Create the report
        report = {
            "timestamp": time.time(),
            "summary": self._generate_summary(current_metrics),
            "key_metrics": self._extract_key_metrics(current_metrics),
            "insights": insights,
            "recommendations": self._generate_recommendations(dashboard_data)
        }
        
        # Cache the report
        await memory_cache.set(cache_key, report, self.report_ttl)
        
        return report
    
    async def _update_dashboard_data(self) -> None:
        """Update the dashboard data with latest metrics."""
        # Update timestamp
        self.dashboard_last_updated = time.time()
        
        # Get snapshots from the monitor
        snapshots = self.monitor.get_snapshots()
        
        # Process snapshots into time series data
        for snapshot in snapshots:
            timestamp = snapshot.get("timestamp", 0)
            
            for metric_name, value in snapshot.get("metrics", {}).items():
                if metric_name not in self.metric_history:
                    self.metric_history[metric_name] = []
                
                # Add data point
                self.metric_history[metric_name].append({
                    "timestamp": timestamp,
                    "value": value
                })
                
                # Trim to maximum size
                if len(self.metric_history[metric_name]) > self.metric_history_size:
                    self.metric_history[metric_name] = self.metric_history[metric_name][-self.metric_history_size:]
    
    async def _collection_loop(self) -> None:
        """Background loop to periodically collect and update metrics."""
        try:
            while True:
                # Update dashboard data
                await self._update_dashboard_data()
                
                # Sleep for 1 minute
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            logger.info("Dashboard collection task cancelled")
        except Exception as e:
            logger.error(f"Error in dashboard collection loop: {e}", exc_info=True)
    
    def _extract_key_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract key metrics for the performance report.
        
        Args:
            metrics: Current metrics data
            
        Returns:
            Dict: Key metrics
        """
        key_metrics = {}
        
        # API metrics
        if "api_request_time" in self.monitor.timers:
            api_stats = self.monitor.get_timer_stats("api_request_time")
            key_metrics["api_p95_response_time"] = api_stats["p95"]
            key_metrics["api_requests_per_minute"] = metrics.get("api_requests", 0) / 60
        
        # Cache metrics
        if "cache_hit_rate" in metrics:
            key_metrics["cache_hit_rate"] = metrics["cache_hit_rate"]
        
        if "cache_size" in metrics:
            key_metrics["cache_size"] = metrics["cache_size"]
        
        # Blockchain metrics
        if "blockchain_request_time" in self.monitor.timers:
            blockchain_stats = self.monitor.get_timer_stats("blockchain_request_time")
            key_metrics["blockchain_avg_request_time"] = blockchain_stats["avg"]
        
        if "blockchain_requests" in metrics:
            key_metrics["blockchain_requests_per_minute"] = metrics.get("blockchain_requests", 0) / 60
        
        # System metrics
        if "cpu_usage" in metrics:
            key_metrics["cpu_usage"] = metrics["cpu_usage"]
        
        if "memory_usage" in metrics:
            key_metrics["memory_usage"] = metrics["memory_usage"]
        
        # Scanner metrics
        if "token_scan_time" in self.monitor.timers:
            scan_stats = self.monitor.get_timer_stats("token_scan_time")
            key_metrics["avg_scan_time"] = scan_stats["avg"]
            key_metrics["p95_scan_time"] = scan_stats["p95"]
        
        return key_metrics
    
    def _generate_summary(self, metrics: Dict[str, Any]) -> str:
        """
        Generate a summary of system performance.
        
        Args:
            metrics: Current metrics data
            
        Returns:
            str: Summary text
        """
        # Start with basic summary
        summary = "System is "
        
        # Check for critical metrics
        has_warnings = False
        
        # Check API response times
        if "api_request_time" in self.monitor.timers:
            api_stats = self.monitor.get_timer_stats("api_request_time")
            if api_stats["p95"] > 2.0:  # More than 2 seconds is critical
                summary += "experiencing performance issues. "
                has_warnings = True
            elif api_stats["p95"] > 1.0:  # More than 1 second is concerning
                summary += "performing slower than optimal. "
                has_warnings = True
        
        # Check blockchain error rate
        if "blockchain_request_errors" in metrics and "blockchain_requests" in metrics:
            total_requests = metrics["blockchain_requests"]
            errors = metrics["blockchain_request_errors"]
            
            if total_requests > 0:
                error_rate = (errors / total_requests) * 100
                if error_rate > 10:  # More than 10% errors is critical
                    summary += "experiencing high blockchain error rates. "
                    has_warnings = True
        
        # If no warnings, system is healthy
        if not has_warnings:
            summary += "operating normally. "
        
        # Add some details about request volume
        if "api_requests" in metrics:
            api_requests = metrics["api_requests"]
            summary += f"Processed {api_requests} API requests. "
        
        if "token_scans" in metrics:
            token_scans = metrics["token_scans"]
            summary += f"Completed {token_scans} token scans. "
        
        return summary.strip()
    
    def _generate_recommendations(self, dashboard_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate performance improvement recommendations.
        
        Args:
            dashboard_data: Dashboard data
            
        Returns:
            List[Dict]: List of recommendations
        """
        recommendations = []
        metrics = dashboard_data["current_metrics"]
        
        # Cache recommendations
        if "cache_hit_rate" in metrics:
            hit_rate = metrics["cache_hit_rate"]
            if hit_rate < 50:
                recommendations.append({
                    "priority": "medium",
                    "area": "caching",
                    "message": "Increase cache TTL to improve hit rate",
                    "metric": "cache_hit_rate"
                })
        
        # API performance recommendations
        if "api_request_time" in self.monitor.timers:
            api_stats = self.monitor.get_timer_stats("api_request_time")
            if api_stats["p95"] > 1.0:
                recommendations.append({
                    "priority": "high",
                    "area": "api",
                    "message": "Optimize API request handlers to improve response times",
                    "metric": "api_request_time"
                })
        
        # Blockchain client recommendations
        if "blockchain_request_errors" in metrics and metrics["blockchain_request_errors"] > 0:
            recommendations.append({
                "priority": "medium",
                "area": "blockchain",
                "message": "Add more fallback RPC providers to reduce error rates",
                "metric": "blockchain_request_errors"
            })
        
        # Memory usage recommendations
        if "memory_usage" in metrics and metrics["memory_usage"] > 85:
            recommendations.append({
                "priority": "high",
                "area": "system",
                "message": "Memory usage is high, consider optimizing memory-intensive operations",
                "metric": "memory_usage"
            })
        
        return recommendations
    
    def _get_system_info(self) -> Dict[str, Any]:
        """
        Get system information.
        
        Returns:
            Dict: System information
        """
        # This would typically include data about the environment
        # For now, we'll return a simple placeholder
        return {
            "start_time": datetime.fromtimestamp(self.monitor.started_at).isoformat(),
            "uptime_seconds": time.time() - self.monitor.started_at,
            "python_version": "3.9+",  # Would get actual version
            "environment": "development"  # Would get from config
        }

# Singleton instance
performance_dashboard = PerformanceDashboard()

# Initialization function
async def initialize_dashboard() -> None:
    """Initialize and start the performance dashboard."""
    await performance_dashboard.start()

# Shutdown function
async def shutdown_dashboard() -> None:
    """Stop the performance dashboard."""
    await performance_dashboard.stop() 