"""Tests for PaymentRewardService — x402 reputation-based agent reward processing."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.payment_reward_service import (
    PaymentRewardService,
    AGENT_FEE_PCT,
    CIRCUIT_BREAKER_THRESHOLD,
    CIRCUIT_BREAKER_RESET_SECS,
    MAX_RETRIES,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

def make_x402_client(reward_amount: float = 0.05, success: bool = True) -> MagicMock:
    client = MagicMock()
    client.calculate_agent_payment.return_value = {
        "agent_id": 0,
        "transfer_amount": 100.0,
        "reputation_score": 75.0,
        "tier": "good",
        "multiplier": 1.2,
        "base_reward": 0.5,
        "reward_amount": reward_amount,
        "currency": "USDm",
    }
    client.process_agent_reward = AsyncMock(return_value={
        "success": success,
        "payment_id": "abc123",
        "agent_id": 0,
        "reward_amount": reward_amount,
        "currency": "USDm",
        "tier": "good",
        "multiplier": 1.2,
    })
    return client


def make_reputation_service(score: float = 75.0) -> MagicMock:
    svc = MagicMock()
    svc.get_summary.return_value = {"score": score, "status": "good"}
    svc.record_event.return_value = {"score": score + 1.0}
    return svc


def make_service(
    reward_amount: float = 0.05,
    success: bool = True,
    reputation_score: float = 75.0,
    daily_cap: float = 100.0,
) -> PaymentRewardService:
    return PaymentRewardService(
        x402_client=make_x402_client(reward_amount, success),
        reputation_service=make_reputation_service(reputation_score),
        daily_cap_usd=daily_cap,
        agent_id=0,
    )


# ─── Init ──────────────────────────────────────────────────────────────────────

class TestPaymentRewardServiceInit:
    def test_init_defaults(self):
        svc = PaymentRewardService()
        assert svc._x402 is None
        assert svc._reputation is None
        assert svc._daily_cap_usd == 100.0
        assert svc._agent_id == 0
        assert not svc._circuit_open
        assert svc._consecutive_failures == 0

    def test_init_with_dependencies(self):
        x402 = make_x402_client()
        rep = make_reputation_service()
        svc = PaymentRewardService(
            x402_client=x402,
            reputation_service=rep,
            daily_cap_usd=50.0,
            agent_id=5,
        )
        assert svc._x402 is x402
        assert svc._reputation is rep
        assert svc._daily_cap_usd == 50.0
        assert svc._agent_id == 5


# ─── process_transfer_reward ───────────────────────────────────────────────────

class TestProcessTransferReward:
    @pytest.mark.asyncio
    async def test_successful_transfer_reward(self):
        svc = make_service(reward_amount=0.05)
        result = await svc.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=True,
            tx_hash="0xabc123",
        )
        assert result["success"] is True
        assert result["payment_id"] == "abc123"
        assert result["reward_amount"] == 0.05
        assert result["tier"] == "good"

    @pytest.mark.asyncio
    async def test_failed_transfer_skips_reward(self):
        svc = make_service()
        result = await svc.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=False,
        )
        assert result["success"] is False
        assert result["reason"] == "transfer_not_successful"

    @pytest.mark.asyncio
    async def test_zero_amount_rejected(self):
        svc = make_service()
        result = await svc.process_transfer_reward(
            agent_id=0,
            transfer_amount=0.0,
            success_status=True,
        )
        assert result["success"] is False
        assert result["reason"] == "invalid_transfer_amount"

    @pytest.mark.asyncio
    async def test_negative_amount_rejected(self):
        svc = make_service()
        result = await svc.process_transfer_reward(
            agent_id=0,
            transfer_amount=-5.0,
            success_status=True,
        )
        assert result["success"] is False
        assert result["reason"] == "invalid_transfer_amount"

    @pytest.mark.asyncio
    async def test_audit_log_populated_on_success(self):
        svc = make_service(reward_amount=0.05)
        await svc.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=True,
            tx_hash="0xtest",
        )
        log = svc.get_audit_log()
        assert len(log) == 1
        assert log[0]["status"] == "success"
        assert log[0]["reward_amount"] == 0.05
        assert log[0]["tx_hash"] == "0xtest"

    @pytest.mark.asyncio
    async def test_audit_log_populated_on_failure(self):
        svc = make_service(success=False)
        await svc.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=True,
        )
        log = svc.get_audit_log()
        assert len(log) == 1
        assert log[0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_reputation_updated_on_success(self):
        svc = make_service(reward_amount=0.05)
        await svc.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=True,
        )
        svc._reputation.record_event.assert_called_once()
        call_kwargs = svc._reputation.record_event.call_args
        assert call_kwargs[1]["event_type"] == "task_success"

    @pytest.mark.asyncio
    async def test_reputation_not_updated_on_failure(self):
        svc = make_service(success=False)
        await svc.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=True,
        )
        svc._reputation.record_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_daily_tracking_updated(self):
        svc = make_service(reward_amount=0.05)
        await svc.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=True,
        )
        tracking = svc._daily_tracking.get(0)
        assert tracking is not None
        assert tracking["earned"] == pytest.approx(0.05)

    @pytest.mark.asyncio
    async def test_daily_cap_blocks_reward(self):
        svc = make_service(reward_amount=0.05, daily_cap=0.01)
        # Manually set daily tracking to cap
        svc._daily_tracking[0] = {"earned": 0.01, "reset_ts": time.time()}
        result = await svc.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=True,
        )
        assert result["success"] is False
        assert result["reason"] == "daily_cap_reached"

    @pytest.mark.asyncio
    async def test_daily_cap_resets_after_24h(self):
        svc = make_service(reward_amount=0.05, daily_cap=0.01)
        # Set tracking as if it was 25 hours ago
        svc._daily_tracking[0] = {
            "earned": 0.01,
            "reset_ts": time.time() - 90_000,
        }
        result = await svc.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=True,
        )
        assert result["success"] is True


# ─── calculate_x402_service_fee ───────────────────────────────────────────────

class TestCalculateX402ServiceFee:
    def test_fee_with_x402_client(self):
        svc = make_service(reward_amount=0.05)
        svc._x402.calculate_agent_payment.return_value = {
            "reward_amount": 0.05,
            "tier": "good",
            "multiplier": 1.2,
        }
        result = svc.calculate_x402_service_fee(100.0, 75.0)
        assert result["service_fee"] == 0.05
        assert result["tier"] == "good"
        assert result["currency"] == "USDm"

    def test_fee_fallback_without_x402_client(self):
        svc = PaymentRewardService()
        result = svc.calculate_x402_service_fee(100.0)
        assert result["service_fee"] == pytest.approx(100.0 * AGENT_FEE_PCT)
        assert result["tier"] == "average"
        assert result["multiplier"] == 1.0

    def test_fee_percentage_calculation(self):
        svc = PaymentRewardService()
        result = svc.calculate_x402_service_fee(200.0)
        assert result["fee_percentage"] == pytest.approx(AGENT_FEE_PCT * 100, rel=1e-3)

    def test_zero_amount_fee(self):
        svc = PaymentRewardService()
        result = svc.calculate_x402_service_fee(0.0)
        assert result["service_fee"] == 0.0
        assert result["fee_percentage"] == 0.0


# ─── get_agent_earnings ────────────────────────────────────────────────────────

class TestGetAgentEarnings:
    @pytest.mark.asyncio
    async def test_earnings_after_successful_rewards(self):
        svc = make_service(reward_amount=0.05)
        await svc.process_transfer_reward(0, 100.0, True, "0xhash1")
        await svc.process_transfer_reward(0, 200.0, True, "0xhash2")
        earnings = svc.get_agent_earnings(0)
        assert earnings["total_earned"] == pytest.approx(0.10)
        assert earnings["total_transfers_rewarded"] == 2
        assert earnings["currency"] == "USDm"

    def test_earnings_empty_agent(self):
        svc = make_service()
        earnings = svc.get_agent_earnings(999)
        assert earnings["total_earned"] == 0.0
        assert earnings["total_transfers_rewarded"] == 0

    @pytest.mark.asyncio
    async def test_recent_payments_populated(self):
        svc = make_service(reward_amount=0.05)
        await svc.process_transfer_reward(0, 100.0, True, "0xhash1")
        earnings = svc.get_agent_earnings(0)
        assert len(earnings["recent_payments"]) == 1
        assert earnings["recent_payments"][0]["reward_amount"] == 0.05

    def test_earnings_includes_reputation_info(self):
        svc = make_service(reputation_score=90.0)
        earnings = svc.get_agent_earnings(0)
        assert earnings["reputation_score"] == 90.0
        assert earnings["tier"] == "excellent"
        assert earnings["multiplier"] == 1.5


# ─── Circuit Breaker ───────────────────────────────────────────────────────────

class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_circuit_trips_after_threshold_failures(self):
        svc = make_service(success=False)
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            await svc.process_transfer_reward(0, 100.0, True)
        assert svc._circuit_open is True

    @pytest.mark.asyncio
    async def test_circuit_blocks_payments_when_open(self):
        svc = make_service(success=False)
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            await svc.process_transfer_reward(0, 100.0, True)
        result = await svc.process_transfer_reward(0, 100.0, True)
        assert result["reason"] == "circuit_breaker_open"

    @pytest.mark.asyncio
    async def test_circuit_auto_resets_after_timeout(self):
        svc = make_service(success=False)
        for _ in range(CIRCUIT_BREAKER_THRESHOLD):
            await svc.process_transfer_reward(0, 100.0, True)
        assert svc._circuit_open is True
        # Simulate timeout
        svc._circuit_opened_at = time.time() - CIRCUIT_BREAKER_RESET_SECS - 1
        assert not svc._is_circuit_open()
        assert svc._circuit_open is False

    def test_circuit_status_closed(self):
        svc = make_service()
        status = svc.get_circuit_breaker_status()
        assert status["open"] is False
        assert status["consecutive_failures"] == 0

    @pytest.mark.asyncio
    async def test_consecutive_failures_reset_on_success(self):
        svc = make_service(success=False)
        # Each call to process_transfer_reward increments by 1 on failure
        await svc.process_transfer_reward(0, 100.0, True)
        assert svc._consecutive_failures == 1
        # Now make it succeed
        svc._x402.process_agent_reward = AsyncMock(return_value={
            "success": True,
            "payment_id": "xyz",
            "reward_amount": 0.05,
            "currency": "USDm",
            "tier": "good",
            "multiplier": 1.2,
        })
        await svc.process_transfer_reward(0, 100.0, True)
        assert svc._consecutive_failures == 0


# ─── Audit Log ─────────────────────────────────────────────────────────────────

class TestAuditLog:
    @pytest.mark.asyncio
    async def test_audit_log_filter_by_agent(self):
        svc = make_service(reward_amount=0.05)
        await svc.process_transfer_reward(0, 100.0, True)
        await svc.process_transfer_reward(1, 200.0, True)
        log_agent0 = svc.get_audit_log(agent_id=0)
        log_agent1 = svc.get_audit_log(agent_id=1)
        assert all(e["agent_id"] == 0 for e in log_agent0)
        assert all(e["agent_id"] == 1 for e in log_agent1)

    @pytest.mark.asyncio
    async def test_audit_log_limit(self):
        svc = make_service(reward_amount=0.05)
        for _ in range(5):
            await svc.process_transfer_reward(0, 100.0, True)
        log = svc.get_audit_log(limit=3)
        assert len(log) == 3

    @pytest.mark.asyncio
    async def test_audit_log_sorted_most_recent_first(self):
        svc = make_service(reward_amount=0.05)
        await svc.process_transfer_reward(0, 100.0, True)
        await svc.process_transfer_reward(0, 200.0, True)
        log = svc.get_audit_log()
        assert log[0]["timestamp"] >= log[1]["timestamp"]


# ─── Local Reward Fallback ─────────────────────────────────────────────────────

class TestLocalRewardFallback:
    def test_local_reward_excellent_tier(self):
        svc = PaymentRewardService()
        result = svc._calculate_local_reward(0, 100.0, 95.0, None)
        assert result["success"] is True
        assert result["tier"] == "excellent"
        assert result["multiplier"] == 1.5
        assert result["simulated"] is True

    def test_local_reward_poor_tier(self):
        svc = PaymentRewardService()
        result = svc._calculate_local_reward(0, 100.0, 10.0, None)
        assert result["tier"] == "poor"
        assert result["multiplier"] == 0.6

    def test_local_reward_capped_at_10(self):
        svc = PaymentRewardService()
        result = svc._calculate_local_reward(0, 100_000.0, 95.0, None)
        assert result["reward_amount"] <= 10.0

    def test_local_reward_has_payment_id(self):
        svc = PaymentRewardService()
        result = svc._calculate_local_reward(0, 100.0, 50.0, "0xhash")
        assert "payment_id" in result
        assert len(result["payment_id"]) > 0


# ─── Reputation Score Lookup ───────────────────────────────────────────────────

class TestReputationScoreLookup:
    def test_score_from_reputation_service(self):
        svc = make_service(reputation_score=85.0)
        score = svc._get_reputation_score(0)
        assert score == 85.0

    def test_score_fallback_when_no_service(self):
        svc = PaymentRewardService()
        score = svc._get_reputation_score(0)
        assert score == 50.0

    def test_score_fallback_on_exception(self):
        svc = make_service()
        svc._reputation.get_summary.side_effect = RuntimeError("DB error")
        score = svc._get_reputation_score(0)
        assert score == 50.0


# ─── Tier Info ─────────────────────────────────────────────────────────────────

class TestTierInfo:
    @pytest.mark.parametrize("score,expected_tier,expected_mult", [
        (95.0, "excellent", 1.5),
        (80.0, "good", 1.2),
        (60.0, "average", 1.0),
        (35.0, "below_average", 0.8),
        (10.0, "poor", 0.6),
    ])
    def test_tier_mapping(self, score: float, expected_tier: str, expected_mult: float):
        info = PaymentRewardService._get_tier_info(score)
        assert info["tier"] == expected_tier
        assert info["multiplier"] == expected_mult


# ─── No x402 Client Fallback ──────────────────────────────────────────────────

class TestNoX402ClientFallback:
    @pytest.mark.asyncio
    async def test_reward_without_x402_client(self):
        svc = PaymentRewardService(
            reputation_service=make_reputation_service(75.0),
            daily_cap_usd=100.0,
        )
        result = await svc.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=True,
        )
        assert result["success"] is True
        assert result["reward_amount"] > 0
        assert result.get("simulated") is True
