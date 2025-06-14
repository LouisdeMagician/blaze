"""
Data models for security-related API endpoints.
"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, EmailStr

class LoginRequest(BaseModel):
    """Login request model."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")
    remember_me: bool = Field(False, description="Remember me flag")

class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiry in seconds")
    user_id: str = Field(..., description="User ID")

class RateLimitInfo(BaseModel):
    """Rate limit information model."""
    ip: str = Field(..., description="Client IP address")
    limit: Any = Field(..., description="Rate limit")
    remaining: int = Field(..., description="Remaining requests")
    reset: int = Field(..., description="Reset timestamp")
    tier: str = Field(..., description="Rate limit tier")

class SessionInfo(BaseModel):
    """Session information model."""
    user_id: str = Field(..., description="User ID")
    session_id: Optional[str] = Field(None, description="Session ID")
    role: str = Field("user", description="User role")
    is_active: bool = Field(True, description="Session active status")

class SecurityStatusResponse(BaseModel):
    """Security subsystem status response model."""
    rate_limiter: Dict[str, Any] = Field(..., description="Rate limiter statistics")
    session_manager: Dict[str, Any] = Field(..., description="Session manager statistics")
    total_requests: int = Field(..., description="Total API requests")
    blocked_requests: int = Field(..., description="Blocked API requests")
    active_sessions: int = Field(..., description="Active user sessions")

class SecurityAuditEvent(BaseModel):
    """Security audit event model."""
    timestamp: float = Field(..., description="Event timestamp")
    event_type: str = Field(..., description="Event type")
    user_id: Optional[str] = Field(None, description="User ID")
    ip_address: str = Field(..., description="Client IP address")
    action: str = Field(..., description="Action performed")
    resource: str = Field(..., description="Resource affected")
    status: str = Field(..., description="Status (success/failure)")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")

class ChangePasswordRequest(BaseModel):
    """Change password request model."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password")

class ChangePasswordResponse(BaseModel):
    """Change password response model."""
    success: bool = Field(..., description="Operation success")
    message: str = Field(..., description="Response message")

class ResetPasswordRequest(BaseModel):
    """Reset password request model."""
    email: EmailStr = Field(..., description="User email")

class ResetPasswordConfirmRequest(BaseModel):
    """Reset password confirmation request model."""
    token: str = Field(..., description="Reset token")
    new_password: str = Field(..., description="New password")

class UserLockStatus(BaseModel):
    """User lock status model."""
    user_id: str = Field(..., description="User ID")
    is_locked: bool = Field(..., description="Lock status")
    failed_attempts: int = Field(0, description="Failed login attempts")
    last_failure: Optional[float] = Field(None, description="Last failure timestamp")

class AnomalyInfo(BaseModel):
    """Session anomaly information model."""
    session_id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")
    anomaly_type: str = Field(..., description="Anomaly type")
    severity: int = Field(..., description="Severity level (1-10)")
    timestamp: float = Field(..., description="Detection timestamp")
    is_resolved: bool = Field(False, description="Resolution status")
    details: Dict[str, Any] = Field(default_factory=dict, description="Anomaly details")

class AnomalyListResponse(BaseModel):
    """Anomaly list response model."""
    anomalies: List[AnomalyInfo] = Field(..., description="Anomalies list")
    total: int = Field(..., description="Total anomalies")
    unresolved: int = Field(..., description="Unresolved anomalies") 