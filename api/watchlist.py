"""
Watchlist API for Blaze Analyst.
Provides endpoints for managing user watchlists.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from typing import Dict, Any, Optional, List

from src.services.watchlist_service import watchlist_service
from src.services.user_service import user_service
from src.services.contract_service import contract_service
from src.models.user import SubscriptionTier

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def get_watchlist(
    user_id: str = Query(..., description="User ID"),
    page: int = Query(1, description="Page number", gt=0),
    limit: int = Query(10, description="Items per page", gt=0, le=100),
    sort_by: Optional[str] = Query(None, description="Sort by field (name, symbol, risk_level, last_scan)"),
    sort_dir: Optional[str] = Query("asc", description="Sort direction (asc or desc)"),
    filter_risk: Optional[str] = Query(None, description="Filter by risk level (low, medium, high, critical)"),
) -> Dict[str, Any]:
    """
    Get a user's watchlist with pagination, sorting, and filtering.
    
    Args:
        user_id: User ID
        page: Page number, starting at 1
        limit: Number of items per page
        sort_by: Field to sort by
        sort_dir: Sort direction (asc or desc)
        filter_risk: Filter by risk level
        
    Returns:
        Dict with watchlist items, pagination info, and total count
    """
    logger.info(f"Getting watchlist for user {user_id} (page: {page}, limit: {limit})")
    
    # Verify user exists
    if not user_service.get_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get watchlist with pagination, sorting, and filtering
    result = watchlist_service.get_watchlist_paged(
        user_id=user_id,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
        filter_risk=filter_risk
    )
    
    return result


@router.post("/add")
async def add_to_watchlist(
    user_id: str = Query(..., description="User ID"),
    contract_address: str = Query(..., description="Contract address to add")
) -> Dict[str, Any]:
    """
    Add a contract to a user's watchlist.
    
    Args:
        user_id: User ID
        contract_address: Contract address to add
        
    Returns:
        Dict with success/error information
    """
    logger.info(f"Adding contract {contract_address} to watchlist for user {user_id}")
    
    # Add to watchlist
    result = watchlist_service.add_to_watchlist(user_id, contract_address)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/remove")
async def remove_from_watchlist(
    user_id: str = Query(..., description="User ID"),
    contract_address: str = Query(..., description="Contract address to remove")
) -> Dict[str, Any]:
    """
    Remove a contract from a user's watchlist.
    
    Args:
        user_id: User ID
        contract_address: Contract address to remove
        
    Returns:
        Dict with success/error information
    """
    logger.info(f"Removing contract {contract_address} from watchlist for user {user_id}")
    
    # Remove from watchlist
    result = watchlist_service.remove_from_watchlist(user_id, contract_address)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/clear")
async def clear_watchlist(
    user_id: str = Query(..., description="User ID")
) -> Dict[str, Any]:
    """
    Clear a user's entire watchlist.
    
    Args:
        user_id: User ID
        
    Returns:
        Dict with success/error information
    """
    logger.info(f"Clearing watchlist for user {user_id}")
    
    # Clear watchlist
    result = watchlist_service.clear_watchlist(user_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/limits")
async def get_watchlist_limits(
    user_id: str = Query(..., description="User ID")
) -> Dict[str, Any]:
    """
    Get watchlist limits for a user based on their subscription tier.
    
    Args:
        user_id: User ID
        
    Returns:
        Dict with watchlist limits information
    """
    logger.info(f"Getting watchlist limits for user {user_id}")
    
    # Get watchlist limits
    result = watchlist_service.get_watchlist_limits(user_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/scan")
async def scan_watchlist(
    user_id: str = Query(..., description="User ID"),
    force_refresh: bool = Query(False, description="Force a fresh scan")
) -> Dict[str, Any]:
    """
    Trigger scans for all contracts in a user's watchlist.
    
    Args:
        user_id: User ID
        force_refresh: Whether to bypass cache
        
    Returns:
        Dict with scan results
    """
    logger.info(f"Scanning watchlist for user {user_id}")
    
    # Scan watchlist
    result = watchlist_service.scan_watchlist(user_id, force_refresh)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/batch")
async def batch_watchlist_operation(
    user_id: str = Query(..., description="User ID"),
    operation: str = Query(..., description="Operation type (add, remove)"),
    addresses: List[str] = Body(..., description="List of contract addresses")
) -> Dict[str, Any]:
    """
    Perform batch operations on a watchlist.
    
    Args:
        user_id: User ID
        operation: Operation type (add, remove)
        addresses: List of contract addresses
        
    Returns:
        Dict with operation results
    """
    logger.info(f"Batch {operation} for user {user_id}, {len(addresses)} addresses")
    
    if operation not in ["add", "remove"]:
        raise HTTPException(status_code=400, detail="Invalid operation. Must be 'add' or 'remove'")
    
    # Perform batch operation
    result = watchlist_service.batch_operation(user_id, operation, addresses)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/history/{contract_address}")
async def get_scan_history(
    contract_address: str = Path(..., description="Contract address"),
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(5, description="Maximum number of results", gt=0, le=20)
) -> Dict[str, Any]:
    """
    Get scan history for a specific contract in the watchlist.
    
    Args:
        contract_address: Contract address
        user_id: User ID
        limit: Maximum number of results
        
    Returns:
        Dict with scan history
    """
    logger.info(f"Getting scan history for {contract_address} (user: {user_id})")
    
    # Check if contract is in user's watchlist
    user = user_service.get_user(user_id)
    if not user or not user.watchlist or contract_address not in user.watchlist:
        raise HTTPException(status_code=404, detail="Contract not found in watchlist")
    
    # Get scan history
    history = watchlist_service.get_scan_history(contract_address, limit)
    
    return {
        "success": True,
        "contract_address": contract_address,
        "history": history
    }


@router.get("/stats")
async def get_watchlist_stats(
    user_id: str = Query(..., description="User ID")
) -> Dict[str, Any]:
    """
    Get statistics about a user's watchlist.
    
    Args:
        user_id: User ID
        
    Returns:
        Dict with watchlist statistics
    """
    logger.info(f"Getting watchlist stats for user {user_id}")
    
    # Get watchlist stats
    result = watchlist_service.get_watchlist_stats(user_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result 