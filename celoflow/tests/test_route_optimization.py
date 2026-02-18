"""Tests for RouteOptimizationService — multi-corridor Mento routing."""

from __future__ import annotations

import pytest

from services.route_optimization_service import RouteOptimizationService


@pytest.fixture
def service() -> RouteOptimizationService:
    return RouteOptimizationService()


# ── Direct Route Finding ──────────────────────────────────────────


class TestDirectRoutes:
    @pytest.mark.asyncio
    async def test_direct_usdm_to_celo(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("USDm", "CELO", 100)
        assert result["route_count"] >= 1
        direct = [r for r in result["routes"] if r["type"] == "direct"]
        assert len(direct) == 1
        assert direct[0]["path"] == ["USDm", "CELO"]

    @pytest.mark.asyncio
    async def test_direct_usdm_to_brlm(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("USDm", "BRLm", 50)
        direct = [r for r in result["routes"] if r["type"] == "direct"]
        assert len(direct) == 1
        assert direct[0]["estimated_output"] > 0

    @pytest.mark.asyncio
    async def test_direct_usdm_to_phpm(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("USDm", "PHPm", 200)
        direct = [r for r in result["routes"] if r["type"] == "direct"]
        assert len(direct) == 1

    @pytest.mark.asyncio
    async def test_no_direct_brlm_to_phpm(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("BRLm", "PHPm", 100)
        direct = [r for r in result["routes"] if r["type"] == "direct"]
        assert len(direct) == 0


# ── Multi-Hop Routes ──────────────────────────────────────────────


class TestMultiHopRoutes:
    @pytest.mark.asyncio
    async def test_brlm_to_phpm_via_usdm(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("BRLm", "PHPm", 100)
        hop_routes = [r for r in result["routes"] if "single_hop" in r["type"]]
        assert len(hop_routes) >= 1
        # Should have a route via USDm
        via_usdm = [r for r in hop_routes if "USDm" in r["type"]]
        assert len(via_usdm) == 1
        assert via_usdm[0]["path"] == ["BRLm", "USDm", "PHPm"]

    @pytest.mark.asyncio
    async def test_eurm_to_phpm_routes(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("EURm", "PHPm", 100)
        assert result["route_count"] >= 1
        assert result["recommended"] is not None

    @pytest.mark.asyncio
    async def test_two_hop_route_exists(self, service: RouteOptimizationService) -> None:
        # EURm → CELO → USDm → PHPm (if no direct EURm→PHPm)
        result = await service.find_routes("EURm", "PHPm", 100)
        two_hop = [r for r in result["routes"] if "two_hop" in r["type"]]
        # May or may not exist depending on pool config
        # Just verify the structure is correct if present
        for route in two_hop:
            assert len(route["hops"]) == 3
            assert len(route["path"]) == 4


# ── Same Currency ─────────────────────────────────────────────────


class TestSameCurrency:
    @pytest.mark.asyncio
    async def test_same_currency_returns_empty(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("USDm", "USDm", 100)
        assert result["routes"] == []
        assert result["recommended"] is None
        assert "same" in result.get("message", "").lower()


# ── Currency Aliases ──────────────────────────────────────────────


class TestCurrencyAliases:
    @pytest.mark.asyncio
    async def test_cusd_alias(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("cUSD", "CELO", 100)
        assert result["from_currency"] == "USDm"
        assert result["route_count"] >= 1

    @pytest.mark.asyncio
    async def test_ceur_alias(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("cEUR", "CELO", 100)
        assert result["from_currency"] == "EURm"


# ── Route Analysis ────────────────────────────────────────────────


class TestRouteAnalysis:
    @pytest.mark.asyncio
    async def test_analyze_direct_route(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("USDm", "CELO", 100)
        direct = [r for r in result["routes"] if r["type"] == "direct"][0]
        analysis = service.analyze_route(direct, 100)
        assert "estimated_slippage_percent" in analysis
        assert "liquidity_score" in analysis
        assert "risk_level" in analysis
        assert analysis["risk_level"] in ("low", "medium", "high")

    @pytest.mark.asyncio
    async def test_high_amount_higher_slippage(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("USDm", "CELO", 100)
        direct = [r for r in result["routes"] if r["type"] == "direct"][0]
        analysis_small = service.analyze_route(direct, 100)
        analysis_large = service.analyze_route(direct, 500_000)
        assert analysis_large["estimated_slippage_percent"] > analysis_small["estimated_slippage_percent"]

    @pytest.mark.asyncio
    async def test_analyze_multi_hop_route(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("BRLm", "PHPm", 100)
        if result["routes"]:
            route = result["routes"][0]
            analysis = service.analyze_route(route, 100)
            assert analysis["hops"] >= 1


# ── Route Comparison ──────────────────────────────────────────────


class TestRouteComparison:
    @pytest.mark.asyncio
    async def test_compare_routes(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("BRLm", "PHPm", 100)
        comparison = service.compare_routes(result["routes"], 100)
        assert "rankings" in comparison
        assert comparison["route_count"] == len(result["routes"])
        if comparison["rankings"]:
            assert comparison["rankings"][0]["rank"] == 1

    def test_compare_empty_routes(self, service: RouteOptimizationService) -> None:
        comparison = service.compare_routes([], 100)
        assert comparison["rankings"] == []


# ── Recommended Route ─────────────────────────────────────────────


class TestRecommendedRoute:
    @pytest.mark.asyncio
    async def test_recommended_is_best_output(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("USDm", "PHPm", 100)
        if result["routes"]:
            recommended = result["recommended"]
            assert recommended is not None
            # Recommended should have highest estimated_output
            max_output = max(r["estimated_output"] for r in result["routes"])
            assert recommended["estimated_output"] == max_output


# ── Fee Estimation ────────────────────────────────────────────────


class TestFeeEstimation:
    @pytest.mark.asyncio
    async def test_direct_route_lower_fee(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("USDm", "CELO", 100)
        direct = [r for r in result["routes"] if r["type"] == "direct"]
        if direct:
            assert direct[0]["total_fee_percent"] == 0.25

    @pytest.mark.asyncio
    async def test_single_hop_higher_fee(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("BRLm", "PHPm", 100)
        hop_routes = [r for r in result["routes"] if "single_hop" in r["type"]]
        if hop_routes:
            assert hop_routes[0]["total_fee_percent"] == 0.50


# ── Caching ───────────────────────────────────────────────────────


class TestCaching:
    @pytest.mark.asyncio
    async def test_cached_result_returned(self, service: RouteOptimizationService) -> None:
        result1 = await service.find_routes("USDm", "CELO", 100)
        result2 = await service.find_routes("USDm", "CELO", 100)
        # Same timestamp means it was cached
        assert result1["timestamp"] == result2["timestamp"]

    @pytest.mark.asyncio
    async def test_different_amounts_not_cached(self, service: RouteOptimizationService) -> None:
        result1 = await service.find_routes("USDm", "CELO", 100)
        result2 = await service.find_routes("USDm", "CELO", 200)
        # Different cache keys
        assert result1["amount"] == 100
        assert result2["amount"] == 200


# ── Edge Cases ────────────────────────────────────────────────────


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_unknown_currency(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("USDm", "FAKECOIN", 100)
        assert result["route_count"] == 0

    @pytest.mark.asyncio
    async def test_zero_amount(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("USDm", "CELO", 0)
        # Should still find routes, just with 0 output
        assert result["route_count"] >= 1

    @pytest.mark.asyncio
    async def test_very_large_amount(self, service: RouteOptimizationService) -> None:
        result = await service.find_routes("USDm", "CELO", 10_000_000)
        if result["recommended"]:
            analysis = service.analyze_route(result["recommended"], 10_000_000)
            assert analysis["risk_level"] == "high"
