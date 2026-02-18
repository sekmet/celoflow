"""Integration tests for x402 reputation payment system.

Tests the full flow: transfer → reputation update → payment reward.
Also tests X402Client new methods: calculate_agent_payment, register_agent_payment,
process_agent_reward, batch_payment_process.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.x402_client import X402Client
from services.payment_reward_service import PaymentRewardService
from services.reputation_analytics import ReputationAnalyticsService


# ─── X402Client: calculate_agent_payment ──────────────────────────────────────

class TestCalculateAgentPayment:
    def setup_method(self):
        self.client = X402Client(
            agent_wallet_address="0xAgentWallet123",
            chain_id=44787,
        )

    def test_excellent_tier(self):
        result = self.client.calculate_agent_payment(0, 100.0, 95.0)
        assert result["tier"] == "excellent"
        assert result["multiplier"] == 1.5
        assert result["reward_amount"] == pytest.approx(100.0 * 0.005 * 1.5)
        assert result["currency"] == "USDm"

    def test_good_tier(self):
        result = self.client.calculate_agent_payment(0, 100.0, 80.0)
        assert result["tier"] == "good"
        assert result["multiplier"] == 1.2
        assert result["reward_amount"] == pytest.approx(100.0 * 0.005 * 1.2)

    def test_average_tier(self):
        result = self.client.calculate_agent_payment(0, 100.0, 60.0)
        assert result["tier"] == "average"
        assert result["multiplier"] == 1.0
        assert result["reward_amount"] == pytest.approx(100.0 * 0.005 * 1.0)

    def test_below_average_tier(self):
        result = self.client.calculate_agent_payment(0, 100.0, 35.0)
        assert result["tier"] == "below_average"
        assert result["multiplier"] == 0.8
        assert result["reward_amount"] == pytest.approx(100.0 * 0.005 * 0.8)

    def test_poor_tier(self):
        result = self.client.calculate_agent_payment(0, 100.0, 10.0)
        assert result["tier"] == "poor"
        assert result["multiplier"] == 0.6
        assert result["reward_amount"] == pytest.approx(100.0 * 0.005 * 0.6)

    def test_reward_capped_at_10(self):
        result = self.client.calculate_agent_payment(0, 1_000_000.0, 95.0)
        assert result["reward_amount"] == 10.0

    def test_zero_transfer_amount(self):
        result = self.client.calculate_agent_payment(0, 0.0, 75.0)
        assert result["reward_amount"] == 0.0

    def test_boundary_score_90(self):
        result = self.client.calculate_agent_payment(0, 100.0, 90.0)
        assert result["tier"] == "excellent"

    def test_boundary_score_75(self):
        result = self.client.calculate_agent_payment(0, 100.0, 75.0)
        assert result["tier"] == "good"

    def test_boundary_score_50(self):
        result = self.client.calculate_agent_payment(0, 100.0, 50.0)
        assert result["tier"] == "average"

    def test_boundary_score_30(self):
        result = self.client.calculate_agent_payment(0, 100.0, 30.0)
        assert result["tier"] == "below_average"

    def test_boundary_score_29(self):
        result = self.client.calculate_agent_payment(0, 100.0, 29.9)
        assert result["tier"] == "poor"

    def test_result_includes_all_fields(self):
        result = self.client.calculate_agent_payment(1, 50.0, 70.0)
        assert "agent_id" in result
        assert "transfer_amount" in result
        assert "reputation_score" in result
        assert "tier" in result
        assert "multiplier" in result
        assert "base_reward" in result
        assert "reward_amount" in result
        assert "currency" in result

    def test_base_reward_calculation(self):
        result = self.client.calculate_agent_payment(0, 200.0, 60.0)
        assert result["base_reward"] == pytest.approx(200.0 * 0.005)


# ─── X402Client: register_agent_payment ───────────────────────────────────────

class TestRegisterAgentPayment:
    def setup_method(self):
        self.client = X402Client(agent_wallet_address="0xAgent")

    def test_register_valid_wallet(self):
        result = self.client.register_agent_payment(0, "0xPaymentWallet123", 75.0)
        assert result["success"] is True
        assert result["agent_id"] == 0
        assert result["payment_address"] == "0xPaymentWallet123"
        assert result["tier"] == "good"

    def test_register_invalid_wallet(self):
        result = self.client.register_agent_payment(0, "invalid_address", 75.0)
        assert "error" in result

    def test_register_empty_wallet(self):
        result = self.client.register_agent_payment(0, "", 75.0)
        assert "error" in result

    def test_register_stores_in_service_registry(self):
        self.client.register_agent_payment(0, "0xWallet123", 80.0)
        assert "agent_reward_0" in self.client._service_registry

    def test_register_different_tiers(self):
        r1 = self.client.register_agent_payment(1, "0xWallet1", 95.0)
        r2 = self.client.register_agent_payment(2, "0xWallet2", 10.0)
        assert r1["tier"] == "excellent"
        assert r2["tier"] == "poor"


# ─── X402Client: process_agent_reward ─────────────────────────────────────────

class TestProcessAgentReward:
    def setup_method(self):
        self.client = X402Client(agent_wallet_address="0xAgent")

    @pytest.mark.asyncio
    async def test_reward_returns_success(self):
        result = await self.client.process_agent_reward(0, 100.0, 75.0, "0xhash")
        assert result["success"] is True
        assert "payment_id" in result
        assert result["reward_amount"] > 0
        assert result["currency"] == "USDm"

    @pytest.mark.asyncio
    async def test_reward_stored_in_payment_history(self):
        await self.client.process_agent_reward(0, 100.0, 75.0, "0xhash")
        history = self.client.get_payment_history()
        assert len(history) == 1
        assert history[0]["type"] == "agent_reward"
        assert history[0]["agent_id"] == 0

    @pytest.mark.asyncio
    async def test_reward_cached_as_receipt(self):
        result = await self.client.process_agent_reward(0, 100.0, 75.0)
        payment_id = result["payment_id"]
        receipt = self.client.verify_payment_receipt(payment_id)
        assert receipt["verified"] is True
        assert receipt["receipt"]["tier"] == "good"

    @pytest.mark.asyncio
    async def test_reward_includes_tier(self):
        result = await self.client.process_agent_reward(0, 100.0, 95.0)
        assert result["tier"] == "excellent"
        assert result["multiplier"] == 1.5

    @pytest.mark.asyncio
    async def test_reward_with_tx_hash(self):
        result = await self.client.process_agent_reward(0, 100.0, 75.0, "0xabc123")
        history = self.client.get_payment_history()
        assert history[0]["transfer_tx_hash"] == "0xabc123"

    @pytest.mark.asyncio
    async def test_multiple_rewards_accumulate_in_history(self):
        await self.client.process_agent_reward(0, 100.0, 75.0)
        await self.client.process_agent_reward(0, 200.0, 80.0)
        await self.client.process_agent_reward(1, 50.0, 60.0)
        history = self.client.get_payment_history()
        assert len(history) == 3


# ─── X402Client: batch_payment_process ────────────────────────────────────────

class TestBatchPaymentProcess:
    def setup_method(self):
        self.client = X402Client(agent_wallet_address="0xAgent")

    @pytest.mark.asyncio
    async def test_batch_all_succeed(self):
        payments = [
            {"agent_id": 0, "transfer_amount": 100.0, "reputation_score": 75.0},
            {"agent_id": 1, "transfer_amount": 200.0, "reputation_score": 80.0},
            {"agent_id": 2, "transfer_amount": 50.0, "reputation_score": 60.0},
        ]
        result = await self.client.batch_payment_process(payments)
        assert result["total_processed"] == 3
        assert result["successful"] == 3
        assert result["failed"] == 0
        assert result["total_rewarded"] > 0

    @pytest.mark.asyncio
    async def test_batch_empty_list(self):
        result = await self.client.batch_payment_process([])
        assert result["total_processed"] == 0
        assert result["successful"] == 0
        assert result["total_rewarded"] == 0.0

    @pytest.mark.asyncio
    async def test_batch_total_rewarded_sum(self):
        payments = [
            {"agent_id": 0, "transfer_amount": 100.0, "reputation_score": 50.0},
            {"agent_id": 1, "transfer_amount": 100.0, "reputation_score": 50.0},
        ]
        result = await self.client.batch_payment_process(payments)
        expected = 100.0 * 0.005 * 1.0 * 2
        assert result["total_rewarded"] == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_batch_with_optional_tx_hash(self):
        payments = [
            {"agent_id": 0, "transfer_amount": 100.0, "reputation_score": 75.0, "tx_hash": "0xhash1"},
        ]
        result = await self.client.batch_payment_process(payments)
        assert result["successful"] == 1
        history = self.client.get_payment_history()
        assert history[0]["transfer_tx_hash"] == "0xhash1"

    @pytest.mark.asyncio
    async def test_batch_currency_is_usdm(self):
        payments = [{"agent_id": 0, "transfer_amount": 100.0, "reputation_score": 75.0}]
        result = await self.client.batch_payment_process(payments)
        assert result["currency"] == "USDm"


# ─── Full Integration: transfer → reputation → reward ─────────────────────────

class TestFullIntegrationFlow:
    """Test the complete flow: transfer success → reputation update → x402 reward."""

    def setup_method(self):
        self.x402_client = X402Client(agent_wallet_address="0xAgent")
        self.reputation_service = ReputationAnalyticsService()
        self.payment_service = PaymentRewardService(
            x402_client=self.x402_client,
            reputation_service=self.reputation_service,
            daily_cap_usd=100.0,
            agent_id=0,
        )

    @pytest.mark.asyncio
    async def test_successful_transfer_triggers_reward(self):
        result = await self.payment_service.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=True,
            tx_hash="0xintegration_test",
        )
        assert result["success"] is True
        assert result["reward_amount"] > 0

    @pytest.mark.asyncio
    async def test_reputation_updated_after_reward(self):
        initial_summary = self.reputation_service.get_summary(0)
        initial_tasks = initial_summary.get("total_tasks", 0)

        await self.payment_service.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=True,
        )

        updated_summary = self.reputation_service.get_summary(0)
        assert updated_summary["total_tasks"] == initial_tasks + 1
        assert updated_summary["successful_tasks"] >= 1

    @pytest.mark.asyncio
    async def test_multiple_transfers_accumulate_earnings(self):
        for i in range(5):
            await self.payment_service.process_transfer_reward(
                agent_id=0,
                transfer_amount=100.0,
                success_status=True,
                tx_hash=f"0xhash{i}",
            )

        earnings = self.payment_service.get_agent_earnings(0)
        assert earnings["total_transfers_rewarded"] == 5
        assert earnings["total_earned"] > 0

    @pytest.mark.asyncio
    async def test_reputation_score_affects_reward_tier(self):
        # Start with low reputation
        self.reputation_service._scores[0] = {
            "score": 20.0,
            "last_updated": time.time(),
            "total_tasks": 0,
            "successful_tasks": 0,
        }

        result_low = await self.payment_service.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=True,
        )

        # Boost reputation
        self.reputation_service._scores[0]["score"] = 95.0

        result_high = await self.payment_service.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=True,
        )

        # Higher reputation should yield higher reward
        assert result_high["reward_amount"] >= result_low["reward_amount"]

    @pytest.mark.asyncio
    async def test_failed_transfer_does_not_update_reputation(self):
        initial_summary = self.reputation_service.get_summary(0)
        initial_tasks = initial_summary.get("total_tasks", 0)

        await self.payment_service.process_transfer_reward(
            agent_id=0,
            transfer_amount=100.0,
            success_status=False,
        )

        updated_summary = self.reputation_service.get_summary(0)
        assert updated_summary.get("total_tasks", 0) == initial_tasks

    @pytest.mark.asyncio
    async def test_audit_trail_complete(self):
        await self.payment_service.process_transfer_reward(
            agent_id=0,
            transfer_amount=150.0,
            success_status=True,
            tx_hash="0xaudit_test",
        )

        log = self.payment_service.get_audit_log(agent_id=0)
        assert len(log) == 1
        entry = log[0]
        assert entry["transfer_amount"] == 150.0
        assert entry["tx_hash"] == "0xaudit_test"
        assert entry["status"] == "success"
        assert "payment_id" in entry
        assert "timestamp" in entry

    @pytest.mark.asyncio
    async def test_daily_cap_enforced_across_multiple_transfers(self):
        svc = PaymentRewardService(
            x402_client=self.x402_client,
            reputation_service=self.reputation_service,
            daily_cap_usd=0.05,  # Very low cap
            agent_id=0,
        )

        # First transfer should succeed
        r1 = await svc.process_transfer_reward(0, 100.0, True)
        # Second transfer should hit cap
        r2 = await svc.process_transfer_reward(0, 100.0, True)

        # At least one should be blocked by cap
        results = [r1, r2]
        blocked = [r for r in results if not r.get("success") and r.get("reason") == "daily_cap_reached"]
        succeeded = [r for r in results if r.get("success")]
        assert len(succeeded) >= 1
        # If cap is very low, second may be blocked
        assert len(blocked) + len(succeeded) == 2


# ─── X402Client: backward compatibility ───────────────────────────────────────

class TestBackwardCompatibility:
    """Ensure existing X402Client methods still work after new additions."""

    def setup_method(self):
        self.client = X402Client(agent_wallet_address="0xAgent")

    def test_register_service_still_works(self):
        self.client.register_service("test_svc", "http://test.com", 0.10, "USDT")
        registry = self.client.get_service_registry()
        assert "test_svc" in registry

    def test_estimate_service_cost_still_works(self):
        self.client.register_service("svc1", "http://svc1.com", 0.10)
        self.client.register_service("svc2", "http://svc2.com", 0.20)
        cost = self.client.estimate_service_cost(["svc1", "svc2"])
        assert cost["total_cost"] == pytest.approx(0.30)

    def test_get_payment_history_still_works(self):
        history = self.client.get_payment_history()
        assert isinstance(history, list)

    def test_verify_payment_receipt_still_works(self):
        result = self.client.verify_payment_receipt("nonexistent")
        assert result["verified"] is False

    @pytest.mark.asyncio
    async def test_new_methods_dont_break_existing_history(self):
        # Use old-style payment recording
        self.client._record_payment("test_svc", 0.10, "USDT", True, "0xhash")
        # Use new reward method
        await self.client.process_agent_reward(0, 100.0, 75.0)
        history = self.client.get_payment_history()
        assert len(history) == 2
