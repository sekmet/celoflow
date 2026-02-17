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


# ── KYCPlugin Tests ──────────────────────────────────────────────


class TestKYCPlugin:
    """Tests for the KYC plugin."""

    @pytest.mark.asyncio
    async def test_verify_kyc_basic(self):
        from plugins.kyc_plugin import KYCPlugin

        plugin = KYCPlugin()
        result = await plugin.verify_kyc("user1", "basic")
        assert result["status"] == "verified"
        assert result["level"] == "basic"

    @pytest.mark.asyncio
    async def test_verify_kyc_invalid_level(self):
        from plugins.kyc_plugin import KYCPlugin

        plugin = KYCPlugin()
        result = await plugin.verify_kyc("user1", "invalid_level")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_verify_kyc_none_level_rejected(self):
        from plugins.kyc_plugin import KYCPlugin

        plugin = KYCPlugin()
        result = await plugin.verify_kyc("user1", "none")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_status_unverified(self):
        from plugins.kyc_plugin import KYCPlugin

        plugin = KYCPlugin()
        result = await plugin.get_status("unknown_user")
        assert result["level"] == "none"
        assert result["status"] == "unverified"

    @pytest.mark.asyncio
    async def test_get_status_after_verification(self):
        from plugins.kyc_plugin import KYCPlugin

        plugin = KYCPlugin()
        await plugin.verify_kyc("user1", "standard")
        result = await plugin.get_status("user1")
        assert result["level"] == "standard"
        assert result["status"] == "verified"

    def test_get_level_requirements(self):
        from plugins.kyc_plugin import KYCPlugin

        plugin = KYCPlugin()
        result = plugin.get_level_requirements("enhanced")
        assert result["level"] == "enhanced"
        assert result["max_single_transfer"] == 100_000.0
        assert "proof_of_address" in result["required_documents"]

    def test_get_level_requirements_unknown(self):
        from plugins.kyc_plugin import KYCPlugin

        plugin = KYCPlugin()
        result = plugin.get_level_requirements("super_vip")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_transfer_eligibility_within_limit(self):
        from plugins.kyc_plugin import KYCPlugin

        plugin = KYCPlugin()
        await plugin.verify_kyc("user1", "basic")
        result = await plugin.check_transfer_eligibility("user1", 500.0)
        assert result["eligible"] is True

    @pytest.mark.asyncio
    async def test_transfer_eligibility_exceeds_limit(self):
        from plugins.kyc_plugin import KYCPlugin

        plugin = KYCPlugin()
        await plugin.verify_kyc("user1", "basic")
        result = await plugin.check_transfer_eligibility("user1", 5000.0)
        assert result["eligible"] is False
        assert "suggested_upgrade" in result

    @pytest.mark.asyncio
    async def test_credential_caching(self):
        from plugins.kyc_plugin import KYCPlugin

        plugin = KYCPlugin()
        await plugin.verify_kyc("user1", "standard")
        # Second call should use cache
        result = await plugin.verify_kyc("user1", "basic")
        assert result["status"] == "verified"
        assert result.get("cached") is True

    @pytest.mark.asyncio
    async def test_level_upgrade(self):
        from plugins.kyc_plugin import KYCPlugin

        plugin = KYCPlugin()
        await plugin.verify_kyc("user1", "basic")
        result = await plugin.verify_kyc("user1", "enhanced")
        assert result["status"] == "verified"
        assert result["level"] == "enhanced"


# ── ComplianceAgentPlugin Tests ──────────────────────────────────


