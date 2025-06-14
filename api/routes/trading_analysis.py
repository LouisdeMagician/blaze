"""
Trading pattern analysis API routes for Blaze Analyst.
Provides endpoints for accessing trading pattern analysis results.
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Path, Body, Depends, Header

from src.analysis.trading.pattern_analyzer import trading_pattern_analyzer
from src.analysis.trading.transaction_monitor import transaction_monitor
from src.analysis.trading.wash_trading_detector import wash_trading_detector
from src.analysis.trading.pump_dump_detector import pump_dump_detector
from src.analysis.trading.market_manipulation_detector import market_manipulation_detector
from src.analysis.trading.volume_analyzer import volume_analyzer
from src.api.models.trading_analysis import (
    TradingAnalysisRequest,
    TradingAnalysisResponse,
    TradePatternAnalysisResult,
    WashTradingAnalysisResult,
    PumpDumpAnalysisResult,
    MarketManipulationAnalysisResult,
    VolumeAnalysisResult,
    AnalysisStatusResponse,
    WebhookRegistrationRequest
)
from src.api.dependencies import rate_limiter, api_key_auth
from src.services.webhook_service import webhook_service
from src.services.analysis_queue import analysis_queue

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/trading",
    tags=["Trading Analysis"],
    dependencies=[Depends(api_key_auth)]
)

# In-memory store for analysis status
# In a production environment, this would be replaced with a database
analysis_status = {}


@router.post("/analyze", response_model=AnalysisStatusResponse)
async def analyze_token_trading(
    request: TradingAnalysisRequest,
    background_tasks: BackgroundTasks,
    x_callback_url: Optional[str] = Header(None),
    _: Any = Depends(rate_limiter)
):
    """
    Start a trading pattern analysis for a token.
    
    Analyzes trading patterns, wash trading, pump and dump, market manipulation, and volume.
    Analysis runs in the background and results can be retrieved using the returned analysis_id.
    
    If x-callback-url header is provided, results will be sent to that URL when analysis completes.
    """
    token_address = request.token_address
    if not token_address:
        raise HTTPException(status_code=400, detail="Token address is required")
    
    # Generate a unique analysis ID
    analysis_id = f"trading_{token_address}_{int(datetime.utcnow().timestamp())}"
    
    # Set initial status
    analysis_status[analysis_id] = {
        "status": "queued",
        "token_address": token_address,
        "requested_at": datetime.utcnow(),
        "components": {
            "transaction_tracking": "pending",
            "pattern_analysis": "pending",
            "wash_trading": "pending",
            "pump_dump": "pending",
            "market_manipulation": "pending",
            "volume_analysis": "pending"
        },
        "results": {},
        "error": None
    }
    
    # Add to analysis queue and run in background
    await analysis_queue.add_task(
        task_id=analysis_id,
        task_func=_run_trading_analysis,
        token_address=token_address,
        analysis_id=analysis_id,
        force_refresh=request.force_refresh,
        callback_url=x_callback_url
    )
    
    return AnalysisStatusResponse(
        analysis_id=analysis_id,
        status="queued",
        token_address=token_address,
        message="Trading pattern analysis has been queued",
        estimated_time_seconds=60
    )


@router.get("/status/{analysis_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    analysis_id: str = Path(..., description="Analysis ID returned from the analyze endpoint"),
    _: Any = Depends(rate_limiter)
):
    """Get the status of a trading pattern analysis."""
    if analysis_id not in analysis_status:
        raise HTTPException(status_code=404, detail="Analysis ID not found")
    
    status_data = analysis_status[analysis_id]
    
    return AnalysisStatusResponse(
        analysis_id=analysis_id,
        status=status_data["status"],
        token_address=status_data["token_address"],
        message=f"Analysis is {status_data['status']}",
        error=status_data.get("error"),
        components_status=status_data["components"],
        completed_at=status_data.get("completed_at"),
        estimated_time_seconds=_estimate_remaining_time(status_data)
    )


@router.get("/results/{analysis_id}", response_model=TradingAnalysisResponse)
async def get_analysis_results(
    analysis_id: str = Path(..., description="Analysis ID returned from the analyze endpoint"),
    _: Any = Depends(rate_limiter)
):
    """Get the results of a completed trading pattern analysis."""
    if analysis_id not in analysis_status:
        raise HTTPException(status_code=404, detail="Analysis ID not found")
    
    status_data = analysis_status[analysis_id]
    
    if status_data["status"] != "completed":
        if status_data["status"] == "failed":
            error_msg = status_data.get("error", "Unknown error")
            raise HTTPException(status_code=500, detail=f"Analysis failed: {error_msg}")
        else:
            raise HTTPException(status_code=202, detail="Analysis is still in progress")
    
    return TradingAnalysisResponse(
        token_address=status_data["token_address"],
        timestamp=status_data.get("completed_at", datetime.utcnow()),
        pattern_analysis=status_data["results"].get("pattern_analysis"),
        wash_trading=status_data["results"].get("wash_trading"),
        pump_dump=status_data["results"].get("pump_dump"),
        market_manipulation=status_data["results"].get("market_manipulation"),
        volume_analysis=status_data["results"].get("volume_analysis")
    )


@router.post("/webhook/register")
async def register_webhook(
    request: WebhookRegistrationRequest,
    _: Any = Depends(rate_limiter)
):
    """Register a webhook for receiving trading analysis notifications."""
    try:
        webhook_id = await webhook_service.register_webhook(
            url=request.callback_url,
            event_types=request.event_types,
            metadata={
                "token_addresses": request.token_addresses,
                "description": request.description
            }
        )
        
        return {
            "webhook_id": webhook_id,
            "status": "registered",
            "message": "Webhook successfully registered"
        }
    except Exception as e:
        logger.error(f"Error registering webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to register webhook: {str(e)}")


@router.delete("/webhook/{webhook_id}")
async def unregister_webhook(
    webhook_id: str = Path(..., description="Webhook ID to unregister"),
    _: Any = Depends(rate_limiter)
):
    """Unregister a webhook."""
    try:
        success = await webhook_service.unregister_webhook(webhook_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Webhook ID not found")
        
        return {
            "webhook_id": webhook_id,
            "status": "unregistered",
            "message": "Webhook successfully unregistered"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unregistering webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to unregister webhook: {str(e)}")


# Direct analysis endpoints for individual components

@router.get("/pattern/{token_address}", response_model=TradePatternAnalysisResult)
async def analyze_trading_pattern(
    token_address: str = Path(..., description="Token mint address"),
    force_refresh: bool = Query(False, description="Force refresh of analysis"),
    _: Any = Depends(rate_limiter)
):
    """
    Analyze trading patterns for a token.
    
    Provides a comprehensive analysis of trading patterns including suspicious activity detection.
    """
    try:
        result = trading_pattern_analyzer.analyze_token_trading(token_address, force_refresh)
        return TradePatternAnalysisResult(**result)
    except Exception as e:
        logger.error(f"Error analyzing trading pattern for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/wash-trading/{token_address}", response_model=WashTradingAnalysisResult)
async def analyze_wash_trading(
    token_address: str = Path(..., description="Token mint address"),
    force_refresh: bool = Query(False, description="Force refresh of analysis"),
    _: Any = Depends(rate_limiter)
):
    """
    Analyze wash trading for a token.
    
    Detects wash trading patterns including circular trades and artificial volume.
    """
    try:
        result = wash_trading_detector.detect_wash_trading(token_address, force_refresh)
        return WashTradingAnalysisResult(**result)
    except Exception as e:
        logger.error(f"Error analyzing wash trading for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/pump-dump/{token_address}", response_model=PumpDumpAnalysisResult)
async def analyze_pump_dump(
    token_address: str = Path(..., description="Token mint address"),
    force_refresh: bool = Query(False, description="Force refresh of analysis"),
    _: Any = Depends(rate_limiter)
):
    """
    Analyze pump and dump patterns for a token.
    
    Detects price and volume patterns indicative of pump and dump schemes.
    """
    try:
        result = pump_dump_detector.detect_pump_dump(token_address, force_refresh)
        return PumpDumpAnalysisResult(**result)
    except Exception as e:
        logger.error(f"Error analyzing pump and dump for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/market-manipulation/{token_address}", response_model=MarketManipulationAnalysisResult)
async def analyze_market_manipulation(
    token_address: str = Path(..., description="Token mint address"),
    force_refresh: bool = Query(False, description="Force refresh of analysis"),
    _: Any = Depends(rate_limiter)
):
    """
    Analyze market manipulation for a token.
    
    Detects manipulation patterns like spoofing, layering, and momentum ignition.
    """
    try:
        result = market_manipulation_detector.detect_market_manipulation(token_address, force_refresh)
        return MarketManipulationAnalysisResult(**result)
    except Exception as e:
        logger.error(f"Error analyzing market manipulation for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/volume/{token_address}", response_model=VolumeAnalysisResult)
async def analyze_volume(
    token_address: str = Path(..., description="Token mint address"),
    force_refresh: bool = Query(False, description="Force refresh of analysis"),
    _: Any = Depends(rate_limiter)
):
    """
    Analyze trading volume for a token.
    
    Analyzes volume trends, anomalies, and buy/sell pressure.
    """
    try:
        result = volume_analyzer.analyze_volume(token_address, force_refresh)
        return VolumeAnalysisResult(**result)
    except Exception as e:
        logger.error(f"Error analyzing volume for {token_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# Helper functions

async def _run_trading_analysis(token_address: str, analysis_id: str, force_refresh: bool = False, callback_url: Optional[str] = None):
    """
    Run a complete trading pattern analysis for a token.
    
    Args:
        token_address: Token mint address
        analysis_id: Analysis ID for tracking
        force_refresh: Whether to force a refresh of all analyses
        callback_url: Optional URL to call with results when complete
    """
    try:
        # Update status to in-progress
        analysis_status[analysis_id]["status"] = "in_progress"
        
        # Step 1: Track transactions
        analysis_status[analysis_id]["components"]["transaction_tracking"] = "in_progress"
        await transaction_monitor.track_token_transactions(token_address, force_refresh)
        analysis_status[analysis_id]["components"]["transaction_tracking"] = "completed"
        
        # Run all analyses in parallel
        pattern_task = _run_pattern_analysis(token_address, analysis_id, force_refresh)
        wash_trading_task = _run_wash_trading_analysis(token_address, analysis_id, force_refresh)
        pump_dump_task = _run_pump_dump_analysis(token_address, analysis_id, force_refresh)
        market_manipulation_task = _run_market_manipulation_analysis(token_address, analysis_id, force_refresh)
        volume_task = _run_volume_analysis(token_address, analysis_id, force_refresh)
        
        # Wait for all tasks to complete
        await pattern_task
        await wash_trading_task
        await pump_dump_task
        await market_manipulation_task
        await volume_task
        
        # Check for any component failures
        component_statuses = analysis_status[analysis_id]["components"]
        if any(status == "failed" for status in component_statuses.values()):
            analysis_status[analysis_id]["status"] = "partial"
        else:
            analysis_status[analysis_id]["status"] = "completed"
        
        # Record completion time
        analysis_status[analysis_id]["completed_at"] = datetime.utcnow()
        
        # Send webhook callback if URL provided
        if callback_url:
            await _send_callback(callback_url, analysis_id)
    
    except Exception as e:
        logger.error(f"Error running trading analysis for {token_address}: {e}", exc_info=True)
        analysis_status[analysis_id]["status"] = "failed"
        analysis_status[analysis_id]["error"] = str(e)
        analysis_status[analysis_id]["completed_at"] = datetime.utcnow()
        
        # Send error callback if URL provided
        if callback_url:
            await _send_callback(callback_url, analysis_id, error=str(e))


async def _run_pattern_analysis(token_address: str, analysis_id: str, force_refresh: bool):
    """Run pattern analysis and update status."""
    try:
        analysis_status[analysis_id]["components"]["pattern_analysis"] = "in_progress"
        result = trading_pattern_analyzer.analyze_token_trading(token_address, force_refresh)
        analysis_status[analysis_id]["results"]["pattern_analysis"] = result
        analysis_status[analysis_id]["components"]["pattern_analysis"] = "completed"
    except Exception as e:
        logger.error(f"Error running pattern analysis for {token_address}: {e}", exc_info=True)
        analysis_status[analysis_id]["components"]["pattern_analysis"] = "failed"
        analysis_status[analysis_id]["results"]["pattern_analysis"] = {"error": str(e)}


async def _run_wash_trading_analysis(token_address: str, analysis_id: str, force_refresh: bool):
    """Run wash trading analysis and update status."""
    try:
        analysis_status[analysis_id]["components"]["wash_trading"] = "in_progress"
        result = wash_trading_detector.detect_wash_trading(token_address, force_refresh)
        analysis_status[analysis_id]["results"]["wash_trading"] = result
        analysis_status[analysis_id]["components"]["wash_trading"] = "completed"
    except Exception as e:
        logger.error(f"Error running wash trading analysis for {token_address}: {e}", exc_info=True)
        analysis_status[analysis_id]["components"]["wash_trading"] = "failed"
        analysis_status[analysis_id]["results"]["wash_trading"] = {"error": str(e)}


async def _run_pump_dump_analysis(token_address: str, analysis_id: str, force_refresh: bool):
    """Run pump and dump analysis and update status."""
    try:
        analysis_status[analysis_id]["components"]["pump_dump"] = "in_progress"
        result = pump_dump_detector.detect_pump_dump(token_address, force_refresh)
        analysis_status[analysis_id]["results"]["pump_dump"] = result
        analysis_status[analysis_id]["components"]["pump_dump"] = "completed"
    except Exception as e:
        logger.error(f"Error running pump and dump analysis for {token_address}: {e}", exc_info=True)
        analysis_status[analysis_id]["components"]["pump_dump"] = "failed"
        analysis_status[analysis_id]["results"]["pump_dump"] = {"error": str(e)}


async def _run_market_manipulation_analysis(token_address: str, analysis_id: str, force_refresh: bool):
    """Run market manipulation analysis and update status."""
    try:
        analysis_status[analysis_id]["components"]["market_manipulation"] = "in_progress"
        result = market_manipulation_detector.detect_market_manipulation(token_address, force_refresh)
        analysis_status[analysis_id]["results"]["market_manipulation"] = result
        analysis_status[analysis_id]["components"]["market_manipulation"] = "completed"
    except Exception as e:
        logger.error(f"Error running market manipulation analysis for {token_address}: {e}", exc_info=True)
        analysis_status[analysis_id]["components"]["market_manipulation"] = "failed"
        analysis_status[analysis_id]["results"]["market_manipulation"] = {"error": str(e)}


async def _run_volume_analysis(token_address: str, analysis_id: str, force_refresh: bool):
    """Run volume analysis and update status."""
    try:
        analysis_status[analysis_id]["components"]["volume_analysis"] = "in_progress"
        result = volume_analyzer.analyze_volume(token_address, force_refresh)
        analysis_status[analysis_id]["results"]["volume_analysis"] = result
        analysis_status[analysis_id]["components"]["volume_analysis"] = "completed"
    except Exception as e:
        logger.error(f"Error running volume analysis for {token_address}: {e}", exc_info=True)
        analysis_status[analysis_id]["components"]["volume_analysis"] = "failed"
        analysis_status[analysis_id]["results"]["volume_analysis"] = {"error": str(e)}


async def _send_callback(callback_url: str, analysis_id: str, error: Optional[str] = None):
    """Send a callback with analysis results or error."""
    try:
        status_data = analysis_status[analysis_id]
        
        payload = {
            "analysis_id": analysis_id,
            "token_address": status_data["token_address"],
            "status": status_data["status"],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if error:
            payload["error"] = error
        elif status_data["status"] in ["completed", "partial"]:
            payload["results"] = status_data["results"]
        
        await webhook_service.send_webhook(callback_url, "trading_analysis", payload)
    except Exception as e:
        logger.error(f"Error sending callback for {analysis_id}: {e}", exc_info=True)


def _estimate_remaining_time(status_data: Dict[str, Any]) -> int:
    """Estimate remaining time for analysis completion in seconds."""
    if status_data["status"] in ["completed", "failed"]:
        return 0
    
    # Count completed components
    components = status_data["components"]
    completed_count = sum(1 for status in components.values() if status == "completed")
    total_components = len(components)
    
    # Base estimate on completed percentage
    if total_components == 0:
        return 60  # Default estimate
    
    completion_percentage = completed_count / total_components
    
    if completion_percentage == 0:
        return 60  # Just starting
    elif completion_percentage < 0.3:
        return 45  # Early stages
    elif completion_percentage < 0.7:
        return 30  # Mid-way
    else:
        return 15  # Nearly done 