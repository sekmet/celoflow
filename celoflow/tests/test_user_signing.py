"""Comprehensive tests for User Wallet Signing Service.

Tests cover:
- UserSigningService initialization
- PreparedTransfer dataclass
- Transfer preparation (simulated mode)
- Transfer execution (simulated mode)
- Transfer rejection
- Transfer expiry
- Pending transfer management
- Auto-swap step preparation
- Token resolution and decimals
- Edge cases: missing fields, expired transfers, duplicate IDs
"""

from __future__ import annotations

import asyncio
import json
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from services.user_signing_service import (
    UserSigningService,
    PreparedTransfer,
    SignerType,
    TransferStatus,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

USER_ADDRESS = "0x" + "a" * 40
RECIPIENT_ADDRESS = "0x" + "b" * 40


@pytest.fixture
def service():
    """Create a UserSigningService without RPC (simulated mode)."""
    return UserSigningService(mento_plugin=None, tee_plugin=None)


@pytest.fixture
def service_with_mock_mento():
    """Create a UserSigningService with mocked mento plugin."""
    mock_mento = MagicMock()
    mock_mento.w3 = None  # Simulated mode
    return UserSigningService(mento_plugin=mock_mento, tee_plugin=None)


# ═══════════════════════════════════════════════════════════════════
# Test: PreparedTransfer dataclass
# ═══════════════════════════════════════════════════════════════════

class TestPreparedTransfer:
    """Test the PreparedTransfer dataclass."""

    def test_default_timestamps(self):
        t = PreparedTransfer(
            transfer_id="test123",
            signer_type=SignerType.USER,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
            resolved_token="BRLm",
            token_address="0x" + "c" * 40,
            decimals=18,
            amount_wei=10**18,
            chain_id=44787,
        )
        assert t.created_at > 0
        assert t.expires_at > t.created_at
        assert t.expires_at - t.created_at == 300  # 5 minutes

    def test_is_expired_false(self):
        t = PreparedTransfer(
            transfer_id="test123",
            signer_type=SignerType.USER,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
            resolved_token="BRLm",
            token_address="0x" + "c" * 40,
            decimals=18,
            amount_wei=10**18,
            chain_id=44787,
        )
        assert not t.is_expired

    def test_is_expired_true(self):
        t = PreparedTransfer(
            transfer_id="test123",
            signer_type=SignerType.USER,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
            resolved_token="BRLm",
            token_address="0x" + "c" * 40,
            decimals=18,
            amount_wei=10**18,
            chain_id=44787,
            created_at=time.time() - 600,
            expires_at=time.time() - 300,
        )
        assert t.is_expired

    def test_to_dict(self):
        t = PreparedTransfer(
            transfer_id="test123",
            signer_type=SignerType.USER,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
            resolved_token="BRLm",
            token_address="0x" + "c" * 40,
            decimals=18,
            amount_wei=10**18,
            chain_id=44787,
        )
        d = t.to_dict()
        assert d["signer_type"] == "user"
        assert d["status"] == "pending"
        assert d["transfer_id"] == "test123"
        assert d["amount"] == 1.0

    def test_default_status_is_pending(self):
        t = PreparedTransfer(
            transfer_id="test123",
            signer_type=SignerType.USER,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
            resolved_token="BRLm",
            token_address="0x" + "c" * 40,
            decimals=18,
            amount_wei=10**18,
            chain_id=44787,
        )
        assert t.status == TransferStatus.PENDING


# ═══════════════════════════════════════════════════════════════════
# Test: SignerType and TransferStatus enums
# ═══════════════════════════════════════════════════════════════════

class TestEnums:
    """Test enum values."""

    def test_signer_type_values(self):
        assert SignerType.TEE.value == "tee"
        assert SignerType.USER.value == "user"

    def test_transfer_status_values(self):
        assert TransferStatus.PENDING.value == "pending"
        assert TransferStatus.SIGNED.value == "signed"
        assert TransferStatus.BROADCASTING.value == "broadcasting"
        assert TransferStatus.CONFIRMED.value == "confirmed"
        assert TransferStatus.FAILED.value == "failed"
        assert TransferStatus.EXPIRED.value == "expired"
        assert TransferStatus.REJECTED.value == "rejected"


# ═══════════════════════════════════════════════════════════════════
# Test: UserSigningService initialization
# ═══════════════════════════════════════════════════════════════════

class TestServiceInit:
    """Test service initialization."""

    def test_init_without_plugins(self):
        svc = UserSigningService()
        assert svc._mento_plugin is None
        assert svc._tee_plugin is None
        assert len(svc._pending) == 0

    def test_init_with_plugins(self):
        mock_mento = MagicMock()
        mock_tee = MagicMock()
        svc = UserSigningService(mento_plugin=mock_mento, tee_plugin=mock_tee)
        assert svc._mento_plugin is mock_mento
        assert svc._tee_plugin is mock_tee

    def test_max_pending_constant(self):
        assert UserSigningService.MAX_PENDING_PER_USER == 10

    def test_transfer_expiry_constant(self):
        assert UserSigningService.TRANSFER_EXPIRY == 300


# ═══════════════════════════════════════════════════════════════════
# Test: Transfer ID generation
# ═══════════════════════════════════════════════════════════════════

class TestTransferIdGeneration:
    """Test deterministic transfer ID generation."""

    def test_generates_hex_string(self, service):
        tid = service._generate_transfer_id(USER_ADDRESS, RECIPIENT_ADDRESS, 1.0, "BRLm")
        assert len(tid) == 16
        # Should be valid hex
        int(tid, 16)

    def test_same_params_same_id(self, service):
        tid1 = service._generate_transfer_id(USER_ADDRESS, RECIPIENT_ADDRESS, 1.0, "BRLm")
        tid2 = service._generate_transfer_id(USER_ADDRESS, RECIPIENT_ADDRESS, 1.0, "BRLm")
        assert tid1 == tid2

    def test_different_amounts_different_ids(self, service):
        tid1 = service._generate_transfer_id(USER_ADDRESS, RECIPIENT_ADDRESS, 1.0, "BRLm")
        tid2 = service._generate_transfer_id(USER_ADDRESS, RECIPIENT_ADDRESS, 2.0, "BRLm")
        assert tid1 != tid2

    def test_different_tokens_different_ids(self, service):
        tid1 = service._generate_transfer_id(USER_ADDRESS, RECIPIENT_ADDRESS, 1.0, "BRLm")
        tid2 = service._generate_transfer_id(USER_ADDRESS, RECIPIENT_ADDRESS, 1.0, "ZARm")
        assert tid1 != tid2


# ═══════════════════════════════════════════════════════════════════
# Test: Prepare transfer (simulated mode)
# ═══════════════════════════════════════════════════════════════════

class TestPrepareTransfer:
    """Test transfer preparation in simulated mode (no RPC)."""

    @pytest.mark.asyncio
    async def test_prepare_basic_transfer(self, service):
        result = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        assert "error" not in result
        assert result["signer_type"] == "user"
        assert result["status"] == "pending"
        assert result["amount"] == 1.0
        assert result["resolved_token"] == "BRLm"
        assert result["decimals"] == 18
        assert result["chain_id"] == 44787

    @pytest.mark.asyncio
    async def test_prepare_unknown_token(self, service):
        result = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="FAKE_TOKEN",
        )
        assert "error" in result
        assert "Unknown token" in result["error"]

    @pytest.mark.asyncio
    async def test_prepare_resolves_cusd_to_usdm(self, service):
        result = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=5.0,
            token="cUSD",
        )
        assert result["resolved_token"] == "USDm"

    @pytest.mark.asyncio
    async def test_prepare_resolves_ceur_to_eurm(self, service):
        result = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=5.0,
            token="cEUR",
        )
        assert result["resolved_token"] == "EURm"

    @pytest.mark.asyncio
    async def test_prepare_6_decimal_token(self, service):
        result = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="USDT",
        )
        assert result["decimals"] == 6
        assert result["amount_wei"] == 1_000_000

    @pytest.mark.asyncio
    async def test_prepare_18_decimal_token(self, service):
        result = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        assert result["decimals"] == 18
        assert result["amount_wei"] == 10**18

    @pytest.mark.asyncio
    async def test_prepare_stores_in_pending(self, service):
        result = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        tid = result["transfer_id"]
        assert tid in service._pending

    @pytest.mark.asyncio
    async def test_prepare_returns_existing_if_not_expired(self, service):
        r1 = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        r2 = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        assert r1["transfer_id"] == r2["transfer_id"]

    @pytest.mark.asyncio
    async def test_prepare_has_tx_data(self, service):
        result = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        assert result["tx_data"] is not None
        assert "to" in result["tx_data"]
        assert "from" in result["tx_data"]

    @pytest.mark.asyncio
    async def test_prepare_custom_chain_id(self, service):
        result = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
            chain_id=42220,
        )
        assert result["chain_id"] == 42220


