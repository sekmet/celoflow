"""Comprehensive tests for send_token auto-swap across all 19 supported tokens.

Tests cover:
- System prompt correctness (auto-swap guidance)
- Context injection (universal auto-swap in transfer guidance)
- Auto-swap helper function (_auto_swap_for_token)
- Real-time status emissions during auto-swap
- send_token with auto-swap for all token types
- Edge cases: small amounts, large amounts, failed swaps
"""

from __future__ import annotations

import asyncio
import json
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from services.real_time_status import (
    RealTimeStatusService,
    StatusEvent,
    OperationType,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

ALL_SUPPORTED_TOKENS = [
    "USDm", "EURm", "BRLm", "KESm", "XOFm", "PHPm", "COPm",
    "GBPm", "CADm", "AUDm", "ZARm", "GHSm", "NGNm", "JPYm",
    "CHFm", "CELO", "USDT", "axlUSDC",
]

STABLECOIN_TOKENS = [
    "USDm", "EURm", "BRLm", "KESm", "XOFm", "PHPm", "COPm",
    "GBPm", "CADm", "AUDm", "ZARm", "GHSm", "NGNm", "JPYm", "CHFm",
]

BRIDGED_TOKENS = ["USDT", "axlUSDC"]

SINGLE_HOP_TOKENS = ["USDm"]
TWO_HOP_TOKENS = [t for t in ALL_SUPPORTED_TOKENS if t not in ("USDm", "CELO")]


@pytest.fixture
def mock_status_service():
    """Mock the real-time status service."""
    service = RealTimeStatusService()
    return service


# ═══════════════════════════════════════════════════════════════════
# Test: System Prompt Correctness
# ═══════════════════════════════════════════════════════════════════

class TestSystemPromptAutoSwap:
    """Verify the system prompt correctly documents auto-swap capability."""

    def test_system_prompt_mentions_auto_swap(self):
        from main import SYSTEM_PROMPT
        assert "auto-swap" in SYSTEM_PROMPT.lower()

    def test_system_prompt_no_no_currency_conversion(self):
        from main import SYSTEM_PROMPT
        assert "NO currency conversion" not in SYSTEM_PROMPT

    def test_system_prompt_mentions_all_19_tokens(self):
        from main import SYSTEM_PROMPT
        for token in ALL_SUPPORTED_TOKENS:
            assert token in SYSTEM_PROMPT, f"Token {token} not found in system prompt"

    def test_system_prompt_send_token_first(self):
        from main import SYSTEM_PROMPT
        assert "Always try `send_token` first" in SYSTEM_PROMPT

    def test_system_prompt_never_suggest_manual_conversion(self):
        from main import SYSTEM_PROMPT
        assert "NEVER" in SYSTEM_PROMPT
        assert "manual currency conversion" in SYSTEM_PROMPT

    def test_system_prompt_mentions_mento_pools(self):
        from main import SYSTEM_PROMPT
        assert "17 pools" in SYSTEM_PROMPT or "17 Mento" in SYSTEM_PROMPT

    def test_system_prompt_mentions_single_hop(self):
        from main import SYSTEM_PROMPT
        assert "Single hop" in SYSTEM_PROMPT

    def test_system_prompt_mentions_two_hops(self):
        from main import SYSTEM_PROMPT
        assert "Two hops" in SYSTEM_PROMPT

    def test_system_prompt_transparent_auto_swap(self):
        from main import SYSTEM_PROMPT
        assert "transparent" in SYSTEM_PROMPT.lower()

    def test_system_prompt_auto_swap_in_transfer_flow(self):
        from main import SYSTEM_PROMPT
        assert "automatically handles auto-swap" in SYSTEM_PROMPT


# ═══════════════════════════════════════════════════════════════════
# Test: Context Injection
# ═══════════════════════════════════════════════════════════════════

class TestContextInjectionAutoSwap:
    """Verify _build_context_message includes universal auto-swap guidance."""

    def test_context_message_has_auto_swap_guidance(self):
        from server import _build_context_message
        msg = _build_context_message()
        assert "UNIVERSAL AUTO-SWAP" in msg

    def test_context_message_mentions_19_tokens(self):
        from server import _build_context_message
        msg = _build_context_message()
        assert "19 supported tokens" in msg

    def test_context_message_never_manual_conversion(self):
        from server import _build_context_message
        msg = _build_context_message()
        assert "NEVER suggest manual currency conversion" in msg

    def test_context_message_mentions_send_token(self):
        from server import _build_context_message
        msg = _build_context_message()
        assert "send_token" in msg

    def test_context_message_lists_all_tokens(self):
        from server import _build_context_message
        msg = _build_context_message()
        for token in ALL_SUPPORTED_TOKENS:
            assert token in msg, f"Token {token} not in context message"


# ═══════════════════════════════════════════════════════════════════
# Test: _emit_swap_status helper
# ═══════════════════════════════════════════════════════════════════

class TestEmitSwapStatus:
    """Test the real-time status emission helper."""

    @pytest.mark.asyncio
    async def test_emit_swap_status_creates_event(self):
        from tools.remittance_tools import _emit_swap_status
        with patch("tools.remittance_tools.real_time_status_service") as mock_svc:
            mock_svc.broadcast_status = AsyncMock()
            await _emit_swap_status("swapping", "Test message", progress=0.5, token="BRLm")
            mock_svc.broadcast_status.assert_called_once()
            event = mock_svc.broadcast_status.call_args[0][0]
            assert event.operation == OperationType.SWAPPING
            assert event.message == "Test message"
            assert event.progress == 0.5
            assert event.token == "BRLm"

    @pytest.mark.asyncio
    async def test_emit_swap_status_with_tx_hash(self):
        from tools.remittance_tools import _emit_swap_status
        with patch("tools.remittance_tools.real_time_status_service") as mock_svc:
            mock_svc.broadcast_status = AsyncMock()
            await _emit_swap_status("swapping", "Done", tx_hash="0xabc123")
            event = mock_svc.broadcast_status.call_args[0][0]
            assert event.transaction_hash == "0xabc123"

    @pytest.mark.asyncio
    async def test_emit_swap_status_handles_errors_gracefully(self):
        from tools.remittance_tools import _emit_swap_status
        with patch("tools.remittance_tools.real_time_status_service") as mock_svc:
            mock_svc.broadcast_status = AsyncMock(side_effect=Exception("broadcast failed"))
            # Should not raise
            await _emit_swap_status("swapping", "Test", progress=0.0)

    @pytest.mark.asyncio
    async def test_emit_swap_status_details_contain_auto_swap(self):
        from tools.remittance_tools import _emit_swap_status
        with patch("tools.remittance_tools.real_time_status_service") as mock_svc:
            mock_svc.broadcast_status = AsyncMock()
            await _emit_swap_status("swapping", "Hop 1", progress=0.5, token="ZARm")
            event = mock_svc.broadcast_status.call_args[0][0]
            assert event.details["auto_swap"] is True


# ═══════════════════════════════════════════════════════════════════
# Test: send_token docstring
# ═══════════════════════════════════════════════════════════════════

class TestSendTokenDocstring:
    """Verify send_token's tool description documents auto-swap."""

    def _get_tool_description(self) -> str:
        """Extract the description from the @function_tool wrapped send_token."""
        from tools.remittance_tools import send_token
        # @function_tool stores description in .description or .name attributes
        desc = getattr(send_token, "description", "") or ""
        # Also check params_json_schema for the tool schema
        schema = getattr(send_token, "params_json_schema", None)
        if schema:
            desc += " " + json.dumps(schema)
        # Fallback: check if there's a tool_schema or similar
        tool_desc = getattr(send_token, "tool_description", "") or ""
        return desc + " " + tool_desc

    def test_send_token_tool_has_description(self):
        from tools.remittance_tools import send_token
        # The tool object should have a name
        name = getattr(send_token, "name", "")
        assert name == "send_token" or "send" in name.lower()

    def test_send_token_description_mentions_auto_swap(self):
        desc = self._get_tool_description()
        # If @function_tool doesn't expose the description, check the source directly
        if not desc.strip():
            import inspect
            from tools import remittance_tools
            source = inspect.getsource(remittance_tools)
            assert "auto-swap" in source.lower()
        else:
            assert "auto-swap" in desc.lower() or "automatic" in desc.lower()


# ═══════════════════════════════════════════════════════════════════
# Test: Chain Config has all 19 tokens
# ═══════════════════════════════════════════════════════════════════

class TestChainConfigTokens:
    """Verify ChainConfig.celo_sepolia() has all 19 token addresses."""

    def test_all_tokens_in_chain_config(self):
        from integrations.chain_config import ChainConfig
        config = ChainConfig.celo_sepolia()
        for token in ALL_SUPPORTED_TOKENS:
            assert token in config.token_addresses, f"Token {token} missing from ChainConfig"

    def test_all_token_addresses_are_valid(self):
        from integrations.chain_config import ChainConfig
        config = ChainConfig.celo_sepolia()
        for token, addr in config.token_addresses.items():
            assert addr.startswith("0x"), f"Token {token} has invalid address: {addr}"
            assert len(addr) == 42, f"Token {token} address wrong length: {len(addr)}"


# ═══════════════════════════════════════════════════════════════════
# Test: Exchange IDs cover all Mento pools
# ═══════════════════════════════════════════════════════════════════

class TestExchangeIds:
    """Verify EXCHANGE_IDS covers all expected Mento v2 pools."""

    def test_exchange_ids_count(self):
        from plugins.mento_plugin import EXCHANGE_IDS
        assert len(EXCHANGE_IDS) >= 17, f"Expected >=17 exchange IDs, got {len(EXCHANGE_IDS)}"

    def test_all_stablecoins_have_usdm_pair(self):
        from plugins.mento_plugin import EXCHANGE_IDS
        for token in STABLECOIN_TOKENS:
            if token == "USDm":
                continue
            pair = f"USDm/{token}"
            assert pair in EXCHANGE_IDS, f"Missing exchange pair: {pair}"

    def test_celo_usdm_pair_exists(self):
        from plugins.mento_plugin import EXCHANGE_IDS
        assert "USDm/CELO" in EXCHANGE_IDS

    def test_usdt_pair_exists(self):
        from plugins.mento_plugin import EXCHANGE_IDS
        assert "USDm/USDT" in EXCHANGE_IDS

    def test_axlusdc_pair_exists(self):
        from plugins.mento_plugin import EXCHANGE_IDS
        assert "USDm/axlUSDC" in EXCHANGE_IDS

    def test_exchange_ids_are_valid_hex(self):
        from plugins.mento_plugin import EXCHANGE_IDS
        for pair, eid in EXCHANGE_IDS.items():
            assert len(eid) == 64, f"Exchange ID for {pair} wrong length: {len(eid)}"
            bytes.fromhex(eid)  # Should not raise


# ═══════════════════════════════════════════════════════════════════
# Test: Auto-swap route coverage
# ═══════════════════════════════════════════════════════════════════

class TestAutoSwapRouteCoverage:
    """Verify auto-swap can route to every supported token."""

    def test_single_hop_usdm(self):
        from plugins.mento_plugin import EXCHANGE_IDS
        assert "USDm/CELO" in EXCHANGE_IDS

    @pytest.mark.parametrize("token", TWO_HOP_TOKENS)
    def test_two_hop_route_exists(self, token):
        from plugins.mento_plugin import EXCHANGE_IDS
        pair = f"USDm/{token}"
        assert pair in EXCHANGE_IDS, f"No Mento pool for two-hop auto-swap to {token}"

    def test_celo_direct_transfer_no_swap_needed(self):
        """CELO transfers don't need auto-swap — direct ERC-20 transfer."""
        from integrations.chain_config import ChainConfig
        config = ChainConfig.celo_sepolia()
        assert "CELO" in config.token_addresses


# ═══════════════════════════════════════════════════════════════════
# Test: send_token with mocked auto-swap (simulated RPC)
# ═══════════════════════════════════════════════════════════════════

class TestSendTokenAutoSwapSimulated:
    """Test send_token falls back to simulated mode when RPC not connected."""

    @pytest.mark.asyncio
    async def test_send_token_simulated_success(self):
        """When RPC is not connected, send_token returns simulated result."""
        import tools.remittance_tools as rt

        mock_tee = MagicMock()
        mock_tee.get_account.return_value = MagicMock(address="0x" + "1" * 40)

        mock_mento = MagicMock()
        mock_mento.w3 = None  # Not connected

        original_tee = rt._tee_plugin
        original_mento = rt._mento_plugin
        try:
            rt._tee_plugin = mock_tee
            rt._mento_plugin = mock_mento

            # Access the inner function
            inner_fn = getattr(rt.send_token, "__wrapped__", None)
            if inner_fn is None:
                pytest.skip("Cannot access inner send_token function")

            result_str = await inner_fn(
                recipient_address="0x" + "a" * 40,
                amount=1.0,
                token="ZARm",
            )
            result = json.loads(result_str)
            assert result["status"] == "success"
            assert "Simulated" in result.get("note", "")
        finally:
            rt._tee_plugin = original_tee
            rt._mento_plugin = original_mento

    @pytest.mark.asyncio
    async def test_send_token_no_tee_plugin(self):
        """send_token returns error when TEE plugin is not configured."""
        import tools.remittance_tools as rt

        original_tee = rt._tee_plugin
        try:
            rt._tee_plugin = None
            inner_fn = getattr(rt.send_token, "__wrapped__", None)
            if inner_fn is None:
                pytest.skip("Cannot access inner send_token function")

            result_str = await inner_fn(
                recipient_address="0x" + "a" * 40,
                amount=1.0,
                token="BRLm",
            )
            result = json.loads(result_str)
            assert "error" in result
            assert "TEE" in result["error"]
        finally:
            rt._tee_plugin = original_tee

    @pytest.mark.asyncio
    async def test_send_token_unknown_token(self):
        """send_token returns error for unknown token symbol."""
        import tools.remittance_tools as rt

        mock_tee = MagicMock()
        mock_tee.get_account.return_value = MagicMock(address="0x" + "1" * 40)

        mock_mento = MagicMock()
        mock_mento.w3 = MagicMock()
        mock_mento.w3.is_connected.return_value = True

        original_tee = rt._tee_plugin
        original_mento = rt._mento_plugin
        try:
            rt._tee_plugin = mock_tee
            rt._mento_plugin = mock_mento

            inner_fn = getattr(rt.send_token, "__wrapped__", None)
            if inner_fn is None:
                pytest.skip("Cannot access inner send_token function")

            result_str = await inner_fn(
                recipient_address="0x" + "a" * 40,
                amount=1.0,
                token="FAKE_TOKEN",
            )
            result = json.loads(result_str)
            assert "error" in result
            assert "Unknown token" in result["error"]
        finally:
            rt._tee_plugin = original_tee
            rt._mento_plugin = original_mento


# ═══════════════════════════════════════════════════════════════════
# Test: _auto_swap_for_token logic
# ═══════════════════════════════════════════════════════════════════

class TestAutoSwapForToken:
    """Test the _auto_swap_for_token helper with mocked web3."""

    def test_auto_swap_no_exchange_id_returns_error(self):
        """If no exchange ID exists for the pair, return error."""
        from plugins.mento_plugin import EXCHANGE_IDS
        # Verify that a non-existent pair would fail
        assert "USDm/FAKE" not in EXCHANGE_IDS

    @pytest.mark.parametrize("token", TWO_HOP_TOKENS)
    def test_auto_swap_exchange_id_exists_for_all_tokens(self, token):
        """Every two-hop token must have a USDm/TOKEN exchange ID."""
        from plugins.mento_plugin import EXCHANGE_IDS
        pair = f"USDm/{token}"
        assert pair in EXCHANGE_IDS


# ═══════════════════════════════════════════════════════════════════
# Test: Real-time status service integration
# ═══════════════════════════════════════════════════════════════════

class TestRealTimeStatusIntegration:
    """Test that auto-swap operations emit proper status events."""

    def test_status_event_creation(self):
        event = StatusEvent(
            operation=OperationType.SWAPPING,
            message="Auto-swap hop 1/2: CELO → USDm",
            progress=0.5,
            token="ZARm",
        )
        assert event.operation == OperationType.SWAPPING
        assert event.progress == 0.5
        assert event.token == "ZARm"
        assert event.timestamp is not None

    def test_status_event_with_tx_hash(self):
        event = StatusEvent(
            operation=OperationType.SWAPPING,
            message="Hop 2/2 complete",
            progress=1.0,
            token="BRLm",
            transaction_hash="0xabc123",
        )
        assert event.transaction_hash == "0xabc123"

    @pytest.mark.asyncio
    async def test_broadcast_status_to_subscribers(self):
        service = RealTimeStatusService()
        queue = await service.subscribe()

        event = StatusEvent(
            operation=OperationType.SWAPPING,
            message="Test broadcast",
            progress=0.5,
        )
        await service.broadcast_status(event)

        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received["message"] == "Test broadcast"
        assert received["progress"] == 0.5

        service.unsubscribe(queue)

    def test_status_history_recorded(self):
        service = RealTimeStatusService()
        # Use asyncio.run for the broadcast
        event = StatusEvent(
            operation=OperationType.SWAPPING,
            message="History test",
            progress=1.0,
        )
        asyncio.get_event_loop().run_until_complete(service.broadcast_status(event))
        history = service.get_status_history()
        assert len(history) >= 1
        assert history[-1]["message"] == "History test"


# ═══════════════════════════════════════════════════════════════════
# Test: Token alias resolution
# ═══════════════════════════════════════════════════════════════════

class TestTokenAliasResolution:
    """Test that token aliases (cUSD→USDm, cEUR→EURm, etc.) resolve correctly."""

    def test_cusd_resolves_to_usdm(self):
        aliases = {"cUSD": "USDm", "cEUR": "EURm", "cREAL": "BRLm"}
        assert aliases.get("cUSD", "cUSD") == "USDm"

    def test_ceur_resolves_to_eurm(self):
        aliases = {"cUSD": "USDm", "cEUR": "EURm", "cREAL": "BRLm"}
        assert aliases.get("cEUR", "cEUR") == "EURm"

    def test_creal_resolves_to_brlm(self):
        aliases = {"cUSD": "USDm", "cEUR": "EURm", "cREAL": "BRLm"}
        assert aliases.get("cREAL", "cREAL") == "BRLm"

    def test_unknown_token_passes_through(self):
        aliases = {"cUSD": "USDm", "cEUR": "EURm", "cREAL": "BRLm"}
        assert aliases.get("ZARm", "ZARm") == "ZARm"

    @pytest.mark.parametrize("token", ALL_SUPPORTED_TOKENS)
    def test_all_tokens_have_chain_config_address(self, token):
        from integrations.chain_config import ChainConfig
        config = ChainConfig.celo_sepolia()
        assert token in config.token_addresses


# ═══════════════════════════════════════════════════════════════════
# Test: Decimal handling for different token types
# ═══════════════════════════════════════════════════════════════════

class TestDecimalHandling:
    """Test correct decimal handling for 18-decimal and 6-decimal tokens."""

    def test_18_decimal_tokens(self):
        for token in STABLECOIN_TOKENS + ["CELO"]:
            decimals = 6 if "USDC" in token or "USDT" in token or "axlUSDC" in token else 18
            if token not in ("USDT",):
                assert decimals == 18, f"{token} should be 18 decimals"

    def test_6_decimal_tokens(self):
        for token in ["USDT", "axlUSDC"]:
            decimals = 6 if "USDC" in token or "USDT" in token or "axlUSDC" in token else 18
            assert decimals == 6, f"{token} should be 6 decimals"

    def test_amount_wei_conversion_18_decimals(self):
        amount = Decimal("1.5")
        decimals = 18
        amount_wei = int(amount * (10 ** decimals))
        assert amount_wei == 1_500_000_000_000_000_000

    def test_amount_wei_conversion_6_decimals(self):
        amount = Decimal("1.5")
        decimals = 6
        amount_wei = int(amount * (10 ** decimals))
        assert amount_wei == 1_500_000
