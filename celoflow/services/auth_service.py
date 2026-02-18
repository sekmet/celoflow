"""
Authentication Service — TEE-aware JWT token management for CeloFlow API.

Provides:
- JWT token generation, validation, and refresh
- Conditional TEE attestation verification (when ENABLE_TEE_ATTESTATION=true)
- API key validation for service-to-service auth
- Rate limiting per client/user
- Comprehensive audit logging
"""

import hashlib
import hmac
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import jwt

logger = logging.getLogger("auth_service")


# ─── Configuration ────────────────────────────────────────────────────────────

@dataclass
class AuthConfig:
    """Authentication configuration loaded from environment variables."""

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expiry: int = 3600        # 1 hour
    refresh_token_expiry: int = 86400 * 7  # 7 days
    enable_tee_attestation: bool = False
    allowed_origins: List[str] = field(default_factory=list)
    api_keys: List[str] = field(default_factory=list)
    rate_limit_requests: int = 100         # per window
    rate_limit_window: int = 60            # seconds
    public_paths: List[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "AuthConfig":
        """Load configuration from environment variables."""
        jwt_secret = os.getenv("JWT_SECRET", "")
        if not jwt_secret:
            jwt_secret = secrets.token_hex(32)
            logger.warning(
                "JWT_SECRET not set — generated ephemeral secret. "
                "Set JWT_SECRET in .env for persistent sessions."
            )

        origins_raw = os.getenv("AUTH_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
        allowed_origins = [o.strip() for o in origins_raw.split(",") if o.strip()]

        api_keys_raw = os.getenv("AUTH_API_KEYS", "")
        api_keys = [k.strip() for k in api_keys_raw.split(",") if k.strip()]

        public_paths_raw = os.getenv(
            "AUTH_PUBLIC_PATHS",
            "/health,/.well-known/mcp.json,/.well-known/oasp.json,/.well-known/agent-card.json,/auth/login,/auth/refresh,/auth/attestation,/docs,/openapi.json,/status/stream,/status/current,/status/history",
        )
        public_paths = [p.strip() for p in public_paths_raw.split(",") if p.strip()]

        return cls(
            jwt_secret=jwt_secret,
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            access_token_expiry=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRY", "3600")),
            refresh_token_expiry=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRY", str(86400 * 7))),
            enable_tee_attestation=os.getenv("ENABLE_TEE_ATTESTATION", "false").lower() == "true",
            allowed_origins=allowed_origins,
            api_keys=api_keys,
            rate_limit_requests=int(os.getenv("AUTH_RATE_LIMIT_REQUESTS", "100")),
            rate_limit_window=int(os.getenv("AUTH_RATE_LIMIT_WINDOW", "60")),
            public_paths=public_paths,
        )


# ─── Token Payloads ──────────────────────────────────────────────────────────

@dataclass
class TokenPayload:
    """Decoded JWT token payload."""

    sub: str                     # subject (client identifier)
    exp: int                     # expiration timestamp
    iat: int                     # issued-at timestamp
    jti: str                     # unique token ID
    token_type: str = "access"   # "access" | "refresh"
    origin: Optional[str] = None
    tee_verified: bool = False
    scopes: List[str] = field(default_factory=lambda: ["chat"])


@dataclass
class AuthResult:
    """Result of an authentication attempt."""

    success: bool
    message: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    token_type: str = "Bearer"
    tee_verified: bool = False


# ─── Rate Limiter ─────────────────────────────────────────────────────────────

class RateLimiter:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}

    def is_allowed(self, client_id: str) -> Tuple[bool, int]:
        """Check if a request is allowed. Returns (allowed, remaining)."""
        now = time.time()
        cutoff = now - self.window_seconds

        if client_id not in self._requests:
            self._requests[client_id] = []

        # Prune old entries
        self._requests[client_id] = [
            ts for ts in self._requests[client_id] if ts > cutoff
        ]

        current_count = len(self._requests[client_id])
        if current_count >= self.max_requests:
            return False, 0

        self._requests[client_id].append(now)
        return True, self.max_requests - current_count - 1

    def cleanup(self) -> None:
        """Remove stale entries to prevent memory growth."""
        now = time.time()
        cutoff = now - self.window_seconds
        stale_keys = [
            k for k, v in self._requests.items()
            if not v or v[-1] < cutoff
        ]
        for k in stale_keys:
            del self._requests[k]


# ─── Revocation Store ────────────────────────────────────────────────────────

class TokenRevocationStore:
    """In-memory store for revoked token IDs (JTIs)."""

    def __init__(self) -> None:
        self._revoked: Dict[str, float] = {}  # jti -> expiry timestamp

    def revoke(self, jti: str, exp: float) -> None:
        """Revoke a token by its JTI."""
        self._revoked[jti] = exp

    def is_revoked(self, jti: str) -> bool:
        """Check if a token has been revoked."""
        return jti in self._revoked

    def cleanup(self) -> None:
        """Remove expired revocations to prevent memory growth."""
        now = time.time()
        expired = [jti for jti, exp in self._revoked.items() if exp < now]
        for jti in expired:
            del self._revoked[jti]


# ─── Auth Service ─────────────────────────────────────────────────────────────

class AuthService:
    """TEE-aware authentication service for CeloFlow API."""

    def __init__(self, config: Optional[AuthConfig] = None, tee_plugin: Any = None) -> None:
        self.config = config or AuthConfig.from_env()
        self.tee_plugin = tee_plugin
        self.rate_limiter = RateLimiter(
            max_requests=self.config.rate_limit_requests,
            window_seconds=self.config.rate_limit_window,
        )
        self.revocation_store = TokenRevocationStore()
        self._audit_log: List[Dict[str, Any]] = []
        logger.info(
            "AuthService initialized (tee_attestation=%s, origins=%d, api_keys=%d, public_paths=%d)",
            self.config.enable_tee_attestation,
            len(self.config.allowed_origins),
            len(self.config.api_keys),
            len(self.config.public_paths),
        )

    # ── Token Generation ──────────────────────────────────────────

    def generate_access_token(
        self,
        subject: str,
        origin: Optional[str] = None,
        tee_verified: bool = False,
        scopes: Optional[List[str]] = None,
    ) -> str:
        """Generate a JWT access token."""
        now = int(time.time())
        jti = secrets.token_hex(16)
        payload = {
            "sub": subject,
            "iat": now,
            "exp": now + self.config.access_token_expiry,
            "jti": jti,
            "token_type": "access",
            "origin": origin,
            "tee_verified": tee_verified,
            "scopes": scopes or ["chat"],
        }
        token = jwt.encode(payload, self.config.jwt_secret, algorithm=self.config.jwt_algorithm)
        self._log_audit("token_generated", subject=subject, token_type="access", jti=jti)
        return token

    def generate_refresh_token(self, subject: str) -> str:
        """Generate a JWT refresh token."""
        now = int(time.time())
        jti = secrets.token_hex(16)
        payload = {
            "sub": subject,
            "iat": now,
            "exp": now + self.config.refresh_token_expiry,
            "jti": jti,
            "token_type": "refresh",
        }
        token = jwt.encode(payload, self.config.jwt_secret, algorithm=self.config.jwt_algorithm)
        self._log_audit("refresh_token_generated", subject=subject, jti=jti)
        return token

    def generate_token_pair(
        self,
        subject: str,
        origin: Optional[str] = None,
        tee_verified: bool = False,
        scopes: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """Generate both access and refresh tokens."""
        access = self.generate_access_token(subject, origin, tee_verified, scopes)
        refresh = self.generate_refresh_token(subject)
        return access, refresh

    # ── Token Validation ──────────────────────────────────────────

    def validate_token(self, token: str) -> Tuple[bool, Optional[TokenPayload], str]:
        """Validate a JWT token. Returns (valid, payload, error_message)."""
        try:
            decoded = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm],
            )

            jti = decoded.get("jti", "")
            if self.revocation_store.is_revoked(jti):
                self._log_audit("token_revoked_access", jti=jti)
                return False, None, "Token has been revoked"

            payload = TokenPayload(
                sub=decoded.get("sub", ""),
                exp=decoded.get("exp", 0),
                iat=decoded.get("iat", 0),
                jti=jti,
                token_type=decoded.get("token_type", "access"),
                origin=decoded.get("origin"),
                tee_verified=decoded.get("tee_verified", False),
                scopes=decoded.get("scopes", ["chat"]),
            )
            return True, payload, ""

        except jwt.ExpiredSignatureError:
            self._log_audit("token_expired")
            return False, None, "Token has expired"
        except jwt.InvalidTokenError as e:
            self._log_audit("token_invalid", error=str(e))
            return False, None, f"Invalid token: {e}"

    # ── Token Refresh ─────────────────────────────────────────────

    def refresh_access_token(
        self, refresh_token: str, origin: Optional[str] = None
    ) -> Tuple[bool, Optional[str], str]:
        """Refresh an access token using a refresh token. Returns (success, new_access_token, error)."""
        valid, payload, error = self.validate_token(refresh_token)
        if not valid or payload is None:
            return False, None, error or "Invalid refresh token"

        if payload.token_type != "refresh":
            return False, None, "Token is not a refresh token"

        new_access = self.generate_access_token(
            subject=payload.sub,
            origin=origin,
            tee_verified=payload.tee_verified,
        )
        self._log_audit("token_refreshed", subject=payload.sub)
        return True, new_access, ""

    # ── Token Revocation ──────────────────────────────────────────

    def revoke_token(self, token: str) -> Tuple[bool, str]:
        """Revoke a token. Returns (success, message)."""
        valid, payload, error = self.validate_token(token)
        if not valid or payload is None:
            return False, error or "Invalid token"

        self.revocation_store.revoke(payload.jti, payload.exp)
        self._log_audit("token_revoked", subject=payload.sub, jti=payload.jti)
        return True, "Token revoked successfully"

    # ── API Key Validation ────────────────────────────────────────

    def validate_api_key(self, api_key: str) -> bool:
        """Validate an API key using constant-time comparison."""
        if not self.config.api_keys:
            return False
        return any(
            hmac.compare_digest(api_key, valid_key)
            for valid_key in self.config.api_keys
        )

    # ── Origin Validation ─────────────────────────────────────────

    def validate_origin(self, origin: Optional[str]) -> bool:
        """Validate request origin against allowed origins."""
        if not self.config.allowed_origins:
            return True  # No restrictions configured
        if not origin:
            return False
        # Wildcard support
        if "*" in self.config.allowed_origins:
            return True
        return origin in self.config.allowed_origins

    # ── Path Checking ─────────────────────────────────────────────

    def is_public_path(self, path: str) -> bool:
        """Check if a path is public (no auth required)."""
        for public_path in self.config.public_paths:
            if path == public_path or path.startswith(public_path + "/"):
                return True
        return False

    # ── Rate Limiting ─────────────────────────────────────────────

    def check_rate_limit(self, client_id: str) -> Tuple[bool, int]:
        """Check rate limit for a client. Returns (allowed, remaining)."""
        return self.rate_limiter.is_allowed(client_id)

    # ── TEE Attestation ───────────────────────────────────────────

    async def verify_tee_attestation(self, attestation_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        """Verify TEE attestation if enabled. Returns (verified, details)."""
        if not self.config.enable_tee_attestation:
            return True, {"mode": "attestation_disabled", "message": "TEE attestation not required"}

        if not self.tee_plugin:
            logger.warning("TEE attestation enabled but no TEE plugin configured")
            return False, {"error": "TEE plugin not configured"}

        try:
            attestation = await self.tee_plugin.get_attestation()
            if attestation.get("mode") == "development":
                # In dev mode, attestation is not available but we allow it
                self._log_audit("tee_attestation_dev_mode")
                return True, attestation

            # Verify the attestation quote
            if "quote" in attestation:
                self._log_audit("tee_attestation_verified", address=attestation.get("address"))
                return True, attestation

            return False, {"error": "No attestation quote available"}
        except Exception as e:
            logger.error("TEE attestation verification failed: %s", e)
            self._log_audit("tee_attestation_failed", error=str(e))
            return False, {"error": str(e)}

    async def get_attestation_info(self) -> Dict[str, Any]:
        """Get TEE attestation information."""
        if not self.config.enable_tee_attestation:
            return {
                "enabled": False,
                "message": "TEE attestation is disabled. Set ENABLE_TEE_ATTESTATION=true to enable.",
            }

        if not self.tee_plugin:
            return {"enabled": True, "available": False, "error": "TEE plugin not configured"}

        try:
            attestation = await self.tee_plugin.get_attestation()
            return {
                "enabled": True,
                "available": True,
                "mode": attestation.get("mode", "production"),
                "address": attestation.get("address"),
                "domain": attestation.get("domain"),
                "has_quote": "quote" in attestation,
            }
        except Exception as e:
            return {"enabled": True, "available": False, "error": str(e)}

    # ── Authentication Flow ───────────────────────────────────────

    async def authenticate(
        self,
        origin: Optional[str] = None,
        api_key: Optional[str] = None,
        wallet_address: Optional[str] = None,
    ) -> AuthResult:
        """Authenticate a client and return tokens.

        Supports three authentication methods:
        1. API key authentication (service-to-service)
        2. Origin-based authentication (celoflow-ui frontend)
        3. Wallet-based authentication (connected wallet)
        """
        # Determine subject identifier
        subject = wallet_address or origin or "anonymous"

        # Rate limit check
        allowed, remaining = self.check_rate_limit(subject)
        if not allowed:
            self._log_audit("rate_limited", subject=subject)
            return AuthResult(
                success=False,
                message=f"Rate limit exceeded. Try again in {self.config.rate_limit_window} seconds.",
            )

        # API key authentication
        if api_key:
            if self.validate_api_key(api_key):
                tee_verified, _ = await self.verify_tee_attestation()
                access, refresh = self.generate_token_pair(
                    subject=f"apikey:{subject}",
                    origin=origin,
                    tee_verified=tee_verified,
                    scopes=["chat", "admin"],
                )
                self._log_audit("auth_api_key", subject=subject)
                return AuthResult(
                    success=True,
                    message="Authenticated via API key",
                    access_token=access,
                    refresh_token=refresh,
                    expires_in=self.config.access_token_expiry,
                    tee_verified=tee_verified,
                )
            else:
                self._log_audit("auth_api_key_failed", subject=subject)
                return AuthResult(success=False, message="Invalid API key")

        # Origin-based authentication
        if origin:
            if not self.validate_origin(origin):
                self._log_audit("auth_origin_rejected", origin=origin)
                return AuthResult(success=False, message=f"Origin not allowed: {origin}")

        # TEE attestation verification
        tee_verified, tee_details = await self.verify_tee_attestation()
        if self.config.enable_tee_attestation and not tee_verified:
            return AuthResult(
                success=False,
                message=f"TEE attestation failed: {tee_details.get('error', 'Unknown error')}",
            )

        # Generate tokens
        access, refresh = self.generate_token_pair(
            subject=subject,
            origin=origin,
            tee_verified=tee_verified,
        )

        self._log_audit("auth_success", subject=subject, tee_verified=tee_verified)
        return AuthResult(
            success=True,
            message="Authentication successful",
            access_token=access,
            refresh_token=refresh,
            expires_in=self.config.access_token_expiry,
            tee_verified=tee_verified,
        )

    # ── Audit Logging ─────────────────────────────────────────────

    def _log_audit(self, event: str, **kwargs: Any) -> None:
        """Log an audit event."""
        entry = {
            "event": event,
            "timestamp": time.time(),
            **kwargs,
        }
        self._audit_log.append(entry)
        # Keep audit log bounded
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]
        logger.info("AUTH_AUDIT: %s %s", event, {k: v for k, v in kwargs.items() if k != "token"})

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit log entries."""
        return self._audit_log[-limit:]

    # ── Cleanup ───────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Periodic cleanup of rate limiter and revocation store."""
        self.rate_limiter.cleanup()
        self.revocation_store.cleanup()