class TestComplianceAgentPlugin:
    """Tests for the Compliance Agent plugin."""

    @pytest.mark.asyncio
    async def test_screen_clear_address(self):
        from plugins.compliance_agent_plugin import ComplianceAgentPlugin

        plugin = ComplianceAgentPlugin()
        result = await plugin.screen_address(
            "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "Philippines",
            100.0,
        )
        assert result["status"] == "clear"
        assert result["risk_score"] < 70

    @pytest.mark.asyncio
    async def test_screen_high_risk_jurisdiction(self):
        from plugins.compliance_agent_plugin import ComplianceAgentPlugin

        plugin = ComplianceAgentPlugin()
        result = await plugin.screen_address(
            "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "North Korea",
            100.0,
        )
        assert result["status"] == "flagged"
        assert result["risk_score"] >= 70

    @pytest.mark.asyncio
    async def test_screen_suspicious_address(self):
        from plugins.compliance_agent_plugin import ComplianceAgentPlugin

        plugin = ComplianceAgentPlugin()
        result = await plugin.screen_address(
            "0x0000000000000000000000000000000000000000",
            "Philippines",
            100.0,
        )
        assert len(result["flags"]) > 0

    @pytest.mark.asyncio
    async def test_screening_caching(self):
        from plugins.compliance_agent_plugin import ComplianceAgentPlugin

        plugin = ComplianceAgentPlugin(enable_caching=True)
        await plugin.screen_address("0xabc123", "Mexico", 50.0)
        result = await plugin.screen_address("0xabc123", "Mexico", 50.0)
        assert result.get("cached") is True

    @pytest.mark.asyncio
    async def test_pre_transfer_check_approved(self):
        from plugins.compliance_agent_plugin import ComplianceAgentPlugin

        plugin = ComplianceAgentPlugin()
        result = await plugin.check_pre_transfer(
            "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "Philippines",
            100.0,
        )
        assert result["approved"] is True

    @pytest.mark.asyncio
    async def test_pre_transfer_check_flagged(self):
        from plugins.compliance_agent_plugin import ComplianceAgentPlugin

        plugin = ComplianceAgentPlugin()
        result = await plugin.check_pre_transfer(
            "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "Iran",
            100.0,
        )
        assert result["approved"] is False

    def test_audit_trail(self):
        from plugins.compliance_agent_plugin import ComplianceAgentPlugin

        plugin = ComplianceAgentPlugin()
        trail = plugin.get_audit_trail()
        assert isinstance(trail, list)

    def test_get_cached_report_not_found(self):
        from plugins.compliance_agent_plugin import ComplianceAgentPlugin

        plugin = ComplianceAgentPlugin()
        result = plugin.get_cached_report("0xnonexistent")
        assert result["status"] == "not_screened"


# ── FeeComparisonService Tests ───────────────────────────────────


class TestFeeComparisonService:
    """Tests for the Fee Comparison Service."""

    @pytest.mark.asyncio
    async def test_compare_fees_basic(self):
        from services.fee_comparison_service import FeeComparisonService

        service = FeeComparisonService()
        result = await service.compare_fees(100.0, "USD", "Philippines")
        assert "comparisons" in result
        assert len(result["comparisons"]) >= 5  # CeloFlow + 4 traditional
        assert result["comparisons"][0]["provider"] is not None

    @pytest.mark.asyncio
    async def test_celoflow_is_cheapest(self):
        from services.fee_comparison_service import FeeComparisonService

        service = FeeComparisonService()
        result = await service.compare_fees(500.0, "USD", "Nigeria")
        # CeloFlow should rank #1 for most corridors
        assert result["celoflow_rank"] == 1

    @pytest.mark.asyncio
    async def test_savings_calculated(self):
        from services.fee_comparison_service import FeeComparisonService

        service = FeeComparisonService()
        result = await service.compare_fees(1000.0, "USD", "Mexico")
        assert result["savings_vs_most_expensive"] > 0

    @pytest.mark.asyncio
    async def test_fee_caching(self):
        from services.fee_comparison_service import FeeComparisonService

        service = FeeComparisonService()
        await service.compare_fees(200.0, "USD", "Kenya")
        # Second call should use cache
        result = await service.compare_fees(200.0, "USD", "Kenya")
        assert "comparisons" in result

    def test_get_provider_details(self):
        from services.fee_comparison_service import FeeComparisonService

        service = FeeComparisonService()
        result = service.get_provider_details("wise")
        assert result["name"] == "Wise (TransferWise)"
        assert "Philippines" in result["supported_corridors"]

    def test_get_provider_details_unknown(self):
        from services.fee_comparison_service import FeeComparisonService

        service = FeeComparisonService()
        result = service.get_provider_details("unknown_provider")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_fee_optimization(self):
        from services.fee_comparison_service import FeeComparisonService

        service = FeeComparisonService()
        result = await service.get_fee_optimization(500.0, "USD", "Philippines")
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_recommendation_text(self):
        from services.fee_comparison_service import FeeComparisonService

        service = FeeComparisonService()
        result = await service.compare_fees(100.0, "USD", "India")
        assert "recommendation" in result
        assert len(result["recommendation"]) > 0


# ── LanguageDetectionService Tests ───────────────────────────────


