"""Tests for CeloFlow plugins and tools."""

from __future__ import annotations

import json
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch


# ── TEEPlugin Tests ──────────────────────────────────────────────


class TestTEEPlugin:
    """Tests for the TEE plugin in dev mode (no actual TEE)."""

    def test_ephemeral_key(self):
        from plugins.tee_plugin import TEEPlugin

        plugin = TEEPlugin(use_tee=False)
        assert plugin.address is not None
        assert plugin.address.startswith("0x")
        assert plugin.account is not None

    def test_private_key_mode(self):
        from plugins.tee_plugin import TEEPlugin

        # Anvil account #0
        key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        plugin = TEEPlugin(private_key=key, use_tee=False)
        assert plugin.address == "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

    def test_get_account(self):
        from plugins.tee_plugin import TEEPlugin

        key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        plugin = TEEPlugin(private_key=key, use_tee=False)
        account = plugin.get_account()
        assert account.address == "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

    @pytest.mark.asyncio
    async def test_get_attestation_dev_mode(self):
        from plugins.tee_plugin import TEEPlugin

        plugin = TEEPlugin(use_tee=False)
        result = await plugin.get_attestation()
        assert result["mode"] == "development"
        assert result["address"] is not None

    @pytest.mark.asyncio
    async def test_sign_message(self):
        from plugins.tee_plugin import TEEPlugin

        key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        plugin = TEEPlugin(private_key=key, use_tee=False)
        result = await plugin.sign_message("hello world")
        assert "signature" in result
        assert result["signer"] == "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


# ── RemittancePlugin Tests ───────────────────────────────────────


class TestRemittancePlugin:
    """Tests for the Remittance plugin."""

    def test_record_transaction(self):
        from plugins.remittance_plugin import RemittancePlugin

        plugin = RemittancePlugin()
        plugin.record_transaction(
            tx_hash="0xabc",
            user_id="user1",
            amount=Decimal("100"),
            from_currency="cUSD",
            to_currency="PHPm",
            destination="Philippines",
            fees={"total": 0.6},
        )
        assert "0xabc" in plugin.transactions
        assert plugin.transactions["0xabc"]["user_id"] == "user1"

    def test_calculate_savings(self):
        from plugins.remittance_plugin import RemittancePlugin

        plugin = RemittancePlugin()
        result = plugin.calculate_savings(
            amount=Decimal("100"),
            destination="Nigeria",
            crypto_fee=0.6,
        )
        assert result["savings"] > 0
        assert result["crypto_fee"] == 0.6
        assert "traditional_fee" in result

    def test_get_user_transactions(self):
        from plugins.remittance_plugin import RemittancePlugin

        plugin = RemittancePlugin()
        plugin.record_transaction(
            tx_hash="0x1",
            user_id="alice",
            amount=Decimal("50"),
            from_currency="cUSD",
            to_currency="PHPm",
            destination="Philippines",
            fees={"total": 0.3},
        )
        plugin.record_transaction(
            tx_hash="0x2",
            user_id="bob",
            amount=Decimal("75"),
            from_currency="cUSD",
            to_currency="XOFm",
            destination="West Africa",
            fees={"total": 0.45},
        )
        alice_txs = plugin.get_user_transactions("alice")
        assert len(alice_txs) == 1
        assert alice_txs[0]["tx_hash"] == "0x1"


# ── CompliancePlugin Tests ───────────────────────────────────────


class TestCompliancePlugin:
    """Tests for the Compliance plugin."""

    @pytest.mark.asyncio
    async def test_approved_transfer(self):
        from plugins.compliance_plugin import CompliancePlugin

        plugin = CompliancePlugin(max_single_transfer=10000)
        result = await plugin.check_compliance(
            amount=100.0,
            destination="Nigeria",
            user_id="user1",
        )
        assert result["approved"] is True

    @pytest.mark.asyncio
    async def test_exceeds_single_limit(self):
        from plugins.compliance_plugin import CompliancePlugin

        plugin = CompliancePlugin(max_single_transfer=500)
        result = await plugin.check_compliance(
            amount=1000.0,
            destination="Nigeria",
            user_id="user1",
        )
        assert result["approved"] is False
        assert any("single-transfer" in i for i in result["issues"])

    @pytest.mark.asyncio
    async def test_exceeds_corridor_limit(self):
        from plugins.compliance_plugin import CompliancePlugin

        plugin = CompliancePlugin(max_single_transfer=100000)
        result = await plugin.check_compliance(
            amount=6000.0,
            destination="Nigeria",
            user_id="user1",
        )
        assert result["approved"] is False
        assert any("corridor" in i for i in result["issues"])


# ── MentoPlugin Tests ────────────────────────────────────────────


