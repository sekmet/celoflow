"""Tests for TransferPreviewService — two-step transfer flow preview generation."""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.transfer_preview_service import (
    TransferPreviewService,
    PREVIEW_TTL_SECONDS,
    AGENT_FEE_PCT,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

def make_mento_plugin(rate: float = 1.0) -> MagicMock:
    plugin = MagicMock()
    plugin.w3 = MagicMock()
    plugin.w3.is_connected.return_value = True
    plugin.find_optimal_route = AsyncMock(return_value={
        "available": True,
        "from_currency": "USDm",
        "to_currency": "BRLm",
        "amount": 100.0,
        "estimated_output": 100.0 * rate,
        "rate": rate,
        "route_type": "two_hop",
        "pool": "USDm/BRLm",
        "slippage_pct": 0.1,
    })
    return plugin


def make_fee_comparison_service() -> MagicMock:
    svc = MagicMock()
    svc.compare_fees = AsyncMock(return_value={
        "providers": [
            {"name": "Western Union", "total_fee": 6.5, "fee_percentage": 6.5, "speed": "1-3 days"},
            {"name": "Wise", "total_fee": 1.5, "fee_percentage": 1.5, "speed": "1-2 days"},
            {"name": "Remitly", "total_fee": 3.5, "fee_percentage": 3.5, "speed": "Minutes"},
        ]
    })
    return svc


def make_payment_reward_service(fee: float = 0.05) -> MagicMock:
    svc = MagicMock()
    svc.calculate_x402_service_fee.return_value = {
        "service_fee": fee,
        "fee_percentage": 0.05,
        "currency": "USDm",
        "tier": "good",
        "multiplier": 1.2,
        "description": "CeloFlow agent service fee (x402)",
    }
    return svc


def make_tee_plugin(address: str = "0xTEEAddress123") -> MagicMock:
    plugin = MagicMock()
    account = MagicMock()
    account.address = address
    plugin.get_account.return_value = account
    return plugin


def make_service(
    with_mento: bool = True,
    with_fee_comparison: bool = True,
    with_payment_reward: bool = True,
    with_tee: bool = True,
) -> TransferPreviewService:
    return TransferPreviewService(
        mento_plugin=make_mento_plugin() if with_mento else None,
        fee_comparison_service=make_fee_comparison_service() if with_fee_comparison else None,
        payment_reward_service=make_payment_reward_service() if with_payment_reward else None,
        tee_plugin=make_tee_plugin() if with_tee else None,
    )


# ─── Init ──────────────────────────────────────────────────────────────────────

class TestTransferPreviewServiceInit:
    def test_init_with_all_dependencies(self):
        svc = make_service()
        assert svc._mento is not None
        assert svc._fee_comparison is not None
        assert svc._payment_reward is not None
        assert svc._tee is not None
        assert len(svc._preview_cache) == 0

    def test_init_without_dependencies(self):
        svc = TransferPreviewService()
        assert svc._mento is None
        assert svc._fee_comparison is None
        assert svc._payment_reward is None
        assert svc._tee is None


# ─── preview_transfer ──────────────────────────────────────────────────────────

class TestPreviewTransfer:
    @pytest.mark.asyncio
    async def test_basic_preview_structure(self):
        svc = make_service()
        result = await svc.preview_transfer(
            recipient="0xRecipient123",
            amount=100.0,
            token="BRLm",
            destination_country="Brazil",
        )
        assert "preview_id" in result
        assert result["preview_id"].startswith("prev_")
        assert result["amount"] == 100.0
        assert result["token"] == "BRLm"
        assert result["recipient"] == "0xRecipient123"
        assert "fees" in result
        assert "route" in result
        assert "comparisons" in result
        assert "savings" in result
        assert "expires_at" in result
        assert "expires_in_seconds" in result

    @pytest.mark.asyncio
    async def test_preview_ttl_is_30_seconds(self):
        svc = make_service()
        before = time.time()
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        after = time.time()
        assert result["expires_at"] >= before + PREVIEW_TTL_SECONDS
        assert result["expires_at"] <= after + PREVIEW_TTL_SECONDS + 1
        assert result["expires_in_seconds"] == PREVIEW_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_preview_cached(self):
        svc = make_service()
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        preview_id = result["preview_id"]
        assert preview_id in svc._preview_cache

    @pytest.mark.asyncio
    async def test_preview_fee_breakdown_present(self):
        svc = make_service()
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        fees = result["fees"]
        assert "network_fee" in fees
        assert "service_fee" in fees
        assert "total_fee_usd" in fees
        assert fees["service_fee"] == 0.05
        assert fees["service_fee_tier"] == "good"

    @pytest.mark.asyncio
    async def test_preview_route_present(self):
        svc = make_service()
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        route = result["route"]
        assert route["available"] is True
        assert route["from_currency"] == "USDm"
        assert route["to_currency"] == "BRLm"

    @pytest.mark.asyncio
    async def test_preview_comparisons_present(self):
        svc = make_service()
        result = await svc.preview_transfer(
            "0xAddr", 100.0, "BRLm", destination_country="Brazil"
        )
        assert len(result["comparisons"]) > 0

    @pytest.mark.asyncio
    async def test_preview_savings_calculated(self):
        svc = make_service()
        result = await svc.preview_transfer(
            "0xAddr", 100.0, "BRLm", destination_country="Brazil"
        )
        savings = result["savings"]
        assert savings["available"] is True
        assert savings["celoflow_fee"] > 0
        assert savings["savings_vs_cheapest"] > 0

    @pytest.mark.asyncio
    async def test_preview_without_mento(self):
        svc = make_service(with_mento=False)
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        assert result["route"]["available"] is False

    @pytest.mark.asyncio
    async def test_preview_without_fee_comparison(self):
        svc = make_service(with_fee_comparison=False)
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        assert result["comparisons"] == []

    @pytest.mark.asyncio
    async def test_preview_fallback_fee_without_payment_reward(self):
        svc = make_service(with_payment_reward=False)
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        fees = result["fees"]
        assert fees["service_fee"] == pytest.approx(100.0 * AGENT_FEE_PCT)

    @pytest.mark.asyncio
    async def test_unique_preview_ids(self):
        svc = make_service()
        r1 = await svc.preview_transfer("0xAddr1", 100.0, "BRLm")
        r2 = await svc.preview_transfer("0xAddr2", 200.0, "KESm")
        assert r1["preview_id"] != r2["preview_id"]


# ─── validate_preview ──────────────────────────────────────────────────────────

class TestValidatePreview:
    @pytest.mark.asyncio
    async def test_valid_preview(self):
        svc = make_service()
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        validation = svc.validate_preview(result["preview_id"])
        assert validation["valid"] is True
        assert validation["expires_in_seconds"] > 0

    def test_invalid_preview_id(self):
        svc = make_service()
        validation = svc.validate_preview("nonexistent_id")
        assert validation["valid"] is False
        assert validation["reason"] == "preview_not_found"

    @pytest.mark.asyncio
    async def test_expired_preview(self):
        svc = make_service()
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        preview_id = result["preview_id"]
        # Force expiry
        svc._preview_cache[preview_id]["expires_at"] = time.time() - 1
        validation = svc.validate_preview(preview_id)
        assert validation["valid"] is False
        assert validation["reason"] == "preview_expired"
        # Should be removed from cache
        assert preview_id not in svc._preview_cache

    @pytest.mark.asyncio
    async def test_valid_preview_contains_transfer_info(self):
        svc = make_service()
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        validation = svc.validate_preview(result["preview_id"])
        assert validation["amount"] == 100.0
        assert validation["token"] == "BRLm"
        assert validation["recipient"] == "0xAddr"


# ─── get_preview ───────────────────────────────────────────────────────────────

class TestGetPreview:
    @pytest.mark.asyncio
    async def test_get_existing_preview(self):
        svc = make_service()
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        preview = svc.get_preview(result["preview_id"])
        assert preview is not None
        assert preview["amount"] == 100.0

    def test_get_nonexistent_preview(self):
        svc = make_service()
        assert svc.get_preview("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_expired_preview_returns_none(self):
        svc = make_service()
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        preview_id = result["preview_id"]
        svc._preview_cache[preview_id]["expires_at"] = time.time() - 1
        assert svc.get_preview(preview_id) is None


# ─── invalidate_preview ────────────────────────────────────────────────────────

class TestInvalidatePreview:
    @pytest.mark.asyncio
    async def test_invalidate_removes_from_cache(self):
        svc = make_service()
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        preview_id = result["preview_id"]
        assert preview_id in svc._preview_cache
        svc.invalidate_preview(preview_id)
        assert preview_id not in svc._preview_cache

    def test_invalidate_nonexistent_is_safe(self):
        svc = make_service()
        svc.invalidate_preview("nonexistent")  # Should not raise


# ─── _calculate_savings ────────────────────────────────────────────────────────

class TestCalculateSavings:
    def test_savings_with_comparisons(self):
        svc = make_service()
        comparisons = [
            {"name": "Western Union", "total_fee": 6.5},
            {"name": "Wise", "total_fee": 1.5},
        ]
        savings = svc._calculate_savings(100.0, 0.05, comparisons)
        assert savings["available"] is True
        assert savings["cheapest_provider"] == "Wise"
        assert savings["savings_vs_cheapest"] == pytest.approx(1.5 - 0.05)
        assert savings["most_expensive_provider"] == "Western Union"

    def test_savings_without_comparisons(self):
        svc = make_service()
        savings = svc._calculate_savings(100.0, 0.05, [])
        assert savings["available"] is False

    def test_savings_celoflow_fee_pct(self):
        svc = make_service()
        comparisons = [{"name": "WU", "total_fee": 5.0}]
        savings = svc._calculate_savings(100.0, 0.5, comparisons)
        assert savings["celoflow_fee_pct"] == pytest.approx(0.5)

    def test_no_negative_savings(self):
        svc = make_service()
        # CeloFlow is more expensive than provider
        comparisons = [{"name": "Cheap", "total_fee": 0.01}]
        savings = svc._calculate_savings(100.0, 1.0, comparisons)
        assert savings["savings_vs_cheapest"] == 0.0


# ─── _generate_preview_id ──────────────────────────────────────────────────────

class TestGeneratePreviewId:
    def test_id_starts_with_prev(self):
        pid = TransferPreviewService._generate_preview_id("0xAddr", 100.0, "BRLm", "user1")
        assert pid.startswith("prev_")

    def test_id_length(self):
        pid = TransferPreviewService._generate_preview_id("0xAddr", 100.0, "BRLm", "user1")
        assert len(pid) == len("prev_") + 12

    def test_different_inputs_different_ids(self):
        pid1 = TransferPreviewService._generate_preview_id("0xAddr1", 100.0, "BRLm", "u1")
        pid2 = TransferPreviewService._generate_preview_id("0xAddr2", 200.0, "KESm", "u2")
        assert pid1 != pid2


# ─── Cache Eviction ────────────────────────────────────────────────────────────

class TestCacheEviction:
    @pytest.mark.asyncio
    async def test_expired_previews_evicted(self):
        svc = make_service()
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        preview_id = result["preview_id"]
        # Force expiry
        svc._preview_cache[preview_id]["expires_at"] = time.time() - 1
        # Create new preview to trigger eviction
        await svc.preview_transfer("0xAddr2", 200.0, "KESm")
        assert preview_id not in svc._preview_cache

    @pytest.mark.asyncio
    async def test_tee_balance_check_unavailable_is_safe(self):
        svc = make_service(with_tee=False)
        result = await svc.preview_transfer("0xAddr", 100.0, "BRLm")
        tee_balance = result["tee_balance"]
        assert tee_balance["sufficient"] is True
        assert tee_balance["auto_swap_needed"] is False