class TestLanguageDetectionService:
    """Tests for the Language Detection Service."""

    def test_detect_english_default(self):
        from services.language_detection import LanguageDetectionService

        service = LanguageDetectionService()
        result = service.detect_language("Hello, how are you?")
        assert result["language"] == "en"

    def test_detect_spanish(self):
        from services.language_detection import LanguageDetectionService

        service = LanguageDetectionService()
        result = service.detect_language("Hola, quiero enviar dinero por favor")
        assert result["language"] == "es"

    def test_detect_portuguese(self):
        from services.language_detection import LanguageDetectionService

        service = LanguageDetectionService()
        result = service.detect_language("Olá, quero enviar dinheiro por favor não")
        assert result["language"] == "pt"

    def test_detect_french(self):
        from services.language_detection import LanguageDetectionService

        service = LanguageDetectionService()
        result = service.detect_language("Bonjour, je veux envoyer de l'argent dans les")
        assert result["language"] == "fr"

    def test_detect_swahili(self):
        from services.language_detection import LanguageDetectionService

        service = LanguageDetectionService()
        result = service.detect_language("Habari, nataka tuma pesa tafadhali")
        assert result["language"] == "sw"

    def test_detect_empty_string(self):
        from services.language_detection import LanguageDetectionService

        service = LanguageDetectionService()
        result = service.detect_language("")
        assert result["language"] == "en"
        assert result["confidence"] == 0.0

    def test_user_preference_storage(self):
        from services.language_detection import LanguageDetectionService

        service = LanguageDetectionService()
        service.set_user_language("user1", "es")
        assert service.get_user_language("user1") == "es"

    def test_detect_and_remember(self):
        from services.language_detection import LanguageDetectionService

        service = LanguageDetectionService()
        result = service.detect_and_remember("user1", "Hola quiero enviar dinero por favor")
        assert result["language"] == "es"
        assert service.get_user_language("user1") == "es"

    def test_supported_languages(self):
        from services.language_detection import LanguageDetectionService

        service = LanguageDetectionService()
        langs = service.get_supported_languages()
        assert "en" in langs
        assert "es" in langs
        assert "sw" in langs


# ── TranslationService Tests ────────────────────────────────────


class TestTranslationService:
    """Tests for the Translation Service."""

    @pytest.mark.asyncio
    async def test_translate_common_phrase(self):
        from services.translation_service import TranslationService

        service = TranslationService()
        result = await service.translate("Transaction successful!", "es")
        assert result["text"] == "¡Transacción exitosa!"
        assert result["method"] == "common_phrase"

    @pytest.mark.asyncio
    async def test_translate_passthrough_same_lang(self):
        from services.translation_service import TranslationService

        service = TranslationService()
        result = await service.translate("Hello world", "en")
        assert result["text"] == "Hello world"
        assert result["method"] == "passthrough"

    @pytest.mark.asyncio
    async def test_translate_term_substitution(self):
        from services.translation_service import TranslationService

        service = TranslationService()
        result = await service.translate("Check your wallet balance", "es")
        assert "billetera" in result["text"]
        assert "saldo" in result["text"]

    def test_translate_financial_term(self):
        from services.translation_service import TranslationService

        service = TranslationService()
        assert service.translate_financial_term("transfer", "es") == "transferencia"
        assert service.translate_financial_term("fee", "pt") == "taxa"
        assert service.translate_financial_term("wallet", "fr") == "portefeuille"

    def test_translate_financial_term_not_found(self):
        from services.translation_service import TranslationService

        service = TranslationService()
        assert service.translate_financial_term("nonexistent_term", "es") is None

    def test_get_supported_languages(self):
        from services.translation_service import TranslationService

        service = TranslationService()
        langs = service.get_supported_languages()
        assert len(langs) >= 6
        codes = [l["code"] for l in langs]
        assert "en" in codes
        assert "es" in codes

    def test_validate_translation_correct(self):
        from services.translation_service import TranslationService

        service = TranslationService()
        result = service.validate_translation(
            "Check your wallet balance",
            "Revisa tu billetera saldo",
            "es",
        )
        assert result["valid"] is True

    def test_validate_translation_missing_term(self):
        from services.translation_service import TranslationService

        service = TranslationService()
        result = service.validate_translation(
            "Check your wallet balance",
            "Revisa tu cuenta",
            "es",
        )
        assert result["valid"] is False
        assert len(result["issues"]) > 0

    @pytest.mark.asyncio
    async def test_translation_caching(self):
        from services.translation_service import TranslationService

        service = TranslationService()
        await service.translate("Check your wallet balance", "es")
        result = await service.translate("Check your wallet balance", "es")
        assert result["method"] == "cache"


# ── ReputationAnalyticsService Tests ─────────────────────────────


