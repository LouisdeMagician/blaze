"""
API router for Blaze Analyst.
Registers all API routes.
"""
from fastapi import APIRouter

from src.api.routes import (
    health,
    token_analysis,
    contract_scanner,
    liquidity_analysis,
    ownership_analysis,
    trading_analysis,  # Import the new trading analysis routes
    anomaly_routes,    # Import the anomaly detection routes
    risk_routes,        # Import the risk classification routes
    smart_money_routes,  # Import the new smart money routes
    predictive_routes  # Import the new predictive routes
)

router = APIRouter()

# Register all routes
router.include_router(health.router)
router.include_router(token_analysis.router)
router.include_router(contract_scanner.router)
router.include_router(liquidity_analysis.router)
router.include_router(ownership_analysis.router)
router.include_router(trading_analysis.router)  # Add the trading analysis routes
router.include_router(anomaly_routes.router)    # Add the anomaly detection routes
router.include_router(risk_routes.router)       # Add the risk classification routes
router.include_router(smart_money_routes.router)  # Add the smart money routes
router.include_router(predictive_routes.router)  # Add the predictive routes 