# ═══════════════════════════════════════════════════════════════════
# Test: Execute signed transfer (simulated mode)
# ═══════════════════════════════════════════════════════════════════

class TestExecuteSignedTransfer:
    """Test executing user-signed transfers in simulated mode."""

    @pytest.mark.asyncio
    async def test_execute_simulated_success(self, service):
        # First prepare
        prepared = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        tid = prepared["transfer_id"]

        # Then execute with a fake signed tx
        result = await service.execute_signed_transfer(
            transfer_id=tid,
            signed_tx_hex="0x" + "ab" * 32,
        )
        assert result["status"] == "success"
        assert result["signer_type"] == "user"
        assert "tx_hash" in result
        assert "Simulated" in result.get("note", "")

    @pytest.mark.asyncio
    async def test_execute_unknown_transfer_id(self, service):
        result = await service.execute_signed_transfer(
            transfer_id="nonexistent",
            signed_tx_hex="0x" + "ab" * 32,
        )
        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_expired_transfer(self, service):
        # Prepare a transfer
        prepared = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        tid = prepared["transfer_id"]

        # Force expire it
        service._pending[tid].expires_at = time.time() - 1

        result = await service.execute_signed_transfer(
            transfer_id=tid,
            signed_tx_hex="0x" + "ab" * 32,
        )
        assert "error" in result
        assert "expired" in result["error"].lower() or "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_already_confirmed(self, service):
        prepared = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        tid = prepared["transfer_id"]

        # Execute once
        await service.execute_signed_transfer(tid, "0x" + "ab" * 32)

        # Try again
        result = await service.execute_signed_transfer(tid, "0x" + "cd" * 32)
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════
# Test: Reject transfer
# ═══════════════════════════════════════════════════════════════════