class TestMentoPlugin:
    """Tests for the Mento plugin (broker-based, Mento v2)."""

    @pytest.mark.asyncio
    async def test_no_rpc_returns_not_connected(self):
        """Without RPC, find_optimal_route should return found=False with error."""
        from plugins.mento_plugin import MentoPlugin

        plugin = MentoPlugin(rpc_url=None)
        route = await plugin.find_optimal_route("cUSD", "PHPm", Decimal("10"))
        assert route["found"] is False
        assert "not connected" in route.get("error", "").lower() or "rpc" in route.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_find_route_unsupported_pair(self):
        """Unsupported pair should return found=False."""
        from plugins.mento_plugin import MentoPlugin

        plugin = MentoPlugin(rpc_url=None)
        route = await plugin.find_optimal_route("FAKE", "COIN", Decimal("100"))
        assert route["found"] is False

    @pytest.mark.asyncio
    async def test_execute_swap_no_broker_returns_stub(self):
        """Without broker, execute_swap should return a stub tx hash."""
        from plugins.mento_plugin import MentoPlugin

        plugin = MentoPlugin(rpc_url=None)
        route = {
            "exchange_id": "7952984d7278ca3417febf52815c321984ac3147ced2c02bb6a02b0bcab08413",
            "token_in": "0xdE9e4C3ce781b4bA68120d6261cbad65ce0aB00b",
            "token_out": "0x0352976d940a2C3FBa0C3623198947Ee1d17869E",
            "amount_in_wei": 10000000000000000000,
            "amount_out_wei": 5650000000000000000000,
            "amount": "10",
            "from_currency": "cUSD",
            "to_currency": "PHPm",
        }
        tx_hash = await plugin.execute_swap(route, "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb", MagicMock())
        assert tx_hash.startswith("0x")

    @pytest.mark.asyncio
    async def test_get_balances_no_rpc(self):
        """Without RPC, get_balances returns empty dict."""
        from plugins.mento_plugin import MentoPlugin

        plugin = MentoPlugin(rpc_url=None)
        balances = await plugin.get_balances("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        assert balances == {}

    @pytest.mark.asyncio
    async def test_get_amount_out_no_broker(self):
        """Without broker, get_amount_out returns 0."""
        from plugins.mento_plugin import MentoPlugin

        plugin = MentoPlugin(rpc_url=None)
        result = await plugin.get_amount_out(
            token_in="0xdE9e4C3ce781b4bA68120d6261cbad65ce0aB00b",
            token_out="0x0352976d940a2C3FBa0C3623198947Ee1d17869E",
            amount_in=10000000000000000000,
            exchange_id_hex="7952984d7278ca3417febf52815c321984ac3147ced2c02bb6a02b0bcab08413",
        )
        assert result == 0


# ── ChainConfig Tests ────────────────────────────────────────────


class TestChainConfig:
    """Tests for chain configuration."""

    def test_celo_mainnet(self):
        from integrations.chain_config import ChainConfig

        config = ChainConfig.celo_mainnet()
        assert config.chain_id == 42220
        assert "cUSD" in config.token_addresses

    def test_celo_sepolia(self):
        from integrations.chain_config import ChainConfig

        config = ChainConfig.celo_sepolia()
        assert config.chain_id == 11142220
        assert config.is_testnet is True
        assert "USDm" in config.token_addresses
        assert "PHPm" in config.token_addresses

    def test_anvil_local(self):
        from integrations.chain_config import ChainConfig

        config = ChainConfig.anvil_local()
        assert config.chain_id == 31337


# ── Remittance Tools Tests ───────────────────────────────────────


class TestRemittanceTools:
    """Tests for remittance tools using mocked plugins."""

    @pytest.mark.asyncio
    async def test_find_optimal_route_no_rpc(self):
        """Without RPC, the tool should return an error."""
        from tools import remittance_tools
        from plugins.mento_plugin import MentoPlugin

        mento = MentoPlugin(rpc_url=None)
        remittance_tools.set_plugins(mento=mento)
        result_str = await remittance_tools.find_optimal_route.on_invoke_tool(
            None,
            '{"from_currency": "FAKE", "to_currency": "COIN", "amount": 100.0}',
        )
        result = json.loads(result_str)
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_get_wallet_balance_no_rpc(self):
        from tools import remittance_tools
        from plugins.mento_plugin import MentoPlugin

        mento = MentoPlugin(rpc_url=None)
        remittance_tools.set_plugins(mento=mento)
        result_str = await remittance_tools.get_wallet_balance.on_invoke_tool(
            None,
            '{"wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"}',
        )
        result = json.loads(result_str)
        assert "balances" in result
