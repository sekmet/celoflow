"""
Authentication Middleware — Raw ASGI middleware for CeloFlow API.

Follows the same pure-ASGI pattern as WalletContextMiddleware to avoid
Starlette's body-replay RuntimeError. Sits BEFORE WalletContextMiddleware
in the middleware stack so every request is authenticated first.

Features:
- JWT Bearer token validation
- API key authentication (X-API-Key header)
- Origin-based access control
- Rate limiting per client
- Public path bypass for health/discovery endpoints
- Conditional TEE attestation enforcement
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from starlette.types import ASGIApp, Receive, Scope, Send

from services.auth_service import AuthService

logger = logging.getLogger("auth_middleware")


class AuthMiddleware:
    """Raw ASGI middleware for request authentication.

    Uses a pure ASGI approach (no BaseHTTPMiddleware) to avoid the
    Starlette body-replay RuntimeError when re-reading the request body.
    """

    def __init__(self, app: ASGIApp, auth_service: AuthService) -> None:
        self.app = app
        self.auth_service = auth_service

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")

        # Allow CORS preflight requests through
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # Allow public paths through without authentication
        if self.auth_service.is_public_path(path):
            await self.app(scope, receive, send)
            return

        # Allow MCP endpoints through (mounted separately)
        if path.startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        # Extract headers
        headers = self._parse_headers(scope)
        origin = headers.get("origin")
        authorization = headers.get("authorization")
        api_key = headers.get("x-api-key")

        # Determine client identifier for rate limiting
        client_id = self._get_client_id(scope, headers)

        # Rate limit check
        allowed, remaining = self.auth_service.check_rate_limit(client_id)
        if not allowed:
            await self._send_error(
                send,
                status=429,
                message="Rate limit exceeded",
                headers={
                    "Retry-After": str(self.auth_service.config.rate_limit_window),
                    "X-RateLimit-Remaining": "0",
                },
            )
            return

        # Try API key authentication first
        if api_key:
            if self.auth_service.validate_api_key(api_key):
                logger.debug("Authenticated via API key for %s", path)
                scope["auth"] = {"method": "api_key", "client_id": client_id}
                await self.app(scope, receive, send)
                return
            else:
                await self._send_error(send, status=401, message="Invalid API key")
                return

        # Try JWT Bearer token authentication
        if authorization:
            token = self._extract_bearer_token(authorization)
            if token:
                valid, payload, error = self.auth_service.validate_token(token)
                if valid and payload is not None:
                    # Validate origin if present in token
                    if payload.origin and origin and payload.origin != origin:
                        logger.warning(
                            "Origin mismatch: token=%s, request=%s",
                            payload.origin,
                            origin,
                        )
                        await self._send_error(
                            send, status=403, message="Origin mismatch"
                        )
                        return

                    logger.debug(
                        "Authenticated via JWT for %s (sub=%s)",
                        path,
                        payload.sub,
                    )
                    scope["auth"] = {
                        "method": "jwt",
                        "subject": payload.sub,
                        "tee_verified": payload.tee_verified,
                        "scopes": payload.scopes,
                        "client_id": client_id,
                    }
                    await self.app(scope, receive, send)
                    return
                else:
                    await self._send_error(
                        send, status=401, message=error or "Invalid token"
                    )
                    return

        # No credentials provided — check if origin is allowed for
        # unauthenticated access (development convenience)
        if origin and self.auth_service.validate_origin(origin):
            logger.debug("Allowing origin-based access for %s from %s", path, origin)
            scope["auth"] = {"method": "origin", "origin": origin, "client_id": client_id}
            await self.app(scope, receive, send)
            return

        # No valid authentication method found
        await self._send_error(
            send,
            status=401,
            message="Authentication required. Provide a Bearer token, API key, or connect from an allowed origin.",
            headers={"WWW-Authenticate": 'Bearer realm="celoflow"'},
        )

    # ── Helper Methods ────────────────────────────────────────────

    @staticmethod
    def _parse_headers(scope: Scope) -> Dict[str, str]:
        """Parse ASGI scope headers into a dict (lowercase keys)."""
        headers: Dict[str, str] = {}
        for key_bytes, value_bytes in scope.get("headers", []):
            key = key_bytes.decode("latin-1").lower()
            value = value_bytes.decode("latin-1")
            headers[key] = value
        return headers

    @staticmethod
    def _extract_bearer_token(authorization: str) -> Optional[str]:
        """Extract token from 'Bearer <token>' header."""
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        return None

    @staticmethod
    def _get_client_id(scope: Scope, headers: Dict[str, str]) -> str:
        """Derive a client identifier for rate limiting."""
        # Prefer X-Forwarded-For for proxied requests
        forwarded = headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Fall back to ASGI client info
        client = scope.get("client")
        if client:
            return f"{client[0]}:{client[1]}"

        return "unknown"

    @staticmethod
    async def _send_error(
        send: Send,
        status: int = 401,
        message: str = "Unauthorized",
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Send an error JSON response."""
        body = json.dumps({"error": message, "status": status}).encode("utf-8")

        response_headers: List[tuple] = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"access-control-allow-origin", b"*"),
        ]
        if headers:
            for k, v in headers.items():
                response_headers.append((k.encode(), v.encode()))

        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": response_headers,
            }
        )
        await send({"type": "http.response.body", "body": body})
