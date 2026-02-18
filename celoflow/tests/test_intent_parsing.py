"""Tests for IntentParsingService — multi-language NL → structured intent."""

from __future__ import annotations

import pytest

from services.intent_parsing_service import IntentParsingService


@pytest.fixture
def service() -> IntentParsingService:
    return IntentParsingService()


# ── Amount + Currency Extraction ──────────────────────────────────


class TestAmountCurrencyExtraction:
    def test_dollar_sign_amount(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $50 to Maria")
        assert intent["amount"] == 50.0
        assert intent["currency"] == "USDm"

    def test_euro_sign_amount(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send €100 to Jean")
        assert intent["amount"] == 100.0
        assert intent["currency"] == "EURm"

    def test_pound_sign_amount(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send £75 to James")
        assert intent["amount"] == 75.0
        assert intent["currency"] == "GBPm"

    def test_real_sign_amount(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send R$200 to Carlos")
        assert intent["amount"] == 200.0
        assert intent["currency"] == "BRLm"

    def test_peso_sign_amount(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send ₱500 to Maria")
        assert intent["amount"] == 500.0
        assert intent["currency"] == "PHPm"

    def test_amount_with_currency_text(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send 100 dollars to John")
        assert intent["amount"] == 100.0
        assert intent["currency"] == "USDm"

    def test_amount_with_token_symbol(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send 50 BRLm to Carlos")
        assert intent["amount"] == 50.0

    def test_amount_with_commas(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Transfer $1,500 to Maria")
        assert intent["amount"] == 1500.0

    def test_amount_with_decimals(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $99.50 to John")
        assert intent["amount"] == 99.5

    def test_no_amount(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send money to Maria")
        assert intent["amount"] is None
        assert "amount" in intent["missing_fields"]


# ── Currency Resolution ───────────────────────────────────────────


class TestCurrencyResolution:
    def test_alias_usd(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send 100 USD to John")
        assert intent["currency"] == "USDm"

    def test_alias_naira(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send 5000 naira to Chidi")
        assert intent["currency"] == "NGNm"

    def test_alias_yen(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send 10000 yen to Yuki")
        assert intent["currency"] == "JPYm"

    def test_alias_celo(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send 5 CELO to Bob")
        assert intent["currency"] == "CELO"

    def test_country_fallback_philippines(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send 100 to my mom in the philippines")
        assert intent["destination_country"] == "philippines"
        # Currency resolved from country
        assert intent["currency"] == "PHPm"

    def test_country_fallback_nigeria(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Transfer money to nigeria")
        assert intent["destination_country"] == "nigeria"


# ── Recipient Extraction ──────────────────────────────────────────


class TestRecipientExtraction:
    def test_wallet_address(self, service: IntentParsingService) -> None:
        addr = "0x1234567890abcdef1234567890abcdef12345678"
        intent = service.parse_intent(f"Send $50 to {addr}")
        assert intent["recipient"] == addr

    def test_name_after_to(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $50 to Maria")
        assert intent["recipient"] == "Maria"

    def test_name_after_para(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Enviar $50 para Carlos")
        assert intent["recipient"] == "Carlos"

    def test_relationship_keyword(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $100 to my mom")
        assert intent["recipient"] == "mom"
        assert intent["relationship"] == "mother"


# ── Frequency / Recurring ─────────────────────────────────────────


class TestFrequencyExtraction:
    def test_daily_english(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $50 daily to Maria")
        assert intent["frequency"] == "daily"
        assert intent["intent_type"] == "recurring_transfer"

    def test_weekly_english(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $100 weekly to John")
        assert intent["frequency"] == "weekly"

    def test_monthly_english(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $200 monthly to Carlos")
        assert intent["frequency"] == "monthly"

    def test_mensual_spanish(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Enviar $200 mensual a Carlos")
        assert intent["frequency"] == "monthly"

    def test_no_frequency(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $50 to Maria")
        assert intent["frequency"] is None
        assert intent["intent_type"] == "single_transfer"


# ── Intent Classification ─────────────────────────────────────────


class TestIntentClassification:
    def test_single_transfer(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $50 to Maria")
        assert intent["intent_type"] == "single_transfer"

    def test_recurring_transfer(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $50 weekly to Maria")
        assert intent["intent_type"] == "recurring_transfer"

    def test_currency_swap(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Swap 100 USD to PHP")
        assert intent["intent_type"] == "currency_swap"

    def test_balance_check(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("What is my balance?")
        assert intent["intent_type"] == "balance_check"

    def test_rate_check(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("What is the exchange rate for USD to PHP?")
        assert intent["intent_type"] == "rate_check"

    def test_fee_check(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("How much are the fees?")
        assert intent["intent_type"] == "fee_check"

    def test_general_query(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Hello, how are you?")
        assert intent["intent_type"] == "general_query"


# ── Confidence Scoring ────────────────────────────────────────────


class TestConfidenceScoring:
    def test_full_intent_high_confidence(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $50 USD to Maria")
        assert intent["confidence"] >= 0.8

    def test_partial_intent_medium_confidence(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $50 to someone")
        # Has amount but recipient is vague
        assert 0.3 <= intent["confidence"] <= 0.8

    def test_empty_input_zero_confidence(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("")
        assert intent["confidence"] == 0.0

    def test_balance_check_high_confidence(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Check my balance")
        assert intent["confidence"] == 0.8


# ── Missing Fields / Clarification ────────────────────────────────


class TestClarification:
    def test_missing_amount(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send money to Maria")
        assert intent["needs_clarification"] is True
        assert "amount" in intent["missing_fields"]

    def test_missing_recipient(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $50")
        assert "recipient" in intent["missing_fields"]

    def test_no_missing_for_balance_check(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("What is my balance?")
        assert intent["needs_clarification"] is False
        assert intent["missing_fields"] == []

    def test_generate_clarification_prompt(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send money")
        prompt = service.generate_clarification(intent)
        assert "How much" in prompt


# ── Validation ────────────────────────────────────────────────────


class TestValidation:
    def test_valid_intent(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $50 USD to Maria")
        result = service.validate_intent(intent)
        assert result["is_valid"] is True

    def test_invalid_no_amount(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send money to Maria")
        result = service.validate_intent(intent)
        assert result["is_valid"] is False
        assert any("amount" in i.lower() for i in result["issues"])

    def test_invalid_exceeds_limit(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Send $200000 to Maria")
        result = service.validate_intent(intent)
        assert result["is_valid"] is False
        assert any("maximum" in i.lower() for i in result["issues"])


# ── Multi-Language ────────────────────────────────────────────────


class TestMultiLanguage:
    def test_spanish_enviar(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Enviar $100 a Carlos en Colombia")
        assert intent["amount"] == 100.0
        assert intent["recipient"] == "Carlos"
        assert intent["destination_country"] == "colombia"

    def test_portuguese_enviar(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Enviar R$200 para Maria")
        assert intent["amount"] == 200.0
        assert intent["currency"] == "BRLm"
        assert intent["recipient"] == "Maria"

    def test_french_envoyer(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Envoyer €50 à Jean en France")
        assert intent["amount"] == 50.0
        assert intent["currency"] == "EURm"

    def test_swahili_tuma(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Tuma 1000 kwa Kenya")
        assert intent["amount"] == 1000.0
        assert intent["destination_country"] == "kenya"

    def test_filipino_magpadala(self, service: IntentParsingService) -> None:
        intent = service.parse_intent("Magpadala ₱500 kay Maria")
        assert intent["amount"] == 500.0
        assert intent["currency"] == "PHPm"
        assert intent["recipient"] == "Maria"
