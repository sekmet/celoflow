"""
Tests for AuthService — JWT token management, TEE attestation, rate limiting.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
import pytest_asyncio

from services.auth_service import (
    AuthConfig,
    AuthResult,
    AuthService,
    RateLimiter,
    TokenPayload,
    TokenRevocationStore,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def auth_config():
    """Minimal auth config for testing."""
    return AuthConfig(
        jwt_secret="test-secret-key-for-unit-tests-only",
        jwt_algorithm="HS256",
        access_token_expiry=3600,
        refresh_token_expiry=86400,
        enable_tee_attestation=False,
        allowed_origins=["http://localhost:3000", "http://localhost:5173"],
        api_keys=["test-api-key-1", "test-api-key-2"],
        rate_limit_requests=10,
        rate_limit_window=60,
        public_paths=["/health", "/auth/login", "/auth/refresh", "/auth/attestation"],
    )


@pytest.fixture
def auth_service(auth_config):
    """AuthService instance with test config."""
    return AuthService(config=auth_config)


@pytest.fixture
def mock_tee_plugin():
    """Mock TEE plugin for attestation tests."""
    plugin = MagicMock()
    plugin.name = "tee"
    plugin.address = "0x1234567890abcdef"
    plugin.get_attestation = AsyncMock(return_value={
        "mode": "development",
        "address": "0x1234567890abcdef",
        "message": "TEE attestation not available in dev mode",
    })
    return plugin


@pytest.fixture
def auth_service_with_tee(auth_config, mock_tee_plugin):
    """AuthService with TEE plugin and attestation enabled."""
    auth_config.enable_tee_attestation = True
    return AuthService(config=auth_config, tee_plugin=mock_tee_plugin)


# ─── AuthConfig Tests ─────────────────────────────────────────────────────────

class TestAuthConfig:
    def test_from_env_defaults(self):
        """Config loads with sensible defaults when no env vars set."""
        with patch.dict("os.environ", {}, clear=True):
            config = AuthConfig.from_env()
            assert config.jwt_algorithm == "HS256"
            assert config.access_token_expiry == 3600
            assert config.enable_tee_attestation is False
            assert len(config.jwt_secret) > 0  # auto-generated

    def test_from_env_custom_values(self):
        """Config loads custom values from env vars."""
        env = {
            "JWT_SECRET": "my-custom-secret",
            "JWT_ALGORITHM": "HS384",
            "JWT_ACCESS_TOKEN_EXPIRY": "7200",
            "ENABLE_TEE_ATTESTATION": "true",
            "AUTH_ALLOWED_ORIGINS": "https://app.example.com,https://admin.example.com",
            "AUTH_API_KEYS": "key1,key2,key3",
            "AUTH_RATE_LIMIT_REQUESTS": "50",
        }
        with patch.dict("os.environ", env, clear=True):
            config = AuthConfig.from_env()
            assert config.jwt_secret == "my-custom-secret"
            assert config.jwt_algorithm == "HS384"
            assert config.access_token_expiry == 7200
            assert config.enable_tee_attestation is True
            assert len(config.allowed_origins) == 2
            assert len(config.api_keys) == 3
            assert config.rate_limit_requests == 50

    def test_from_env_empty_origins(self):
        """Empty origins string produces empty list."""
        with patch.dict("os.environ", {"AUTH_ALLOWED_ORIGINS": ""}, clear=True):
            config = AuthConfig.from_env()
            assert config.allowed_origins == []


# ─── Token Generation Tests ──────────────────────────────────────────────────

class TestTokenGeneration:
    def test_generate_access_token(self, auth_service):
        """Access token is a valid JWT with correct claims."""
        token = auth_service.generate_access_token(subject="test-user")
        decoded = jwt.decode(token, "test-secret-key-for-unit-tests-only", algorithms=["HS256"])
        assert decoded["sub"] == "test-user"
        assert decoded["token_type"] == "access"
        assert "jti" in decoded
        assert "exp" in decoded
        assert "iat" in decoded
        assert decoded["scopes"] == ["chat"]

    def test_generate_access_token_with_scopes(self, auth_service):
        """Access token includes custom scopes."""
        token = auth_service.generate_access_token(
            subject="admin", scopes=["chat", "admin"]
        )
        decoded = jwt.decode(token, "test-secret-key-for-unit-tests-only", algorithms=["HS256"])
        assert decoded["scopes"] == ["chat", "admin"]

    def test_generate_access_token_with_origin(self, auth_service):
        """Access token includes origin claim."""
        token = auth_service.generate_access_token(
            subject="user", origin="http://localhost:3000"
        )
        decoded = jwt.decode(token, "test-secret-key-for-unit-tests-only", algorithms=["HS256"])
        assert decoded["origin"] == "http://localhost:3000"

    def test_generate_access_token_tee_verified(self, auth_service):
        """Access token includes tee_verified flag."""
        token = auth_service.generate_access_token(
            subject="user", tee_verified=True
        )
        decoded = jwt.decode(token, "test-secret-key-for-unit-tests-only", algorithms=["HS256"])
        assert decoded["tee_verified"] is True

    def test_generate_refresh_token(self, auth_service):
        """Refresh token is a valid JWT with refresh type."""
        token = auth_service.generate_refresh_token(subject="test-user")
        decoded = jwt.decode(token, "test-secret-key-for-unit-tests-only", algorithms=["HS256"])
        assert decoded["sub"] == "test-user"
        assert decoded["token_type"] == "refresh"

    def test_generate_token_pair(self, auth_service):
        """Token pair returns both access and refresh tokens."""
        access, refresh = auth_service.generate_token_pair(subject="user")
        access_decoded = jwt.decode(access, "test-secret-key-for-unit-tests-only", algorithms=["HS256"])
        refresh_decoded = jwt.decode(refresh, "test-secret-key-for-unit-tests-only", algorithms=["HS256"])
        assert access_decoded["token_type"] == "access"
        assert refresh_decoded["token_type"] == "refresh"
        assert access_decoded["sub"] == "user"
        assert refresh_decoded["sub"] == "user"

    def test_tokens_have_unique_jtis(self, auth_service):
        """Each token has a unique JTI."""
        t1 = auth_service.generate_access_token(subject="user")
        t2 = auth_service.generate_access_token(subject="user")
        d1 = jwt.decode(t1, "test-secret-key-for-unit-tests-only", algorithms=["HS256"])
        d2 = jwt.decode(t2, "test-secret-key-for-unit-tests-only", algorithms=["HS256"])
        assert d1["jti"] != d2["jti"]


# ─── Token Validation Tests ──────────────────────────────────────────────────

class TestTokenValidation:
    def test_validate_valid_token(self, auth_service):
        """Valid token passes validation."""
        token = auth_service.generate_access_token(subject="user")
        valid, payload, error = auth_service.validate_token(token)
        assert valid is True
        assert payload is not None
        assert payload.sub == "user"
        assert payload.token_type == "access"
        assert error == ""

    def test_validate_expired_token(self, auth_config):
        """Expired token fails validation."""
        auth_config.access_token_expiry = -1  # Already expired
        service = AuthService(config=auth_config)
        token = service.generate_access_token(subject="user")
        valid, payload, error = service.validate_token(token)
        assert valid is False
        assert payload is None
        assert "expired" in error.lower()

    def test_validate_invalid_token(self, auth_service):
        """Malformed token fails validation."""
        valid, payload, error = auth_service.validate_token("not-a-valid-jwt")
        assert valid is False
        assert payload is None
        assert "invalid" in error.lower()

    def test_validate_wrong_secret(self, auth_service):
        """Token signed with different secret fails validation."""
        token = jwt.encode(
            {"sub": "user", "exp": int(time.time()) + 3600, "jti": "test", "iat": int(time.time())},
            "wrong-secret",
            algorithm="HS256",
        )
        valid, payload, error = auth_service.validate_token(token)
        assert valid is False

    def test_validate_revoked_token(self, auth_service):
        """Revoked token fails validation."""
        token = auth_service.generate_access_token(subject="user")
        auth_service.revoke_token(token)
        valid, payload, error = auth_service.validate_token(token)
        assert valid is False
        assert "revoked" in error.lower()


# ─── Token Refresh Tests ─────────────────────────────────────────────────────

class TestTokenRefresh:
    def test_refresh_with_valid_refresh_token(self, auth_service):
        """Refreshing with a valid refresh token returns new access token."""
        refresh = auth_service.generate_refresh_token(subject="user")
        success, new_access, error = auth_service.refresh_access_token(refresh)
        assert success is True
        assert new_access is not None
        assert error == ""
        # Verify new access token
        valid, payload, _ = auth_service.validate_token(new_access)
        assert valid is True
        assert payload.sub == "user"

    def test_refresh_with_access_token_fails(self, auth_service):
        """Refreshing with an access token (not refresh) fails."""
        access = auth_service.generate_access_token(subject="user")
        success, new_access, error = auth_service.refresh_access_token(access)
        assert success is False
        assert new_access is None
        assert "not a refresh token" in error.lower()

    def test_refresh_with_invalid_token_fails(self, auth_service):
        """Refreshing with an invalid token fails."""
        success, new_access, error = auth_service.refresh_access_token("invalid-token")
        assert success is False
        assert new_access is None


# ─── Token Revocation Tests ──────────────────────────────────────────────────

class TestTokenRevocation:
    def test_revoke_valid_token(self, auth_service):
        """Revoking a valid token succeeds."""
        token = auth_service.generate_access_token(subject="user")
        success, message = auth_service.revoke_token(token)
        assert success is True
        assert "revoked" in message.lower()

    def test_revoke_invalid_token(self, auth_service):
        """Revoking an invalid token fails."""
        success, message = auth_service.revoke_token("invalid-token")
        assert success is False

    def test_revoked_token_cannot_be_used(self, auth_service):
        """A revoked token cannot be validated."""
        token = auth_service.generate_access_token(subject="user")
        auth_service.revoke_token(token)
        valid, _, error = auth_service.validate_token(token)
        assert valid is False
        assert "revoked" in error.lower()


# ─── API Key Validation Tests ────────────────────────────────────────────────

class TestAPIKeyValidation:
    def test_valid_api_key(self, auth_service):
        """Valid API key passes validation."""
        assert auth_service.validate_api_key("test-api-key-1") is True
        assert auth_service.validate_api_key("test-api-key-2") is True

    def test_invalid_api_key(self, auth_service):
        """Invalid API key fails validation."""
        assert auth_service.validate_api_key("wrong-key") is False
        assert auth_service.validate_api_key("") is False

    def test_no_api_keys_configured(self, auth_config):
        """When no API keys configured, all keys fail."""
        auth_config.api_keys = []
        service = AuthService(config=auth_config)
        assert service.validate_api_key("any-key") is False


# ─── Origin Validation Tests ─────────────────────────────────────────────────

class TestOriginValidation:
    def test_valid_origin(self, auth_service):
        """Allowed origin passes validation."""
        assert auth_service.validate_origin("http://localhost:3000") is True
        assert auth_service.validate_origin("http://localhost:5173") is True

    def test_invalid_origin(self, auth_service):
        """Disallowed origin fails validation."""
        assert auth_service.validate_origin("http://evil.com") is False

    def test_none_origin(self, auth_service):
        """None origin fails validation when origins are configured."""
        assert auth_service.validate_origin(None) is False

    def test_wildcard_origin(self, auth_config):
        """Wildcard origin allows all."""
        auth_config.allowed_origins = ["*"]
        service = AuthService(config=auth_config)
        assert service.validate_origin("http://anything.com") is True

    def test_no_origins_configured(self, auth_config):
        """When no origins configured, all origins are allowed."""
        auth_config.allowed_origins = []
        service = AuthService(config=auth_config)
        assert service.validate_origin("http://anything.com") is True


# ─── Public Path Tests ────────────────────────────────────────────────────────

class TestPublicPaths:
    def test_public_path(self, auth_service):
        """Public paths are recognized."""
        assert auth_service.is_public_path("/health") is True
        assert auth_service.is_public_path("/auth/login") is True
        assert auth_service.is_public_path("/auth/refresh") is True
        assert auth_service.is_public_path("/auth/attestation") is True

    def test_private_path(self, auth_service):
        """Non-public paths are not recognized as public."""
        assert auth_service.is_public_path("/chat") is False
        assert auth_service.is_public_path("/chat/stream") is False
        assert auth_service.is_public_path("/v1/chat/completions") is False

    def test_subpath_of_public(self, auth_service):
        """Subpaths of public paths are also public."""
        assert auth_service.is_public_path("/auth/login/callback") is True


# ─── Rate Limiter Tests ──────────────────────────────────────────────────────

class TestRateLimiter:
    def test_allows_within_limit(self):
        """Requests within limit are allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for i in range(5):
            allowed, remaining = limiter.is_allowed("client1")
            assert allowed is True
            assert remaining == 4 - i

    def test_blocks_over_limit(self):
        """Requests over limit are blocked."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.is_allowed("client1")
        allowed, remaining = limiter.is_allowed("client1")
        assert allowed is False
        assert remaining == 0

    def test_separate_clients(self):
        """Different clients have separate limits."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.is_allowed("client1")
        limiter.is_allowed("client1")
        # client1 is at limit
        allowed1, _ = limiter.is_allowed("client1")
        assert allowed1 is False
        # client2 is fresh
        allowed2, _ = limiter.is_allowed("client2")
        assert allowed2 is True

    def test_cleanup_removes_stale(self):
        """Cleanup removes stale entries."""
        limiter = RateLimiter(max_requests=10, window_seconds=1)
        limiter.is_allowed("client1")
        time.sleep(1.1)
        limiter.cleanup()
        assert "client1" not in limiter._requests


