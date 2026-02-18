"""Tests for fee comparison user preference integration.

Covers:
- get_user_setting / get_user_fee_comparison_preference helpers
- _build_dynamic_instructions() conditional fee section
- WalletContextMiddleware user_settings extraction
- /api/settings GET and PUT endpoints
- End-to-end preference propagation
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers — import server module components without starting the full server
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_user_settings():
    """Reset the in-memory _user_settings store between tests."""
    import server
    original = dict(server._user_settings)
    server._user_settings.clear()
    yield
    server._user_settings.clear()
    server._user_settings.update(original)


# ---------------------------------------------------------------------------
# Unit: get_user_setting / get_user_fee_comparison_preference
# ---------------------------------------------------------------------------

class TestGetUserSetting:
    def test_returns_default_when_no_settings(self):
        import server
        result = server.get_user_setting("unknown_user", "showFeeComparison", True)
        assert result is True

    def test_returns_stored_value(self):
        import server
        server._user_settings["user1"] = {"showFeeComparison": False}
        result = server.get_user_setting("user1", "showFeeComparison", True)
        assert result is False

    def test_returns_default_for_missing_key(self):
        import server
        server._user_settings["user1"] = {"theme": "dark"}
        result = server.get_user_setting("user1", "showFeeComparison", True)
        assert result is True

    def test_returns_none_default_when_not_specified(self):
        import server
        result = server.get_user_setting("user1", "nonexistent")
        assert result is None


class TestGetUserFeeComparisonPreference:
    def test_defaults_to_true_when_no_settings(self):
        import server
        result = server.get_user_fee_comparison_preference("default")
        assert result is True

    def test_returns_false_when_disabled(self):
        import server
        server._user_settings["default"] = {"showFeeComparison": False}
        result = server.get_user_fee_comparison_preference("default")
        assert result is False

    def test_returns_true_when_enabled(self):
        import server
        server._user_settings["default"] = {"showFeeComparison": True}
        result = server.get_user_fee_comparison_preference("default")
        assert result is True

    def test_uses_default_user_id(self):
        import server
        server._user_settings["default"] = {"showFeeComparison": False}
        result = server.get_user_fee_comparison_preference()
        assert result is False


# ---------------------------------------------------------------------------
# Unit: _build_dynamic_instructions() fee comparison section
# ---------------------------------------------------------------------------

class TestBuildDynamicInstructions:
    def test_fee_comparison_enabled_by_default(self):
        import server
        instructions = server._build_dynamic_instructions()
        assert "User Preference: ENABLED" in instructions
        assert "ALWAYS" in instructions
        assert "compare_fees_with_providers" in instructions
        assert "User Preference: DISABLED" not in instructions

    def test_fee_comparison_disabled_when_setting_false(self):
        import server
        server._user_settings["default"] = {"showFeeComparison": False}
        instructions = server._build_dynamic_instructions()
        assert "User Preference: DISABLED" in instructions
        assert "user has **disabled** fee comparisons" in instructions
        assert "User Preference: ENABLED" not in instructions

    def test_fee_comparison_enabled_when_setting_true(self):
        import server
        server._user_settings["default"] = {"showFeeComparison": True}
        instructions = server._build_dynamic_instructions()
        assert "User Preference: ENABLED" in instructions
        assert "User Preference: DISABLED" not in instructions

    def test_disabled_instructions_allow_explicit_request(self):
        import server
        server._user_settings["default"] = {"showFeeComparison": False}
        instructions = server._build_dynamic_instructions()
        assert "explicitly asks" in instructions
        assert "compare fees" in instructions

    def test_instructions_always_include_wallet_section(self):
        import server
        instructions = server._build_dynamic_instructions()
        assert "LIVE Wallet Context" in instructions

    def test_instructions_always_include_contacts_section(self):
        import server
        instructions = server._build_dynamic_instructions()
        assert "LIVE User Contacts" in instructions

    def test_instructions_include_system_prompt(self):
        import server
        from main import SYSTEM_PROMPT
        instructions = server._build_dynamic_instructions()
        assert "CeloFlow Remittance Agent" in instructions

    def test_switching_preference_changes_instructions(self):
        import server
        server._user_settings["default"] = {"showFeeComparison": True}
        enabled_instructions = server._build_dynamic_instructions()

        server._user_settings["default"] = {"showFeeComparison": False}
        disabled_instructions = server._build_dynamic_instructions()

        assert enabled_instructions != disabled_instructions
        assert "ENABLED" in enabled_instructions
        assert "DISABLED" in disabled_instructions


# ---------------------------------------------------------------------------
# Unit: WalletContextMiddleware — user_settings extraction
# ---------------------------------------------------------------------------

class TestMiddlewareUserSettingsExtraction:
    """Test that WalletContextMiddleware correctly extracts and stores user_settings."""

    def _make_receive(self, body: bytes):
        """Create a mock ASGI receive callable that yields the body once."""
        called = False

        async def receive():
            nonlocal called
            if not called:
                called = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        return receive

    def _make_send(self):
        responses = []

        async def send(message):
            responses.append(message)

        send.responses = responses
        return send

    @pytest.mark.asyncio
    async def test_middleware_extracts_user_settings(self):
        import server

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat/stream",
            "headers": [],
        }

        body = json.dumps({
            "messages": [{"role": "user", "content": "hello"}],
            "user_settings": {
                "userId": "test_user",
                "showFeeComparison": False,
                "defaultCurrency": "BRLm",
            },
        }).encode()

        inner_app = AsyncMock()
        middleware = server.WalletContextMiddleware(inner_app)
        receive = self._make_receive(body)
        send = self._make_send()

        await middleware(scope, receive, send)

        assert "test_user" in server._user_settings
        assert server._user_settings["test_user"]["showFeeComparison"] is False
        assert server._user_settings["test_user"]["defaultCurrency"] == "BRLm"

    @pytest.mark.asyncio
    async def test_middleware_uses_user_id_field(self):
        import server

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat",
            "headers": [],
        }

        body = json.dumps({
            "messages": [{"role": "user", "content": "hello"}],
            "user_settings": {
                "userId": "wallet_user",
                "showFeeComparison": True,
            },
        }).encode()

        inner_app = AsyncMock()
        middleware = server.WalletContextMiddleware(inner_app)
        receive = self._make_receive(body)
        send = self._make_send()

        await middleware(scope, receive, send)

        assert "wallet_user" in server._user_settings
        assert server._user_settings["wallet_user"]["showFeeComparison"] is True

    @pytest.mark.asyncio
    async def test_middleware_merges_settings(self):
        import server
        server._user_settings["default"] = {"showFeeComparison": True, "theme": "dark"}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat/stream",
            "headers": [],
        }

        body = json.dumps({
            "messages": [{"role": "user", "content": "hello"}],
            "user_settings": {
                "userId": "default",
                "showFeeComparison": False,
            },
        }).encode()

        inner_app = AsyncMock()
        middleware = server.WalletContextMiddleware(inner_app)
        receive = self._make_receive(body)
        send = self._make_send()

        await middleware(scope, receive, send)

        # showFeeComparison updated, theme preserved
        assert server._user_settings["default"]["showFeeComparison"] is False
        assert server._user_settings["default"]["theme"] == "dark"

    @pytest.mark.asyncio
    async def test_middleware_skips_non_chat_paths(self):
        import server

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/settings",
            "headers": [],
        }

        body = json.dumps({
            "user_settings": {"userId": "default", "showFeeComparison": False},
        }).encode()

        inner_app = AsyncMock()
        middleware = server.WalletContextMiddleware(inner_app)
        receive = self._make_receive(body)
        send = self._make_send()

        await middleware(scope, receive, send)

        # Settings should NOT be extracted for non-chat paths
        assert "default" not in server._user_settings

    @pytest.mark.asyncio
    async def test_middleware_handles_missing_user_settings(self):
        import server

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat/stream",
            "headers": [],
        }

        body = json.dumps({
            "messages": [{"role": "user", "content": "hello"}],
        }).encode()

        inner_app = AsyncMock()
        middleware = server.WalletContextMiddleware(inner_app)
        receive = self._make_receive(body)
        send = self._make_send()

        # Should not raise
        await middleware(scope, receive, send)

    @pytest.mark.asyncio
    async def test_middleware_rebuilds_agent_instructions(self):
        import server

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat/stream",
            "headers": [],
        }

        body = json.dumps({
            "messages": [{"role": "user", "content": "send money"}],
            "user_settings": {
                "userId": "default",
                "showFeeComparison": False,
            },
        }).encode()

        inner_app = AsyncMock()
        middleware = server.WalletContextMiddleware(inner_app)
        receive = self._make_receive(body)
        send = self._make_send()

        await middleware(scope, receive, send)

        # Agent instructions should reflect the disabled preference
        assert "DISABLED" in server.agent.instructions


# ---------------------------------------------------------------------------
# Integration: /api/settings endpoints
# ---------------------------------------------------------------------------

class TestSettingsEndpoints:
    @pytest.mark.asyncio
    async def test_get_settings_returns_defaults(self):
        from httpx import AsyncClient, ASGITransport
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/settings?user_id=new_user",
                headers={"Origin": "http://localhost:3000"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["showFeeComparison"] is True
        assert data["userId"] == "new_user"

    @pytest.mark.asyncio
    async def test_get_settings_returns_stored_values(self):
        from httpx import AsyncClient, ASGITransport
        import server

        server._user_settings["stored_user"] = {"showFeeComparison": False, "theme": "dark"}

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/settings?user_id=stored_user",
                headers={"Origin": "http://localhost:3000"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["showFeeComparison"] is False
        assert data["theme"] == "dark"

    @pytest.mark.asyncio
    async def test_put_settings_updates_store(self):
        from httpx import AsyncClient, ASGITransport
        import server

        payload = {
            "userId": "put_user",
            "showFeeComparison": False,
            "defaultCurrency": "EURm",
            "language": "es",
            "theme": "dark",
            "notifications": {"transfers": True, "recurring": False, "failures": True},
            "privacy": {"shareAnalytics": False, "saveHistory": True},
        }

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.put(
                "/api/settings",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Origin": "http://localhost:3000",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["settings"]["showFeeComparison"] is False
        assert data["settings"]["defaultCurrency"] == "EURm"

    @pytest.mark.asyncio
    async def test_put_settings_persists_to_memory(self):
        from httpx import AsyncClient, ASGITransport
        import server

        payload = {
            "userId": "persist_user",
            "showFeeComparison": False,
            "defaultCurrency": "USDm",
            "language": "en",
            "theme": "auto",
            "notifications": {"transfers": True, "recurring": True, "failures": True},
            "privacy": {"shareAnalytics": False, "saveHistory": True},
        }

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            await client.put(
                "/api/settings",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Origin": "http://localhost:3000",
                },
            )

        # Verify it was stored in memory
        assert "persist_user" in server._user_settings
        assert server._user_settings["persist_user"]["showFeeComparison"] is False


# ---------------------------------------------------------------------------
# Integration: fee comparison preference affects agent instructions end-to-end
# ---------------------------------------------------------------------------

class TestFeeComparisonEndToEnd:
    def test_default_user_gets_fee_comparison_enabled(self):
        import server
        # No settings stored — should default to enabled
        instructions = server._build_dynamic_instructions()
        assert "ENABLED" in instructions
        assert "compare_fees_with_providers" in instructions

    def test_disabling_fee_comparison_removes_tool_guidance(self):
        import server
        server._user_settings["default"] = {"showFeeComparison": False}
        instructions = server._build_dynamic_instructions()
        # The ENABLED section with compare_fees_with_providers should be absent
        assert "User Preference: ENABLED" not in instructions
        # The DISABLED section should be present
        assert "Do NOT show fee comparison tables" in instructions

    def test_enabling_fee_comparison_includes_tool_guidance(self):
        import server
        server._user_settings["default"] = {"showFeeComparison": True}
        instructions = server._build_dynamic_instructions()
        assert "compare_fees_with_providers" in instructions
        assert "Highlight savings" in instructions

    def test_preference_change_is_reflected_immediately(self):
        import server

        # Start disabled
        server._user_settings["default"] = {"showFeeComparison": False}
        disabled = server._build_dynamic_instructions()
        assert "DISABLED" in disabled

        # Switch to enabled
        server._user_settings["default"] = {"showFeeComparison": True}
        enabled = server._build_dynamic_instructions()
        assert "ENABLED" in enabled

        # Switch back to disabled
        server._user_settings["default"] = {"showFeeComparison": False}
        disabled_again = server._build_dynamic_instructions()
        assert "DISABLED" in disabled_again

    def test_multiple_users_independent_settings(self):
        import server
        server._user_settings["user_a"] = {"showFeeComparison": True}
        server._user_settings["user_b"] = {"showFeeComparison": False}

        pref_a = server.get_user_fee_comparison_preference("user_a")
        pref_b = server.get_user_fee_comparison_preference("user_b")

        assert pref_a is True
        assert pref_b is False
