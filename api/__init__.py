"""
API module initialization.
Sets up FastAPI and API routes.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import token_routes, scanner_routes, security_routes
from src.api.middleware.security_middleware import add_security_middleware
from src.utils.settings import SECURITY_CORS_ORIGINS

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        FastAPI: Configured FastAPI application
    """
    app = FastAPI(
        title="Blaze Analyst API",
        description="API for Blaze Analyst Solana token analysis",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=SECURITY_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add security middleware
    add_security_middleware(
        app,
        exclude_paths=["/docs", "/redoc", "/openapi.json", "/health", "/metrics"],
        trusted_proxies=["127.0.0.1", "::1"]
    )
    
    # Include routers
    app.include_router(token_routes.router)
    app.include_router(scanner_routes.router)
    app.include_router(security_routes.router)
    
    # Add health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "ok"}
    
    return app 