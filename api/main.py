"""
Main API application for Blaze Analyst.
Sets up FastAPI with all routes.
"""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from src.api.health import router as health_router
from src.api.scanner import router as scanner_router
from src.api.watchlist import router as watchlist_router
from src.api.blockchain_gateway import router as blockchain_router
from src.api.routes.performance import router as performance_router
from src.api.routes.liquidity_routes import router as liquidity_router
# Import additional routers as needed

from src.utils.performance_monitor import performance_monitor, time_function

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Blaze Analyst API",
    description="API for the Blaze Analyst system",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware for request logging, timing, and performance monitoring
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests and their processing time."""
    start_time = time.time()
    
    # Get client IP and request details
    client_host = request.client.host if request.client else "unknown"
    method = request.method
    url = request.url.path
    
    logger.info(f"Request started: {method} {url} from {client_host}")
    
    # Process the request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add processing time header
        response.headers["X-Process-Time"] = str(process_time)
        
        # Record performance metrics
        performance_monitor.record_timer(f"api.request.{method.lower()}.time", process_time)
        performance_monitor.increment(f"api.request.{method.lower()}.count")
        performance_monitor.increment(f"api.response.{response.status_code}")
        
        # Log completion
        logger.info(f"Request completed: {method} {url} - Status: {response.status_code} - Took: {process_time:.4f}s")
        
        return response
    except Exception as e:
        # Log exception
        logger.error(f"Request failed: {method} {url} - Error: {str(e)}")
        
        # Record failure in performance metrics
        performance_monitor.increment("api.request.error")
        
        # Return error response
        process_time = time.time() - start_time
        error_response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(e)}
        )
        error_response.headers["X-Process-Time"] = str(process_time)
        
        return error_response

# Include all routers
app.include_router(health_router, tags=["Health"])
app.include_router(scanner_router, prefix="/scanner", tags=["Contract Scanner"])
app.include_router(watchlist_router, prefix="/watchlist", tags=["Watchlist"])
app.include_router(blockchain_router, prefix="/blockchain", tags=["Blockchain Data"])
app.include_router(performance_router, prefix="/admin", tags=["Admin"])
app.include_router(liquidity_router, prefix="/api", tags=["Liquidity Analysis"])
# Add additional routers here

# Add root endpoint
@app.get("/", tags=["Root"])
@time_function("api.root.time")
async def root():
    """Root endpoint for the API."""
    performance_monitor.increment("api.root.count")
    return {
        "name": "Blaze Analyst API",
        "version": "1.0.0",
        "description": "API for the Blaze Analyst system",
        "documentation": "/docs"
    }

# Add graceful shutdown events
@app.on_event("shutdown")
async def shutdown_event():
    """Perform cleanup on application shutdown."""
    logger.info("Application shutting down")
    # Add cleanup code here as needed 