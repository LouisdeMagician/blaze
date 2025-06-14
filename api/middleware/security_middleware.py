"""
Security middleware for API endpoints.
Provides rate limiting, session management, and encryption with the FastAPI application
"""
import time
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from fastapi import Request, Response, FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from src.utils.rate_limiter import rate_limiter, RequestMetadata, RateLimitTier
from src.utils.session_manager import session_manager
from src.utils.encryption import encryption_service
from src.utils.settings import (
    SECURITY_AUDIT_LOGGING_ENABLED,
    SECURITY_BOT_DETECTION_ENABLED,
    SECURITY_IP_GEOLOCATION_ENABLED
)

logger = logging.getLogger(__name__)

class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Security middleware for API endpoints.
    Implements rate limiting, session validation, and IP-based security.
    """
    
    def __init__(
        self, 
        app: ASGIApp,
        exclude_paths: List[str] = None,
        trusted_proxies: List[str] = None
    ):
        """
        Initialize the security middleware.
        
        Args:
            app: ASGI application
            exclude_paths: Paths to exclude from security checks
            trusted_proxies: Trusted proxy IP addresses
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"]
        self.trusted_proxies = trusted_proxies or ["127.0.0.1", "::1"]
        self.audit_logging_enabled = SECURITY_AUDIT_LOGGING_ENABLED
        self.bot_detection_enabled = SECURITY_BOT_DETECTION_ENABLED
        self.ip_geolocation_enabled = SECURITY_IP_GEOLOCATION_ENABLED
    
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """
        Process the request through security middleware.
        
        Args:
            request: HTTP request
            call_next: Next middleware in chain
            
        Returns:
            Response: HTTP response
        """
        # Skip security checks for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Start timing for performance metrics
        start_time = time.time()
        
        # Get client IP address (with proxy handling)
        client_ip = self._get_client_ip(request)
        
        # Create a unique endpoint identifier for rate limiting
        endpoint = f"{request.method.lower()}.{request.url.path.strip('/')}"
        endpoint = endpoint.replace("/", ".")
        
        # Extract user information from authorization header or session cookie
        user_id, session = await self._extract_user_info(request)
        
        # Create request metadata for rate limiting
        metadata = RequestMetadata(
            ip=client_ip,
            user_id=user_id,
            endpoint=endpoint,
            method=request.method,
            path=request.url.path,
            user_agent=request.headers.get("user-agent", ""),
            headers={k.lower(): v for k, v in request.headers.items()}
        )
        
        # Check rate limits
        allowed, rate_limit_info = await rate_limiter.check_rate_limit(metadata)
        
        if not allowed:
            # Log rate limit exceeded
            logger.warning(
                f"Rate limit exceeded: {client_ip} {request.method} {request.url.path} "
                f"(User: {user_id or 'anonymous'}, Reason: {rate_limit_info.get('reason', 'unknown')})"
            )
            
            # Create response with rate limit headers
            headers = rate_limit_info.get("headers", {})
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded: {rate_limit_info.get('reason', 'Too many requests')}"},
                headers=headers
            )
        
        # Check for bot/crawler detection if enabled
        if self.bot_detection_enabled and self._is_bot(request):
            if self._should_block_bot(request):
                logger.warning(f"Blocked bot request: {client_ip} {request.method} {request.url.path}")
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Access denied"}
                )
        
        # Audit logging for sensitive operations
        if (self.audit_logging_enabled and 
            request.method in ["POST", "PUT", "DELETE"] and
            not request.url.path.startswith("/public/")):
            self._log_audit_event(request, user_id, client_ip)
        
        # Process the request
        response = await call_next(request)
        
        # Add security headers to response
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
        
        # Add rate limit headers to response
        if "headers" in rate_limit_info:
            for header, value in rate_limit_info["headers"].items():
                response.headers[header] = value
        
        # Add timing header for performance monitoring
        response.headers["X-Response-Time"] = f"{(time.time() - start_time) * 1000:.2f}ms"
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Get the client IP address, handling proxies.
        
        Args:
            request: HTTP request
            
        Returns:
            str: Client IP address
        """
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for and any(proxy in self.trusted_proxies for proxy in request.client.host.split(", ")):
            # Get the original client IP from X-Forwarded-For
            return forwarded_for.split(",")[0].strip()
        
        # Use direct client IP
        return request.client.host
    
    async def _extract_user_info(self, request: Request) -> tuple[Optional[str], Optional[Any]]:
        """
        Extract user information from request.
        
        Args:
            request: HTTP request
            
        Returns:
            tuple: (user_id, session)
        """
        # Check for JWT token in Authorization header
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            is_valid, payload = encryption_service.verify_jwt(token)
            if is_valid and payload:
                user_id = payload.get("sub")
                session_id = payload.get("sid")
                
                if session_id:
                    # Validate session
                    is_valid, session, _ = await session_manager.validate_token(
                        token, 
                        ip_address=self._get_client_ip(request),
                        user_agent=request.headers.get("user-agent")
                    )
                    if is_valid and session:
                        return user_id, session
                else:
                    # Token without session
                    return user_id, None
        
        # Check for session cookie
        session_token = request.cookies.get("session")
        if session_token:
            is_valid, session, _ = await session_manager.validate_token(
                session_token,
                ip_address=self._get_client_ip(request),
                user_agent=request.headers.get("user-agent")
            )
            if is_valid and session:
                return session.user_id, session
        
        # No user identified
        return None, None
    
    def _is_bot(self, request: Request) -> bool:
        """
        Check if request is from a bot/crawler.
        
        Args:
            request: HTTP request
            
        Returns:
            bool: True if request is from a bot
        """
        user_agent = request.headers.get("user-agent", "").lower()
        
        # Check for common bot user agents
        bot_signatures = [
            "bot", "crawler", "spider", "slurp", "baiduspider",
            "yandex", "googlebot", "bingbot", "semrushbot"
        ]
        
        if any(sig in user_agent for sig in bot_signatures):
            return True
        
        # Check for missing accept headers (common for simple bots)
        if not request.headers.get("accept") and not request.headers.get("accept-language"):
            return True
        
        # Check for unusual request patterns
        headers = dict(request.headers)
        if len(headers) < 3:
            return True
        
        return False
    
    def _should_block_bot(self, request: Request) -> bool:
        """
        Determine if a bot should be blocked.
        
        Args:
            request: HTTP request
            
        Returns:
            bool: True if bot should be blocked
        """
        user_agent = request.headers.get("user-agent", "").lower()
        
        # Allow well-known legitimate bots
        allowed_bots = ["googlebot", "bingbot", "yandexbot"]
        if any(bot in user_agent for bot in allowed_bots):
            return False
        
        # Block bots accessing non-public API endpoints
        if not request.url.path.startswith("/public/") and not request.url.path.startswith("/docs"):
            return True
        
        # Block bots with suspicious patterns
        suspicious_patterns = [
            "zgrab", "masscan", "nmap", "nikto", "sqlmap", "jorgee",
            "dotbot", "mj12", "ahrefsbot", "semrushbot", "petalbot"
        ]
        if any(pattern in user_agent for pattern in suspicious_patterns):
            return True
        
        return False
    
    def _log_audit_event(self, request: Request, user_id: Optional[str], client_ip: str) -> None:
        """
        Log an audit event for sensitive operations.
        
        Args:
            request: HTTP request
            user_id: User ID
            client_ip: Client IP address
        """
        try:
            event = {
                "timestamp": time.time(),
                "user_id": user_id or "anonymous",
                "ip_address": client_ip,
                "method": request.method,
                "path": request.url.path,
                "user_agent": request.headers.get("user-agent", ""),
                "referer": request.headers.get("referer", "")
            }
            
            logger.info(f"AUDIT: {event}")
            
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")

def add_security_middleware(app: FastAPI, exclude_paths: List[str] = None, trusted_proxies: List[str] = None) -> None:
    """
    Add security middleware to FastAPI application.
    
    Args:
        app: FastAPI application
        exclude_paths: Paths to exclude from security checks
        trusted_proxies: Trusted proxy IP addresses
    """
    app.add_middleware(
        SecurityMiddleware,
        exclude_paths=exclude_paths,
        trusted_proxies=trusted_proxies
    ) 