class TestReputationAnalyticsService:
    """Tests for the Reputation Analytics Service."""

    def test_record_event(self):
        from services.reputation_analytics import ReputationAnalyticsService

        service = ReputationAnalyticsService()
        result = service.record_event(1, "task_success", 5.0)
        assert result["agent_id"] == 1
        assert result["score"] == 55.0
        assert result["total_tasks"] == 1
        assert result["successful_tasks"] == 1

    def test_record_failure(self):
        from services.reputation_analytics import ReputationAnalyticsService

        service = ReputationAnalyticsService()
        result = service.record_event(1, "task_failure", -10.0)
        assert result["score"] == 40.0
        assert result["total_tasks"] == 1
        assert result["successful_tasks"] == 0

    def test_score_bounds(self):
        from services.reputation_analytics import ReputationAnalyticsService

        service = ReputationAnalyticsService()
        result = service.record_event(1, "task_success", 200.0)
        assert result["score"] == 100.0  # Capped at max

        result = service.record_event(2, "task_failure", -200.0)
        assert result["score"] == 0.0  # Capped at min

    def test_get_summary_unknown(self):
        from services.reputation_analytics import ReputationAnalyticsService

        service = ReputationAnalyticsService()
        result = service.get_summary(999)
        assert result["status"] == "unknown"

    def test_get_trend_insufficient_data(self):
        from services.reputation_analytics import ReputationAnalyticsService

        service = ReputationAnalyticsService()
        result = service.get_trend(1)
        assert result["direction"] == "stable"
        assert result["data_points"] == 0

    def test_get_trend_with_data(self):
        from services.reputation_analytics import ReputationAnalyticsService

        service = ReputationAnalyticsService()
        service.record_event(1, "task_success", 5.0)
        service.record_event(1, "task_success", 5.0)
        service.record_event(1, "task_success", 5.0)
        result = service.get_trend(1)
        assert result["direction"] == "improving"
        assert result["change"] > 0

    def test_select_best_agent(self):
        from services.reputation_analytics import ReputationAnalyticsService

        service = ReputationAnalyticsService()
        service.record_event(1, "task_success", 30.0)
        service.record_event(2, "task_success", 10.0)
        service.record_event(3, "task_failure", -30.0)

        best = service.select_best_agent([1, 2, 3], min_score=30.0)
        assert best is not None
        assert best["agent_id"] == 1

    def test_select_best_agent_none_eligible(self):
        from services.reputation_analytics import ReputationAnalyticsService

        service = ReputationAnalyticsService()
        service.record_event(1, "task_failure", -40.0)
        best = service.select_best_agent([1], min_score=50.0)
        assert best is None

    def test_pricing_modifier(self):
        from services.reputation_analytics import ReputationAnalyticsService

        service = ReputationAnalyticsService()
        service.record_event(1, "task_success", 45.0)  # score = 95
        modifier = service.get_pricing_modifier(1)
        assert modifier == 1.10  # Excellent reputation premium

    def test_detect_fraud_no_history(self):
        from services.reputation_analytics import ReputationAnalyticsService

        service = ReputationAnalyticsService()
        result = service.detect_fraud(999)
        assert result["suspicious"] is False

    def test_success_rate(self):
        from services.reputation_analytics import ReputationAnalyticsService

        service = ReputationAnalyticsService()
        service.record_event(1, "task_success", 5.0)
        service.record_event(1, "task_success", 5.0)
        service.record_event(1, "task_failure", -5.0)
        summary = service.get_summary(1)
        assert summary["success_rate"] == pytest.approx(66.7, abs=0.1)


# ── SelfProtocolClient Tests ────────────────────────────────────


class TestSelfProtocolClient:
    """Tests for the Self Protocol API client."""

    @pytest.mark.asyncio
    async def test_simulated_verification(self):
        from integrations.self_protocol import SelfProtocolClient

        client = SelfProtocolClient()
        assert client.is_configured is False
        result = await client.verify_identity("user1", "basic", ["selfie", "email"])
        assert result["verified"] is True
        assert result["status"] == "verified"
        assert len(result["attestation_hash"]) > 0

    @pytest.mark.asyncio
    async def test_simulated_status_check(self):
        from integrations.self_protocol import SelfProtocolClient

        client = SelfProtocolClient()
        result = await client.check_verification_status("sim_123")
        assert result["status"] == "verified"

    @pytest.mark.asyncio
    async def test_simulated_document_upload(self):
        from integrations.self_protocol import SelfProtocolClient

        client = SelfProtocolClient()
        result = await client.upload_document("user1", "selfie", b"fake_image_data")
        assert result["uploaded"] is True
        assert result["document_id"].startswith("sim_doc_")

    @pytest.mark.asyncio
    async def test_simulated_attestation(self):
        from integrations.self_protocol import SelfProtocolClient

        client = SelfProtocolClient()
        result = await client.get_attestation("user1")
        assert result["has_attestation"] is True
        assert len(result["attestation_hash"]) > 0

    def test_fee_estimate(self):
        from integrations.self_protocol import SelfProtocolClient

        client = SelfProtocolClient()
        result = client.get_fee_estimate("standard")
        assert result["fee_usdt"] == 2.50

    def test_fee_estimate_unknown_level(self):
        from integrations.self_protocol import SelfProtocolClient

        client = SelfProtocolClient()
        result = client.get_fee_estimate("vip")
        assert "error" in result
