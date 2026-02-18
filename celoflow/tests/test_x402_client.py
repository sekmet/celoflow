"""Tests for X402Client — agent-to-agent payment protocol."""

from __future__ import annotations

import pytest

from integrations.x402_client import X402Client


@pytest.fixture
def client() -> X402Client:
    return X402Client(
        agent_wallet_address="0x1234567890abcdef1234567890abcdef12345678",
        chain_id=44787,
    )


# ── Service Registration ──────────────────────────────────────────


class TestServiceRegistration:
    def test_register_service(self, client: X402Client) -> None:
        client.register_service(
            service_name="compliance",
            endpoint_url="https://compliance.example.com/screen",
            fee_amount=0.10,
            fee_currency="USDT",
            description="Compliance screening",
        )
        registry = client.get_service_registry()
        assert "compliance" in registry
        assert registry["compliance"]["fee"] == 0.10
        assert registry["compliance"]["currency"] == "USDT"

    def test_register_multiple_services(self, client: X402Client) -> None:
        client.register_service("svc1", "https://a.com", 0.05)
        client.register_service("svc2", "https://b.com", 0.15)
        registry = client.get_service_registry()
        assert len(registry) == 2

    def test_overwrite_service(self, client: X402Client) -> None:
        client.register_service("svc", "https://a.com", 0.05)
        client.register_service("svc", "https://b.com", 0.10)
        registry = client.get_service_registry()
        assert registry["svc"]["fee"] == 0.10
        assert registry["svc"]["url"] == "https://b.com"


# ── Cost Estimation ───────────────────────────────────────────────


class TestCostEstimation:
    def test_estimate_single_service(self, client: X402Client) -> None:
        client.register_service("svc1", "https://a.com", 0.10)
        estimate = client.estimate_service_cost(["svc1"])
        assert estimate["total_cost"] == 0.10
        assert len(estimate["services"]) == 1

    def test_estimate_multiple_services(self, client: X402Client) -> None:
        client.register_service("svc1", "https://a.com", 0.10)
        client.register_service("svc2", "https://b.com", 0.25)
        estimate = client.estimate_service_cost(["svc1", "svc2"])
        assert estimate["total_cost"] == 0.35

    def test_estimate_unknown_service(self, client: X402Client) -> None:
        estimate = client.estimate_service_cost(["nonexistent"])
        assert estimate["total_cost"] == 0.0
        assert estimate["services"][0].get("error") is not None

    def test_estimate_empty_list(self, client: X402Client) -> None:
        estimate = client.estimate_service_cost([])
        assert estimate["total_cost"] == 0.0


# ── Payment for Service ───────────────────────────────────────────


class TestPayForService:
    @pytest.mark.asyncio
    async def test_pay_unregistered_service(self, client: X402Client) -> None:
        result = await client.pay_for_service("nonexistent", {"data": "test"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_pay_registered_service_simulated(self, client: X402Client) -> None:
        client.register_service(
            "test_svc",
            "https://httpbin.org/status/503",  # Will fail, triggering simulation
            0.05,
        )
        result = await client.pay_for_service("test_svc", {"query": "test"})
        # Should get simulated success after retries
        assert result.get("success") is True
        assert result.get("simulated") is True

    @pytest.mark.asyncio
    async def test_custom_fee_override(self, client: X402Client) -> None:
        client.register_service("svc", "https://httpbin.org/status/503", 0.05)
        result = await client.pay_for_service("svc", {}, custom_fee=0.99)
        assert result.get("fee_paid") == 0.99


# ── Compliance Agent Call ─────────────────────────────────────────


class TestComplianceAgentCall:
    @pytest.mark.asyncio
    async def test_call_compliance_agent_simulated(self, client: X402Client) -> None:
        result = await client.call_compliance_agent(
            agent_url="https://httpbin.org/status/503",
            recipient_address="0xabcdef1234567890abcdef1234567890abcdef12",
            destination_country="Philippines",
            amount=100.0,
            fee=0.10,
        )
        # Simulated success after retries
        assert result.get("success") is True


# ── Payment Receipt ───────────────────────────────────────────────


class TestPaymentReceipt:
    def test_verify_nonexistent_receipt(self, client: X402Client) -> None:
        result = client.verify_payment_receipt("nonexistent_id")
        assert result["verified"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_receipt_cached_after_payment(self, client: X402Client) -> None:
        client.register_service("svc", "https://httpbin.org/status/503", 0.05)
        pay_result = await client.pay_for_service("svc", {})
        receipt_id = pay_result.get("receipt_id")
        if receipt_id:
            verify = client.verify_payment_receipt(receipt_id)
            assert verify["verified"] is True


# ── Payment History ───────────────────────────────────────────────


class TestPaymentHistory:
    def test_empty_history(self, client: X402Client) -> None:
        history = client.get_payment_history()
        assert history == []

    @pytest.mark.asyncio
    async def test_history_recorded_after_payment(self, client: X402Client) -> None:
        client.register_service("svc", "https://httpbin.org/status/503", 0.05)
        await client.pay_for_service("svc", {})
        history = client.get_payment_history()
        assert len(history) == 1
        assert history[0]["service"] == "svc"
        assert history[0]["fee"] == 0.05

    @pytest.mark.asyncio
    async def test_history_limit(self, client: X402Client) -> None:
        client.register_service("svc", "https://httpbin.org/status/503", 0.01)
        for _ in range(5):
            await client.pay_for_service("svc", {})
        history = client.get_payment_history(limit=3)
        assert len(history) == 3


# ── Build Payment Data ────────────────────────────────────────────


class TestBuildPaymentData:
    def test_payment_data_structure(self, client: X402Client) -> None:
        data = client._build_payment_data(0.10, "USDT")
        assert "payment_id" in data
        assert data["payer"] == "0x1234567890abcdef1234567890abcdef12345678"
        assert data["amount"] == "0.1"
        assert data["currency"] == "USDT"
        assert data["chain_id"] == 44787

    def test_payment_id_uniqueness(self, client: X402Client) -> None:
        data1 = client._build_payment_data(0.10, "USDT")
        data2 = client._build_payment_data(0.10, "USDT")
        # IDs should differ due to timestamp
        assert data1["payment_id"] != data2["payment_id"]

    def test_no_wallet_address(self) -> None:
        client = X402Client()
        data = client._build_payment_data(0.05, "USDT")
        assert data["payer"] == "0x0000000000000000000000000000000000000000"
