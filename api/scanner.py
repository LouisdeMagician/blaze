"""
Scanner API for Blaze Analyst.
Provides endpoints for scanning and analyzing contracts.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Dict, Any, Optional, List

from src.services.scanner import contract_scanner
from src.services.advanced_scanner import advanced_scanner
from src.models.scan_result import ScanStatus

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/scan/{address}")
async def scan_contract(
    address: str = Path(..., description="Contract address to scan"),
    user_id: Optional[str] = Query(None, description="User ID for attribution"),
    force_refresh: bool = Query(False, description="Force a fresh scan"),
) -> Dict[str, Any]:
    """
    Scan a contract address and return basic analysis.
    
    Args:
        address: Solana contract address
        user_id: Optional user ID for attribution
        force_refresh: Whether to bypass cache
        
    Returns:
        Dict with scan results
    """
    logger.info(f"Scanning contract {address} (user: {user_id}, force: {force_refresh})")
    
    # Call the scanner service
    scan_result = contract_scanner.scan_contract(address, user_id, force_refresh)
    
    if not scan_result:
        raise HTTPException(status_code=400, detail="Invalid contract address format")
    
    if scan_result.status == ScanStatus.FAILED:
        raise HTTPException(
            status_code=500, 
            detail=f"Scan failed: {scan_result.error_message or 'Unknown error'}"
        )
    
    # Return the scan result
    return scan_result.to_dict()


@router.get("/enhanced-scan/{address}")
async def enhanced_scan_contract(
    address: str = Path(..., description="Contract address to scan"),
    user_id: Optional[str] = Query(None, description="User ID for attribution"),
    force_refresh: bool = Query(False, description="Force a fresh scan"),
    scan_depth: str = Query("standard", description="Scan depth: standard, deep, or comprehensive")
) -> Dict[str, Any]:
    """
    Perform an enhanced scan of a contract with more in-depth analysis.
    
    Args:
        address: Solana contract address
        user_id: Optional user ID for attribution
        force_refresh: Whether to bypass cache
        scan_depth: Depth of analysis (standard, deep, comprehensive)
        
    Returns:
        Dict with enhanced scan results
    """
    logger.info(f"Enhanced scanning of {address} (user: {user_id}, depth: {scan_depth})")
    
    # Validate scan depth
    if scan_depth not in ["standard", "deep", "comprehensive"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid scan_depth. Must be one of: standard, deep, comprehensive"
        )
    
    # Call the advanced scanner service
    scan_result = advanced_scanner.enhanced_scan(address, user_id, force_refresh, scan_depth)
    
    if not scan_result:
        raise HTTPException(status_code=400, detail="Invalid contract address format")
    
    if scan_result.status == ScanStatus.FAILED:
        raise HTTPException(
            status_code=500, 
            detail=f"Scan failed: {scan_result.error_message or 'Unknown error'}"
        )
    
    # Return the scan result
    return scan_result.to_dict()


@router.get("/scan-status/{scan_id}")
async def get_scan_status(
    scan_id: str = Path(..., description="ID of a previous scan")
) -> Dict[str, Any]:
    """
    Get the status and result of a previous scan by ID.
    
    Args:
        scan_id: Scan ID from a previous scan
        
    Returns:
        Dict with scan status and result
    """
    # Get scan result from either scanner
    scan_result = contract_scanner.get_scan_result(scan_id)
    
    if not scan_result:
        raise HTTPException(status_code=404, detail=f"Scan with ID {scan_id} not found")
    
    return scan_result.to_dict()


@router.get("/scan-history/{address}")
async def get_scan_history(
    address: str = Path(..., description="Contract address"),
    limit: int = Query(10, description="Maximum number of results")
) -> List[Dict[str, Any]]:
    """
    Get scan history for a specific contract address.
    
    Args:
        address: Solana contract address
        limit: Maximum number of results to return
        
    Returns:
        List of scan results in chronological order
    """
    # Get scan history
    scan_history = contract_scanner.get_scan_history(address, limit)
    
    # Convert to dict
    return [scan.to_dict() for scan in scan_history] 