# ─── Token Revocation Store Tests ────────────────────────────────────────────

class TestTokenRevocationStore:
    def test_revoke_and_check(self):
        """Revoked JTI is detected."""
        store = TokenRevocationStore()
        store.revoke("jti-123", time.time() + 3600)
        assert store.is_revoked("jti-123") is True
        assert store.is_revoked("jti-456") is False

    def test_cleanup_removes_expired(self):
        """Cleanup removes expired revocations."""
        store = TokenRevocationStore()
        store.revoke("jti-old", time.time() - 1)  # Already expired
        store.revoke("jti-new", time.time() + 3600)
        store.cleanup()
        assert store.is_revoked("jti-old") is False
        assert store.is_revoked("jti-new") is True


# ─── TEE Attestation Tests ───────────────────────────────────────────────────

class TestTEEAttestation:
    @pytest.mark.asyncio
    async def test_attestation_disabled(self, auth_service):
        """When TEE attestation is disabled, verification always succeeds."""
        verified, details = await auth_service.verify_tee_attestation()
        assert verified is True
        assert details["mode"] == "attestation_disabled"

    @pytest.mark.asyncio
    async def test_attestation_enabled_dev_mode(self, auth_service_with_tee):
        """In dev mode, TEE attestation succeeds with dev mode flag."""
        verified, details = await auth_service_with_tee.verify_tee_attestation()
        assert verified is True
        assert details["mode"] == "development"

    @pytest.mark.asyncio
    async def test_attestation_enabled_no_plugin(self, auth_config):
        """TEE attestation enabled but no plugin returns failure."""
        auth_config.enable_tee_attestation = True
        service = AuthService(config=auth_config, tee_plugin=None)
        verified, details = await service.verify_tee_attestation()
        assert verified is False
        assert "not configured" in details.get("error", "")

    @pytest.mark.asyncio
    async def test_attestation_with_quote(self, auth_config):
        """TEE attestation with a real quote succeeds."""
        auth_config.enable_tee_attestation = True
        plugin = MagicMock()
        plugin.get_attestation = AsyncMock(return_value={
            "quote": "base64-encoded-quote",
            "event_log": "log-data",
            "address": "0xabc",
            "domain": "celoflow.remittance",
        })
        service = AuthService(config=auth_config, tee_plugin=plugin)
        verified, details = await service.verify_tee_attestation()
        assert verified is True
        assert "quote" in details

    @pytest.mark.asyncio
    async def test_attestation_plugin_error(self, auth_config):
        """TEE attestation handles plugin errors gracefully."""
        auth_config.enable_tee_attestation = True
        plugin = MagicMock()
        plugin.get_attestation = AsyncMock(side_effect=RuntimeError("TEE unavailable"))
        service = AuthService(config=auth_config, tee_plugin=plugin)
        verified, details = await service.verify_tee_attestation()
        assert verified is False
        assert "TEE unavailable" in details.get("error", "")

    @pytest.mark.asyncio
    async def test_get_attestation_info_disabled(self, auth_service):
        """Attestation info when disabled."""
        info = await auth_service.get_attestation_info()
        assert info["enabled"] is False

    @pytest.mark.asyncio
    async def test_get_attestation_info_enabled(self, auth_service_with_tee):
        """Attestation info when enabled with plugin."""
        info = await auth_service_with_tee.get_attestation_info()
        assert info["enabled"] is True
        assert info["available"] is True


