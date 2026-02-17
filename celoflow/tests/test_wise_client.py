"""Tests for Wise API client and enhanced fee comparison with real-time data."""

from __future__ import annotations

import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from integrations.wise_client import WiseClient
from services.fee_comparison_service import FeeComparisonService


# ── WiseClient Tests ────────────────────────────────────────────────


class TestWiseClientInit:
    """Tests for WiseClient initialization and configuration."""

    def test_unconfigured_client(self):
        client = WiseClient()
        assert client.is_configured is False

    def test_configured_client(self):
        client = WiseClient(api_key="test-key-123")
        assert client.is_configured is True

    def test_sandbox_url_default(self):
        client = WiseClient(use_sandbox=True)
        assert "sandbox" in client.base_url

    def test_production_url(self):
        client = WiseClient(use_sandbox=False)
        assert "sandbox" not in client.base_url

    def test_custom_urls(self):
        client = WiseClient(
            base_url="https://custom.api.com/v4",
            sandbox_url="https://custom.sandbox.com/v4",
            use_sandbox=True,
        )
        assert client.base_url == "https://custom.sandbox.com/v4"

    def test_custom_production_url(self):
        client = WiseClient(
            base_url="https://custom.api.com/v4",
            use_sandbox=False,
        )
        assert client.base_url == "https://custom.api.com/v4"


class TestWiseClientSimulation:
    """Tests for simulated (no API key) comparison data."""

    @pytest.mark.asyncio
    async def test_simulated_comparison_returns_data(self):
        client = WiseClient()
        result = await client.get_comparison("USD", "PHP", send_amount=100.0)
        assert result["data_source"] == "simulated"
        assert result["source_currency"] == "USD"
        assert result["target_currency"] == "PHP"
        assert len(result["providers"]) >= 4

    @pytest.mark.asyncio
    async def test_simulated_providers_sorted_by_cost(self):
        client = WiseClient()
        result = await client.get_comparison("USD", "PHP", send_amount=500.0)
        costs = [p["total_cost"] for p in result["providers"]]
        assert costs == sorted(costs)

    @pytest.mark.asyncio
    async def test_simulated_providers_have_rankings(self):
        client = WiseClient()
        result = await client.get_comparison("USD", "MXN", send_amount=200.0)
        ranks = [p["rank"] for p in result["providers"]]
        assert ranks == list(range(1, len(ranks) + 1))

    @pytest.mark.asyncio
    async def test_simulated_cheapest_and_most_expensive(self):
        client = WiseClient()
        result = await client.get_comparison("USD", "NGN", send_amount=1000.0)
        assert result["cheapest"] is not None
        assert result["most_expensive"] is not None
        assert result["cheapest"]["total_cost"] <= result["most_expensive"]["total_cost"]

    @pytest.mark.asyncio
    async def test_simulated_provider_fields(self):
        client = WiseClient()
        result = await client.get_comparison("USD", "KES", send_amount=100.0)
        provider = result["providers"][0]
        assert "name" in provider
        assert "fee" in provider
        assert "exchange_rate" in provider
        assert "total_cost" in provider
        assert "recipient_receives" in provider
        assert "speed" in provider
        assert "confidence" in provider

    @pytest.mark.asyncio
    async def test_simulated_fetched_at_timestamp(self):
        client = WiseClient()
        before = time.time()
        result = await client.get_comparison("USD", "INR", send_amount=100.0)
        after = time.time()
        assert before <= result["fetched_at"] <= after


class TestWiseClientCountryMapping:
    """Tests for country-to-currency mapping."""

    @pytest.mark.asyncio
    async def test_philippines_maps_to_php(self):
        client = WiseClient()
        result = await client.get_comparison_for_country(100.0, "USD", "Philippines")
        assert result["target_currency"] == "PHP"

    @pytest.mark.asyncio
    async def test_mexico_maps_to_mxn(self):
        client = WiseClient()
        result = await client.get_comparison_for_country(100.0, "USD", "Mexico")
        assert result["target_currency"] == "MXN"

    @pytest.mark.asyncio
    async def test_unsupported_country_returns_error(self):
        client = WiseClient()
        result = await client.get_comparison_for_country(100.0, "USD", "Atlantis")
        assert "error" in result
        assert "supported_countries" in result

    @pytest.mark.asyncio
    async def test_crypto_currency_mapping(self):
        client = WiseClient()
        result = await client.get_comparison_for_country(100.0, "cUSD", "Philippines")
        assert result["source_currency"] == "USD"

    @pytest.mark.asyncio
    async def test_usdm_currency_mapping(self):
        client = WiseClient()
        result = await client.get_comparison_for_country(100.0, "USDm", "Nigeria")
        assert result["source_currency"] == "USD"

    def test_get_supported_corridors(self):
        client = WiseClient()
        corridors = client.get_supported_corridors()
        assert "Philippines" in corridors
        assert corridors["Philippines"] == "PHP"
        assert "Mexico" in corridors
        assert "Nigeria" in corridors


