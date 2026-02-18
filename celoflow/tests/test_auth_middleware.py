"""
Tests for AuthMiddleware — ASGI middleware request authentication.
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
import pytest_asyncio

from middleware.auth_middleware import AuthMiddleware
from services.auth_service import AuthConfig, AuthService


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_scope(
    path: str = "/chat",
    method: str = "POST",
    headers: dict | None = None,
    client: tuple | None = ("127.0.0.1", 12345),
) -> dict:
    """Build a minimal ASGI HTTP scope."""
    raw_headers = []
    for k, v in (headers or {}).items():
        raw_headers.append((k.lower().encode(), v.encode()))
    return {
        "type": "http",
        "path": path,
        "method": method,
        "headers": raw_headers,
        "client": client,
    }


async def _make_receive(body: bytes = b"") -> dict:
    """Simple receive callable that returns body once."""
    return {"type": "http.request", "body": body, "more_body": False}


class ResponseCapture:
    """Captures ASGI send() calls."""

    def __init__(self):
        self.status = None
        self.headers = {}
        self.body = b""

    async def __call__(self, message: dict):
        if message["type"] == "http.response.start":
            self.status = message["status"]
            for k, v in message.get("headers", []):
                self.headers[k.decode()] = v.decode()
        elif message["type"] == "http.response.body":
            self.body += message.get("body", b"")

    @property
    def json(self) -> dict:
        return json.loads(self.body) if self.body else {}


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def auth_config():
    return AuthConfig(
        jwt_secret="test-middleware-secret",
        jwt_algorithm="HS256",
        access_token_expiry=3600,
        refresh_token_expiry=86400,
        enable_tee_attestation=False,
        allowed_origins=["http://localhost:3000"],
        api_keys=["valid-api-key"],
        rate_limit_requests=100,
        rate_limit_window=60,
        public_paths=["/health", "/auth/login", "/auth/refresh", "/auth/attestation",
                      "/.well-known/mcp.json", "/.well-known/oasp.json", "/.well-known/agent-card.json"],
    )


@pytest.fixture
def auth_service(auth_config):
    return AuthService(config=auth_config)


@pytest.fixture
def downstream_app():
    """Mock downstream ASGI app that records if it was called."""
    app = AsyncMock()

    async def passthrough(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b'{"ok": true}'})

    app.side_effect = passthrough
    return app


@pytest.fixture
def middleware(downstream_app, auth_service):
    return AuthMiddleware(app=downstream_app, auth_service=auth_service)


# ─── Public Path Tests ────────────────────────────────────────────────────────

class TestPublicPaths:
    @pytest.mark.asyncio
    async def test_public_path_passes_through(self, middleware, downstream_app):
        """Public paths bypass authentication."""
        scope = _make_scope(path="/health", method="GET")
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        downstream_app.assert_called_once()

    @pytest.mark.asyncio
    async def test_auth_login_is_public(self, middleware, downstream_app):
        """Auth login endpoint is public."""
        scope = _make_scope(path="/auth/login", method="POST")
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        downstream_app.assert_called_once()

    @pytest.mark.asyncio
    async def test_well_known_is_public(self, middleware, downstream_app):
        """Well-known endpoints are public."""
        scope = _make_scope(path="/.well-known/mcp.json", method="GET")
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        downstream_app.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_path_passes_through(self, middleware, downstream_app):
        """MCP paths bypass authentication."""
        scope = _make_scope(path="/mcp/sse", method="GET")
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        downstream_app.assert_called_once()


# ─── OPTIONS Preflight Tests ─────────────────────────────────────────────────

class TestCORSPreflight:
    @pytest.mark.asyncio
    async def test_options_passes_through(self, middleware, downstream_app):
        """OPTIONS requests bypass authentication."""
        scope = _make_scope(path="/chat", method="OPTIONS")
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        downstream_app.assert_called_once()


# ─── JWT Bearer Token Tests ──────────────────────────────────────────────────

class TestJWTAuth:
    @pytest.mark.asyncio
    async def test_valid_bearer_token(self, middleware, auth_service, downstream_app):
        """Valid Bearer token authenticates successfully."""
        token = auth_service.generate_access_token(subject="test-user")
        scope = _make_scope(
            path="/chat",
            method="POST",
            headers={"authorization": f"Bearer {token}"},
        )
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        downstream_app.assert_called_once()
        # Check auth info was injected into scope
        call_scope = downstream_app.call_args[0][0]
        assert call_scope.get("auth", {}).get("method") == "jwt"
        assert call_scope["auth"]["subject"] == "test-user"

    @pytest.mark.asyncio
    async def test_invalid_bearer_token(self, middleware, downstream_app):
        """Invalid Bearer token returns 401."""
        scope = _make_scope(
            path="/chat",
            method="POST",
            headers={"authorization": "Bearer invalid-token"},
        )
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        assert send.status == 401
        assert "invalid" in send.json.get("error", "").lower()
        downstream_app.assert_not_called()

    @pytest.mark.asyncio
    async def test_expired_bearer_token(self, middleware, downstream_app, auth_config):
        """Expired Bearer token returns 401."""
        # Create a token that's already expired
        payload = {
            "sub": "user",
            "exp": int(time.time()) - 10,
            "iat": int(time.time()) - 3610,
            "jti": "test-jti",
            "token_type": "access",
        }
        token = jwt.encode(payload, auth_config.jwt_secret, algorithm="HS256")
        scope = _make_scope(
            path="/chat",
            method="POST",
            headers={"authorization": f"Bearer {token}"},
        )
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        assert send.status == 401
        downstream_app.assert_not_called()

    @pytest.mark.asyncio
    async def test_origin_mismatch_in_token(self, middleware, auth_service, downstream_app):
        """Token with origin mismatch returns 403."""
        token = auth_service.generate_access_token(
            subject="user", origin="http://localhost:3000"
        )
        scope = _make_scope(
            path="/chat",
            method="POST",
            headers={
                "authorization": f"Bearer {token}",
                "origin": "http://evil.com",
            },
        )
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        assert send.status == 403
        downstream_app.assert_not_called()


# ─── API Key Tests ────────────────────────────────────────────────────────────

class TestAPIKeyAuth:
    @pytest.mark.asyncio
    async def test_valid_api_key(self, middleware, downstream_app):
        """Valid API key authenticates successfully."""
        scope = _make_scope(
            path="/chat",
            method="POST",
            headers={"x-api-key": "valid-api-key"},
        )
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        downstream_app.assert_called_once()
        call_scope = downstream_app.call_args[0][0]
        assert call_scope.get("auth", {}).get("method") == "api_key"

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, middleware, downstream_app):
        """Invalid API key returns 401."""
        scope = _make_scope(
            path="/chat",
            method="POST",
            headers={"x-api-key": "wrong-key"},
        )
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        assert send.status == 401
        downstream_app.assert_not_called()


# ─── Origin-Based Auth Tests ─────────────────────────────────────────────────

class TestOriginAuth:
    @pytest.mark.asyncio
    async def test_valid_origin_no_token(self, middleware, downstream_app):
        """Allowed origin without token passes through."""
        scope = _make_scope(
            path="/chat",
            method="POST",
            headers={"origin": "http://localhost:3000"},
        )
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        downstream_app.assert_called_once()
        call_scope = downstream_app.call_args[0][0]
        assert call_scope.get("auth", {}).get("method") == "origin"

    @pytest.mark.asyncio
    async def test_invalid_origin_no_token(self, middleware, downstream_app):
        """Disallowed origin without token returns 401."""
        scope = _make_scope(
            path="/chat",
            method="POST",
            headers={"origin": "http://evil.com"},
        )
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        assert send.status == 401
        downstream_app.assert_not_called()


# ─── No Auth Tests ───────────────────────────────────────────────────────────

class TestNoAuth:
    @pytest.mark.asyncio
    async def test_no_credentials_returns_401(self, middleware, downstream_app):
        """Request with no credentials returns 401."""
        scope = _make_scope(path="/chat", method="POST")
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        assert send.status == 401
        assert "authentication required" in send.json.get("error", "").lower()
        downstream_app.assert_not_called()


# ─── Rate Limiting Tests ─────────────────────────────────────────────────────

class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, downstream_app, auth_config):
        """Rate limit returns 429."""
        auth_config.rate_limit_requests = 2
        service = AuthService(config=auth_config)
        mw = AuthMiddleware(app=downstream_app, auth_service=service)

        for _ in range(2):
            scope = _make_scope(
                path="/chat",
                method="POST",
                headers={"origin": "http://localhost:3000"},
            )
            send = ResponseCapture()
            await mw(scope, _make_receive, send)

        # Third request should be rate limited
        scope = _make_scope(
            path="/chat",
            method="POST",
            headers={"origin": "http://localhost:3000"},
        )
        send = ResponseCapture()
        await mw(scope, _make_receive, send)
        assert send.status == 429
        assert "rate limit" in send.json.get("error", "").lower()


# ─── Non-HTTP Scope Tests ────────────────────────────────────────────────────

class TestNonHTTP:
    @pytest.mark.asyncio
    async def test_websocket_passes_through(self, middleware, downstream_app):
        """Non-HTTP scopes pass through without auth."""
        scope = {"type": "websocket", "path": "/ws"}
        send = ResponseCapture()
        await middleware(scope, _make_receive, send)
        downstream_app.assert_called_once()
