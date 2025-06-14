"""
Health check API for Blaze Analyst.
Provides endpoint for checking system health.
"""
import logging
from fastapi import APIRouter, Depends
from typing import Dict, Any

# Comment out database import
# from src.services.database import db_service
from src.blockchain.solana_client import solana_client
from src.blockchain.helius_client import helius_client

router = APIRouter()
logger = logging.getLogger(__name__)


class HealthCheck:
    """Service for health checking."""
    
    @staticmethod
    async def check_database() -> Dict[str, Any]:
        """Check database connectivity."""
        return {
            "status": "warning",
            "message": "Database module disabled",
            "details": {
                "count": 0
            }
        }
    
    @staticmethod
    async def check_blockchain() -> Dict[str, Any]:
        """Check blockchain connection."""
        try:
            # Simple request to check blockchain connectivity
            result = solana_client.get_health()
            return {
                "status": "ok" if result == "ok" else "warning",
                "message": "Blockchain connection successful",
                "details": {
                    "primary_rpc": result
                }
            }
        except Exception as e:
            logger.error(f"Blockchain health check failed: {e}")
            return {
                "status": "error",
                "message": f"Blockchain connection failed: {str(e)}",
                "details": None
            }
    
    @staticmethod
    async def check_helius() -> Dict[str, Any]:
        """Check Helius API connectivity."""
        try:
            # Simple request to check Helius connectivity
            helius_available = helius_client.check_health()
            return {
                "status": "ok" if helius_available else "warning",
                "message": "Helius API connection successful" if helius_available else "Helius API not available",
                "details": {
                    "available": helius_available
                }
            }
        except Exception as e:
            logger.error(f"Helius health check failed: {e}")
            return {
                "status": "error",
                "message": f"Helius API connection failed: {str(e)}",
                "details": None
            }
    
    @classmethod
    async def check_all(cls) -> Dict[str, Any]:
        """Check all system components."""
        db_health = await cls.check_database()
        blockchain_health = await cls.check_blockchain()
        helius_health = await cls.check_helius()
        
        # Determine overall status (ok, warning, error)
        statuses = [
            db_health["status"],
            blockchain_health["status"],
            helius_health["status"]
        ]
        
        if "error" in statuses:
            overall_status = "error"
        elif "warning" in statuses:
            overall_status = "warning"
        else:
            overall_status = "ok"
        
        return {
            "status": overall_status,
            "components": {
                "database": db_health,
                "blockchain": blockchain_health,
                "helius": helius_health
            },
            "version": "1.0.0"
        }


health_check = HealthCheck()


@router.get("/health")
async def health() -> Dict[str, Any]:
    """
    Health check endpoint.
    Returns status of various system components.
    """
    return await health_check.check_all()


@router.get("/health/db")
async def database_health() -> Dict[str, Any]:
    """
    Database health check endpoint.
    Returns status of database connection.
    """
    return await health_check.check_database()


@router.get("/health/blockchain")
async def blockchain_health() -> Dict[str, Any]:
    """
    Blockchain health check endpoint.
    Returns status of blockchain connection.
    """
    return await health_check.check_blockchain()


@router.get("/health/helius")
async def helius_health() -> Dict[str, Any]:
    """
    Helius API health check endpoint.
    Returns status of Helius API connection.
    """
    return await health_check.check_helius()
