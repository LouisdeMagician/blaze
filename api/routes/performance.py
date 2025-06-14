"""
API routes for performance monitoring and system metrics.
Provides endpoints to check system performance and optimization status.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List

from src.utils.performance_monitor import performance_monitor
from src.utils.connection_pool import connection_pools
from src.utils.circuit_breaker import get_all_stats as get_all_circuit_breaker_stats
from src.utils.db_optimizer import db_optimizer
from src.api.auth import verify_admin_access

router = APIRouter(
    prefix="/performance",
    tags=["Performance"],
    dependencies=[Depends(verify_admin_access)]  # Only admins can access these endpoints
)

@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """
    Get current performance metrics.
    
    Returns:
        Dict: Current performance metrics
    """
    return performance_monitor.get_current_metrics()

@router.get("/snapshots")
async def get_snapshots() -> List[Dict[str, Any]]:
    """
    Get historical performance metric snapshots.
    
    Returns:
        List[Dict]: List of performance metric snapshots
    """
    return performance_monitor.get_snapshots()

@router.get("/connection-pools")
async def get_connection_pools() -> Dict[str, Any]:
    """
    Get connection pool statistics.
    
    Returns:
        Dict: Connection pool statistics
    """
    return {
        name: pool.get_stats() 
        for name, pool in connection_pools.items()
    }

@router.get("/circuit-breakers")
async def get_circuit_breakers() -> Dict[str, Any]:
    """
    Get circuit breaker statistics.
    
    Returns:
        Dict: Circuit breaker statistics
    """
    return get_all_circuit_breaker_stats()

@router.get("/db/stats")
async def get_db_stats() -> Dict[str, Any]:
    """
    Get database statistics.
    
    Returns:
        Dict: Database statistics
    """
    collection_stats = await db_optimizer.get_collection_stats()
    query_stats = db_optimizer.get_query_stats()
    index_info = await db_optimizer.get_index_info()
    
    return {
        "collections": collection_stats,
        "query_stats": query_stats,
        "indexes": index_info
    }

@router.get("/db/recommendations")
async def get_db_recommendations() -> List[Dict[str, Any]]:
    """
    Get database optimization recommendations.
    
    Returns:
        List[Dict]: Database optimization recommendations
    """
    return db_optimizer.get_optimization_recommendations()

@router.post("/db/optimize/{collection}")
async def optimize_collection(collection: str, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Optimize a specific database collection.
    
    Args:
        collection: Collection name
        background_tasks: Background tasks
        
    Returns:
        Dict: Optimization result
    """
    # Start optimization in a background task for long-running operations
    background_tasks.add_task(db_optimizer.optimize_collection, collection)
    
    return {
        "status": "Optimization started in background",
        "collection": collection
    } 