class TestRejectTransfer:
    """Test transfer rejection."""

    @pytest.mark.asyncio
    async def test_reject_pending_transfer(self, service):
        prepared = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        tid = prepared["transfer_id"]

        result = service.reject_transfer(tid)
        assert result["status"] == "rejected"
        assert service._pending[tid].status == TransferStatus.REJECTED

    def test_reject_unknown_transfer(self, service):
        result = service.reject_transfer("nonexistent")
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════
# Test: Get transfer
# ═══════════════════════════════════════════════════════════════════

class TestGetTransfer:
    """Test getting transfer status."""

    @pytest.mark.asyncio
    async def test_get_existing_transfer(self, service):
        prepared = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        tid = prepared["transfer_id"]

        result = service.get_transfer(tid)
        assert result is not None
        assert result["transfer_id"] == tid

    def test_get_nonexistent_transfer(self, service):
        result = service.get_transfer("nonexistent")
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# Test: Pending transfers
# ═══════════════════════════════════════════════════════════════════

class TestPendingTransfers:
    """Test pending transfer listing."""

    @pytest.mark.asyncio
    async def test_get_pending_for_user(self, service):
        await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        pending = service.get_pending_transfers(USER_ADDRESS)
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_get_pending_empty_for_other_user(self, service):
        await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        pending = service.get_pending_transfers("0x" + "f" * 40)
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_get_pending_case_insensitive(self, service):
        await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        pending = service.get_pending_transfers(USER_ADDRESS.upper())
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_confirmed_not_in_pending(self, service):
        prepared = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        tid = prepared["transfer_id"]
        await service.execute_signed_transfer(tid, "0x" + "ab" * 32)

        pending = service.get_pending_transfers(USER_ADDRESS)
        assert len(pending) == 0


