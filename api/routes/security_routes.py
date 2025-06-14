"""
Security-related API routes.
Provides endpoints for rate limits, security status, and user session management.
"""
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Request, Response, HTTPException
from fastapi.security import OAuth2PasswordBearer
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from src.utils.rate_limiter import rate_limiter, RequestMetadata, RateLimitTier
from src.utils.session_manager import session_manager
from src.utils.encryption import encryption_service
from src.api.models.security_models import (
    LoginRequest,
    LoginResponse,
    RateLimitInfo,
    SessionInfo,
    SecurityStatusResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/security",
    tags=["security"]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/security/login", auto_error=False)

async def get_current_user(request: Request, token: Optional[str] = Depends(oauth2_scheme)) -> Optional[Dict[str, Any]]:
    """
    Get current user from token or session.
    
    Args:
        request: HTTP request
        token: OAuth2 token
        
    Returns:
        Optional[Dict]: User information or None
    """
    # If no token provided, check session cookie
    if not token:
        token = request.cookies.get("session")
    
    if not token:
        return None
    
    # Validate token
    is_valid, session, _ = await session_manager.validate_token(
        token,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    if is_valid and session:
        return {
            "user_id": session.user_id,
            "session_id": session.session_id,
            **session.data
        }
    
    return None

@router.post("/login", response_model=LoginResponse)
async def login(request: Request, login_data: LoginRequest, response: Response):
    """
    Login user and create session.
    
    Note: In a real application, this would validate credentials against a database.
    This implementation is simplified for demonstration purposes.
    """
    # Simplified authentication (in real app, validate against database)
    # In a real app, you would also hash the password and compare against stored hash
    if login_data.username == "demo" and login_data.password == "securepassword":
        # Create user session
        session = await session_manager.create_session(
            user_id=login_data.username,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            session_data={"role": "user"}
        )
        
        if not session:
            raise HTTPException(status_code=429, detail="Too many active sessions")
        
        # Set session cookie
        response.set_cookie(
            key="session",
            value=session.token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=3600  # 1 hour
        )
        
        return LoginResponse(
            access_token=session.token,
            token_type="bearer",
            expires_in=3600,
            user_id=login_data.username
        )
    
    # Log failed login attempt
    await session_manager.record_failed_login(
        user_id=login_data.username,
        ip_address=request.client.host
    )
    
    raise HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"}
    )

@router.post("/logout")
async def logout(request: Request, response: Response, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Logout user and invalidate session."""
    if not current_user:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    # Invalidate session
    if "session_id" in current_user:
        await session_manager.invalidate_session(current_user["session_id"])
    
    # Clear session cookie
    response.delete_cookie(key="session")
    
    return {"detail": "Successfully logged out"}

@router.get("/rate-limit-info", response_model=RateLimitInfo)
async def get_rate_limit_info(request: Request):
    """Get rate limit information for the current IP address."""
    # Create request metadata
    metadata = RequestMetadata(
        ip=request.client.host,
        endpoint="security.rate-limit-info",
        method=request.method,
        path=request.url.path,
        user_agent=request.headers.get("user-agent", "")
    )
    
    # Check rate limits (but always allow this endpoint)
    _, rate_limit_info = await rate_limiter.check_rate_limit(metadata)
    
    return RateLimitInfo(
        ip=request.client.host,
        limit=rate_limit_info.get("limit"),
        remaining=rate_limit_info.get("limits", {}).get("ip", {}).get("remaining", 0),
        reset=rate_limit_info.get("limits", {}).get("ip", {}).get("reset", 0),
        tier=rate_limit_info.get("tier", "basic")
    )

@router.get("/session-info", response_model=SessionInfo)
async def get_session_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get information about the current session."""
    if not current_user:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    return SessionInfo(
        user_id=current_user["user_id"],
        session_id=current_user.get("session_id"),
        role=current_user.get("role", "user"),
        is_active=True
    )

@router.get("/status", response_model=SecurityStatusResponse)
async def get_security_status(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get security subsystem status.
    Requires authentication with admin role.
    """
    # Check if user is admin
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Admin access required")
    
    # Get stats from various security subsystems
    rate_limit_stats = rate_limiter.get_stats()
    session_stats = session_manager.get_stats()
    
    return SecurityStatusResponse(
        rate_limiter=rate_limit_stats,
        session_manager=session_stats,
        total_requests=rate_limit_stats.get("total_requests", 0),
        blocked_requests=rate_limit_stats.get("blocked_requests", 0),
        active_sessions=session_stats.get("active_sessions", 0)
    )

@router.post("/invalidate-sessions/{user_id}")
async def invalidate_user_sessions(user_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Invalidate all sessions for a user.
    Requires authentication with admin role or the user themselves.
    """
    # Check if user is admin or the user themselves
    if not current_user:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    if current_user.get("role") != "admin" and current_user.get("user_id") != user_id:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Not authorized")
    
    # Invalidate sessions
    count = await session_manager.invalidate_user_sessions(user_id)
    
    return {"detail": f"Invalidated {count} sessions for user {user_id}"}

@router.post("/unlock-user/{user_id}")
async def unlock_user(user_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Unlock a locked user account.
    Requires authentication with admin role.
    """
    # Check if user is admin
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Admin access required")
    
    # Unlock user
    success = await session_manager.unlock_user(user_id)
    
    if success:
        return {"detail": f"Successfully unlocked user {user_id}"}
    else:
        return {"detail": f"User {user_id} was not locked or does not exist"} 