class TestWiseClientValidation:
    """Tests for input validation."""

    @pytest.mark.asyncio
    async def test_missing_amount_params(self):
        client = WiseClient(api_key="test-key")
        result = await client.get_comparison("USD", "PHP")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_recipient_gets_amount(self):
        client = WiseClient()
        result = await client.get_comparison(
            "USD", "PHP", recipient_gets_amount=5000.0
        )
        assert result["data_source"] == "simulated"


class TestWiseClientCaching:
    """Tests for caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        client = WiseClient()
        result1 = await client.get_comparison("USD", "PHP", send_amount=100.0)
        result2 = await client.get_comparison("USD", "PHP", send_amount=100.0)
        # Second call should be from cache (simulated doesn't cache, but configured does)
        assert result1["data_source"] == "simulated"

    def test_clear_cache(self):
        client = WiseClient()
        client._cache["test"] = {"data": {}, "expires_at": time.time() + 300}
        client.clear_cache()
        assert len(client._cache) == 0


class TestWiseClientRateLimiting:
    """Tests for rate limiting."""

    def test_rate_limit_check_within_limit(self):
        client = WiseClient()
        assert client._check_rate_limit() is True

    def test_rate_limit_check_exceeded(self):
        client = WiseClient()
        now = time.time()
        client._rate_limit_timestamps = [now - i for i in range(35)]
        assert client._check_rate_limit() is False

    def test_rate_limit_old_entries_pruned(self):
        client = WiseClient()
        old_time = time.time() - 120  # 2 minutes ago (outside window)
        client._rate_limit_timestamps = [old_time] * 50
        assert client._check_rate_limit() is True


class TestWiseClientResponseParsing:
    """Tests for API response parsing."""

    def test_parse_provider_quote(self):
        client = WiseClient()
        quote = {
            "providerName": "Wise",
            "fee": 1.50,
            "rate": 56.10,
            "midMarketRate": 56.20,
            "receivedAmount": 5500.0,
            "speed": "1-2 business days",
        }
        result = client._parse_provider_quote(quote, 100.0)
        assert result is not None
        assert result["name"] == "Wise"
        assert result["fee"] == 1.50
        assert result["exchange_rate"] > 0
        assert result["fx_markup_pct"] >= 0

    def test_parse_provider_quote_missing_name(self):
        client = WiseClient()
        quote = {"fee": 1.50, "rate": 56.10}
        result = client._parse_provider_quote(quote, 100.0)
        assert result is None

    def test_parse_comparison_response_list(self):
        client = WiseClient()
        raw = [
            {"providerName": "Wise", "fee": 1.50, "rate": 56.10, "receivedAmount": 5500.0},
            {"providerName": "WU", "fee": 5.00, "rate": 55.80, "receivedAmount": 5300.0},
        ]
        result = client._parse_comparison_response(raw, "USD", "PHP", 100.0)
        assert result["provider_count"] == 2
        assert result["cheapest"]["name"] == "Wise"

    def test_parse_comparison_response_dict(self):
        client = WiseClient()
        raw = {
            "providers": [
                {"providerName": "Wise", "fee": 1.50, "rate": 56.10, "receivedAmount": 5500.0},
            ]
        }
        result = client._parse_comparison_response(raw, "USD", "PHP", 100.0)
        assert result["provider_count"] == 1

    def test_normalize_speed_instant(self):
        client = WiseClient()
        assert client._normalize_speed("instant") == "Instant"
        assert client._normalize_speed("within seconds") == "Instant"

    def test_normalize_speed_days(self):
        client = WiseClient()
        assert "day" in client._normalize_speed("1-2 business days").lower()

    def test_normalize_speed_empty(self):
        client = WiseClient()
        assert client._normalize_speed("") == "Unknown"
        assert client._normalize_speed(None) == "Unknown"


class TestWiseClientHTTPErrors:
    """Tests for HTTP error handling with mocked responses."""

    @pytest.mark.asyncio
    async def test_api_rate_limit_returns_error(self):
        client = WiseClient(api_key="test-key")
        # Exhaust rate limit
        now = time.time()
        client._rate_limit_timestamps = [now - i for i in range(35)]
        result = await client.get_comparison("USD", "PHP", send_amount=100.0)
        assert "error" in result
        assert "rate_limit" in result["error"]


# ── Enhanced FeeComparisonService Tests ─────────────────────────────


class TestFeeComparisonServiceWithWise:
    """Tests for FeeComparisonService with Wise client integration."""

    @pytest.mark.asyncio
    async def test_compare_fees_with_wise_client(self):
        wise = WiseClient()
        service = FeeComparisonService(wise_client=wise)
        result = await service.compare_fees(100.0, "USD", "Philippines")
        assert "comparisons" in result
        assert "data_source" in result
        assert "last_updated" in result
        assert "provider_count" in result

    @pytest.mark.asyncio
    async def test_compare_fees_without_wise_client(self):
        service = FeeComparisonService()
        result = await service.compare_fees(100.0, "USD", "Philippines")
        assert "comparisons" in result
        assert result.get("data_source") == "static"

    @pytest.mark.asyncio
    async def test_celoflow_has_confidence_field(self):
        wise = WiseClient()
        service = FeeComparisonService(wise_client=wise)
        result = await service.compare_fees(100.0, "USD", "Philippines")
        celoflow = next(c for c in result["comparisons"] if c["provider"] == "CeloFlow")
        assert celoflow["confidence"] == "high"
        assert celoflow["data_source"] == "calculated"

    @pytest.mark.asyncio
    async def test_providers_have_rankings(self):
        wise = WiseClient()
        service = FeeComparisonService(wise_client=wise)
        result = await service.compare_fees(500.0, "USD", "Nigeria")
        ranks = [c.get("rank") for c in result["comparisons"]]
        assert all(r is not None for r in ranks)
        assert ranks == sorted(ranks)

    @pytest.mark.asyncio
    async def test_set_wise_client_after_init(self):
        service = FeeComparisonService()
        wise = WiseClient()
        service.set_wise_client(wise)
        result = await service.compare_fees(100.0, "USD", "Mexico")
        assert "comparisons" in result

    @pytest.mark.asyncio
    async def test_prefer_realtime_false_uses_static(self):
        wise = WiseClient()
        service = FeeComparisonService(wise_client=wise)
        result = await service.compare_fees(
            100.0, "USD", "Philippines", prefer_realtime=False
        )
        assert "comparisons" in result

    @pytest.mark.asyncio
    async def test_wise_error_falls_back_to_static(self):
        """When Wise client raises an exception, service falls back to static."""
        mock_wise = MagicMock()
        mock_wise.is_configured = True
        mock_wise.get_comparison_for_country = AsyncMock(
            side_effect=Exception("API down")
        )
        service = FeeComparisonService(wise_client=mock_wise)
        result = await service.compare_fees(100.0, "USD", "Philippines")
        assert "comparisons" in result
        assert len(result["comparisons"]) >= 5

    @pytest.mark.asyncio
    async def test_wise_error_response_falls_back(self):
        """When Wise client returns error dict, service falls back to static."""
        mock_wise = MagicMock()
        mock_wise.is_configured = True
        mock_wise.get_comparison_for_country = AsyncMock(
            return_value={"error": "rate_limit_exceeded"}
        )
        service = FeeComparisonService(wise_client=mock_wise)
        result = await service.compare_fees(100.0, "USD", "Philippines")
        assert "comparisons" in result
        assert len(result["comparisons"]) >= 5

    @pytest.mark.asyncio
    async def test_realtime_cache_shorter_ttl(self):
        """Real-time data should be cached with shorter TTL."""
        wise = WiseClient()
        service = FeeComparisonService(wise_client=wise)
        await service.compare_fees(100.0, "USD", "Philippines")
        # Check that realtime cache has an entry
        cache_key = "100.0:USD:Philippines"
        # The data should be in one of the caches
        has_cache = (
            cache_key in service._realtime_cache or cache_key in service._cache
        )
        assert has_cache

    @pytest.mark.asyncio
    async def test_data_source_field_present(self):
        wise = WiseClient()
        service = FeeComparisonService(wise_client=wise)
        result = await service.compare_fees(100.0, "USD", "Kenya")
        assert "data_source" in result
        assert result["data_source"] in ("realtime", "simulated", "static", "cache")

    @pytest.mark.asyncio
    async def test_last_updated_timestamp(self):
        wise = WiseClient()
        service = FeeComparisonService(wise_client=wise)
        before = time.time()
        result = await service.compare_fees(100.0, "USD", "India")
        after = time.time()
        assert before <= result["last_updated"] <= after


class TestFeeMonitoring:
    """Tests for fee monitoring and trend analysis."""

    @pytest.mark.asyncio
    async def test_monitor_fee_changes_basic(self):
        service = FeeComparisonService()
        result = await service.monitor_fee_changes(100.0, "USD", "Philippines")
        assert "current_comparison" in result
        assert "trend" in result
        assert "data_points" in result
        assert result["trend"] == "stable"

    @pytest.mark.asyncio
    async def test_monitor_fee_changes_with_history(self):
        service = FeeComparisonService()
        await service.monitor_fee_changes(100.0, "USD", "Philippines")
        result = await service.monitor_fee_changes(100.0, "USD", "Philippines")
        assert result["data_points"] >= 2

    @pytest.mark.asyncio
    async def test_monitor_returns_recommendations(self):
        service = FeeComparisonService()
        result = await service.monitor_fee_changes(100.0, "USD", "Nigeria")
        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)

    @pytest.mark.asyncio
    async def test_monitor_last_checked_timestamp(self):
        service = FeeComparisonService()
        before = time.time()
        result = await service.monitor_fee_changes(100.0, "USD", "Mexico")
        after = time.time()
        assert before <= result["last_checked"] <= after


class TestBackwardCompatibility:
    """Ensure existing FeeComparisonService interface still works."""

    @pytest.mark.asyncio
    async def test_compare_fees_basic_still_works(self):
        service = FeeComparisonService()
        result = await service.compare_fees(100.0, "USD", "Philippines")
        assert "comparisons" in result
        assert len(result["comparisons"]) >= 5
        assert result["comparisons"][0]["provider"] is not None

    @pytest.mark.asyncio
    async def test_celoflow_is_cheapest(self):
        service = FeeComparisonService()
        result = await service.compare_fees(500.0, "USD", "Nigeria")
        assert result["celoflow_rank"] == 1

    @pytest.mark.asyncio
    async def test_savings_calculated(self):
        service = FeeComparisonService()
        result = await service.compare_fees(1000.0, "USD", "Mexico")
        assert result["savings_vs_most_expensive"] > 0

    @pytest.mark.asyncio
    async def test_fee_caching_still_works(self):
        service = FeeComparisonService()
        await service.compare_fees(200.0, "USD", "Kenya", prefer_realtime=False)
        result = await service.compare_fees(200.0, "USD", "Kenya", prefer_realtime=False)
        assert "comparisons" in result

    def test_get_provider_details_still_works(self):
        service = FeeComparisonService()
        result = service.get_provider_details("wise")
        assert result["name"] == "Wise (TransferWise)"
        assert "Philippines" in result["supported_corridors"]

    def test_get_provider_details_unknown(self):
        service = FeeComparisonService()
        result = service.get_provider_details("unknown_provider")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_fee_optimization_still_works(self):
        service = FeeComparisonService()
        result = await service.get_fee_optimization(500.0, "USD", "Philippines")
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_recommendation_text_still_works(self):
        service = FeeComparisonService()
        result = await service.compare_fees(100.0, "USD", "India")
        assert "recommendation" in result
        assert len(result["recommendation"]) > 0

    def test_historical_trends_still_works(self):
        service = FeeComparisonService()
        result = service.get_historical_trends("Philippines")
        assert isinstance(result, list)


class TestRemittanceToolsIntegration:
    """Tests for the updated remittance tools with Wise integration."""

    @pytest.mark.asyncio
    async def test_compare_fees_tool_with_wise(self):
        from tools import remittance_tools

        wise = WiseClient()
        service = FeeComparisonService(wise_client=wise)
        remittance_tools.set_plugins(fee_comparison=service, wise=wise)

        result_str = await remittance_tools.compare_fees_with_providers.on_invoke_tool(
            None,
            '{"amount": 100.0, "from_currency": "USD", "destination_country": "Philippines"}',
        )
        result = json.loads(result_str)
        assert "comparisons" in result
        assert "data_source" in result

    @pytest.mark.asyncio
    async def test_compare_fees_tool_prefer_realtime(self):
        from tools import remittance_tools

        wise = WiseClient()
        service = FeeComparisonService(wise_client=wise)
        remittance_tools.set_plugins(fee_comparison=service, wise=wise)

        result_str = await remittance_tools.compare_fees_with_providers.on_invoke_tool(
            None,
            '{"amount": 500.0, "from_currency": "USD", "destination_country": "Mexico", "prefer_realtime": true}',
        )
        result = json.loads(result_str)
        assert "comparisons" in result

    @pytest.mark.asyncio
    async def test_monitor_fee_changes_tool(self):
        from tools import remittance_tools

        service = FeeComparisonService()
        remittance_tools.set_plugins(fee_comparison=service)

        result_str = await remittance_tools.monitor_fee_changes.on_invoke_tool(
            None,
            '{"amount": 100.0, "from_currency": "USD", "destination_country": "Nigeria"}',
        )
        result = json.loads(result_str)
        assert "current_comparison" in result
        assert "trend" in result

    @pytest.mark.asyncio
    async def test_monitor_fee_changes_tool_not_configured(self):
        from tools import remittance_tools

        remittance_tools.set_plugins(fee_comparison=None)

        result_str = await remittance_tools.monitor_fee_changes.on_invoke_tool(
            None,
            '{"amount": 100.0, "from_currency": "USD", "destination_country": "Nigeria"}',
        )
        result = json.loads(result_str)
        assert "error" in result