# ═══════════════════════════════════════════════════════════════════
# Test: Cleanup expired
# ═══════════════════════════════════════════════════════════════════

class TestCleanupExpired:
    """Test expired transfer cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired(self, service):
        prepared = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        tid = prepared["transfer_id"]

        # Force expire
        service._pending[tid].expires_at = time.time() - 1
        service._cleanup_expired()

        assert tid not in service._pending

    @pytest.mark.asyncio
    async def test_cleanup_keeps_valid(self, service):
        prepared = await service.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token="BRLm",
        )
        tid = prepared["transfer_id"]

        service._cleanup_expired()
        assert tid in service._pending


# ═══════════════════════════════════════════════════════════════════
# Test: Auto-swap step preparation
# ═══════════════════════════════════════════════════════════════════

class TestAutoSwapSteps:
    """Test auto-swap step preparation for user signing."""

    def test_single_hop_usdm(self, service):
        from integrations.chain_config import ChainConfig
        config = ChainConfig.celo_sepolia()
        steps = service._prepare_auto_swap_steps(
            user_address=USER_ADDRESS,
            target_symbol="USDm",
            target_address=config.token_addresses["USDm"],
            deficit_wei=10**18,
            target_decimals=18,
            config=config,
            w3=MagicMock(),
        )
        assert len(steps) == 2  # approve + swap
        assert steps[0]["action"] == "approve"
        assert steps[1]["action"] == "swap"
        assert steps[1]["to_token"] == "USDm"

    def test_two_hop_brlm(self, service):
        from integrations.chain_config import ChainConfig
        config = ChainConfig.celo_sepolia()
        steps = service._prepare_auto_swap_steps(
            user_address=USER_ADDRESS,
            target_symbol="BRLm",
            target_address=config.token_addresses["BRLm"],
            deficit_wei=10**18,
            target_decimals=18,
            config=config,
            w3=MagicMock(),
        )
        assert len(steps) == 4  # approve + swap + approve + swap
        assert steps[0]["action"] == "approve"
        assert steps[1]["to_token"] == "USDm"
        assert steps[2]["action"] == "approve"
        assert steps[3]["to_token"] == "BRLm"

    def test_two_hop_zarm(self, service):
        from integrations.chain_config import ChainConfig
        config = ChainConfig.celo_sepolia()
        steps = service._prepare_auto_swap_steps(
            user_address=USER_ADDRESS,
            target_symbol="ZARm",
            target_address=config.token_addresses["ZARm"],
            deficit_wei=10**18,
            target_decimals=18,
            config=config,
            w3=MagicMock(),
        )
        assert len(steps) == 4
        assert steps[3]["to_token"] == "ZARm"

    def test_no_pool_returns_error(self, service):
        from integrations.chain_config import ChainConfig
        config = ChainConfig.celo_sepolia()
        steps = service._prepare_auto_swap_steps(
            user_address=USER_ADDRESS,
            target_symbol="FAKE",
            target_address="0x" + "0" * 40,
            deficit_wei=10**18,
            target_decimals=18,
            config=config,
            w3=MagicMock(),
        )
        assert len(steps) == 1
        assert "error" in steps[0]


# ═══════════════════════════════════════════════════════════════════
# Test: All supported tokens can be prepared
# ═══════════════════════════════════════════════════════════════════

ALL_TOKENS = [
    "USDm", "EURm", "BRLm", "KESm", "XOFm", "PHPm", "COPm",
    "GBPm", "CADm", "AUDm", "ZARm", "GHSm", "NGNm", "JPYm",
    "CHFm", "CELO", "USDT", "axlUSDC",
]


class TestAllTokensPrepare:
    """Verify prepare_transfer works for all 18 supported tokens."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token", ALL_TOKENS)
    async def test_prepare_all_tokens(self, token):
        svc = UserSigningService()
        result = await svc.prepare_transfer(
            user_address=USER_ADDRESS,
            recipient_address=RECIPIENT_ADDRESS,
            amount=1.0,
            token=token,
        )
        assert "error" not in result, f"Failed to prepare {token}: {result.get('error')}"
        assert result["resolved_token"] in (token, "USDm", "EURm", "BRLm")  # alias resolution