# ─── Full Authentication Flow Tests ──────────────────────────────────────────

class TestAuthenticationFlow:
    @pytest.mark.asyncio
    async def test_authenticate_with_api_key(self, auth_service):
        """Authentication with valid API key succeeds."""
        result = await auth_service.authenticate(api_key="test-api-key-1")
        assert result.success is True
        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.expires_in == 3600
        assert "api key" in result.message.lower()

    @pytest.mark.asyncio
    async def test_authenticate_with_invalid_api_key(self, auth_service):
        """Authentication with invalid API key fails."""
        result = await auth_service.authenticate(api_key="wrong-key")
        assert result.success is False
        assert result.access_token is None

    @pytest.mark.asyncio
    async def test_authenticate_with_valid_origin(self, auth_service):
        """Authentication with allowed origin succeeds."""
        result = await auth_service.authenticate(origin="http://localhost:3000")
        assert result.success is True
        assert result.access_token is not None

    @pytest.mark.asyncio
    async def test_authenticate_with_invalid_origin(self, auth_service):
        """Authentication with disallowed origin fails."""
        result = await auth_service.authenticate(origin="http://evil.com")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_authenticate_with_wallet(self, auth_service):
        """Authentication with wallet address succeeds."""
        result = await auth_service.authenticate(
            origin="http://localhost:3000",
            wallet_address="0x1234567890abcdef1234567890abcdef12345678",
        )
        assert result.success is True
        assert result.access_token is not None

    @pytest.mark.asyncio
    async def test_authenticate_rate_limited(self, auth_config):
        """Authentication is rate limited."""
        auth_config.rate_limit_requests = 2
        service = AuthService(config=auth_config)
        # Use up the rate limit
        await service.authenticate(origin="http://localhost:3000")
        await service.authenticate(origin="http://localhost:3000")
        # Third request should be rate limited
        result = await service.authenticate(origin="http://localhost:3000")
        assert result.success is False
        assert "rate limit" in result.message.lower()

    @pytest.mark.asyncio
    async def test_authenticate_tee_required_but_fails(self, auth_config):
        """Authentication fails when TEE attestation is required but unavailable."""
        auth_config.enable_tee_attestation = True
        service = AuthService(config=auth_config, tee_plugin=None)
        result = await service.authenticate(origin="http://localhost:3000")
        assert result.success is False
        assert "tee" in result.message.lower()


# ─── Audit Log Tests ─────────────────────────────────────────────────────────

class TestAuditLog:
    @pytest.mark.asyncio
    async def test_audit_log_records_events(self, auth_service):
        """Audit log records authentication events."""
        await auth_service.authenticate(origin="http://localhost:3000")
        log = auth_service.get_audit_log()
        assert len(log) > 0
        events = [entry["event"] for entry in log]
        assert "auth_success" in events

    def test_audit_log_limit(self, auth_service):
        """Audit log is bounded."""
        for i in range(200):
            auth_service._log_audit(f"test_event_{i}")
        log = auth_service.get_audit_log(limit=50)
        assert len(log) == 50

    def test_cleanup(self, auth_service):
        """Cleanup runs without error."""
        auth_service.cleanup()  # Should not raise
