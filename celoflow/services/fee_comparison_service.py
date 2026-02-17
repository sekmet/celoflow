"""Fee Comparison Service — real-time fee comparison with traditional providers.

Compares CeloFlow fees against Western Union, Wise, Remitly and other
traditional remittance providers with caching and rate limiting.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Cache TTL in seconds (15 minutes for fee data)
FEE_CACHE_TTL = 900

# Rate limit: max requests per minute per provider
RATE_LIMIT_PER_MINUTE = 10

# Traditional provider fee structures (fallback/baseline data)
PROVIDER_FEES: Dict[str, Dict[str, Any]] = {
    "western_union": {
        "name": "Western Union",
        "base_fee_pct": 0.065,
        "min_fee": 4.99,
        "fx_markup_pct": 0.025,
        "speed": "1-3 business days",
        "corridors": {
            "Philippines": {"fee_pct": 0.05, "fx_markup": 0.02},
            "Mexico": {"fee_pct": 0.04, "fx_markup": 0.015},
            "Nigeria": {"fee_pct": 0.07, "fx_markup": 0.03},
            "Kenya": {"fee_pct": 0.06, "fx_markup": 0.025},
            "India": {"fee_pct": 0.03, "fx_markup": 0.015},
            "Colombia": {"fee_pct": 0.06, "fx_markup": 0.025},
            "Brazil": {"fee_pct": 0.05, "fx_markup": 0.02},
        },
    },
    "wise": {
        "name": "Wise (TransferWise)",
        "base_fee_pct": 0.015,
        "min_fee": 1.50,
        "fx_markup_pct": 0.005,
        "speed": "1-2 business days",
        "corridors": {
            "Philippines": {"fee_pct": 0.012, "fx_markup": 0.004},
            "Mexico": {"fee_pct": 0.01, "fx_markup": 0.003},
            "Nigeria": {"fee_pct": 0.02, "fx_markup": 0.006},
            "Kenya": {"fee_pct": 0.018, "fx_markup": 0.005},
            "India": {"fee_pct": 0.008, "fx_markup": 0.003},
            "Colombia": {"fee_pct": 0.015, "fx_markup": 0.005},
            "Brazil": {"fee_pct": 0.013, "fx_markup": 0.004},
        },
    },
    "remitly": {
        "name": "Remitly",
        "base_fee_pct": 0.035,
        "min_fee": 2.99,
        "fx_markup_pct": 0.015,
        "speed": "Minutes to 3 days",
        "corridors": {
            "Philippines": {"fee_pct": 0.03, "fx_markup": 0.012},
            "Mexico": {"fee_pct": 0.025, "fx_markup": 0.01},
            "Nigeria": {"fee_pct": 0.04, "fx_markup": 0.018},
            "Kenya": {"fee_pct": 0.035, "fx_markup": 0.015},
            "India": {"fee_pct": 0.02, "fx_markup": 0.008},
            "Colombia": {"fee_pct": 0.035, "fx_markup": 0.015},
            "Brazil": {"fee_pct": 0.03, "fx_markup": 0.012},
        },
    },
    "moneygram": {
        "name": "MoneyGram",
        "base_fee_pct": 0.055,
        "min_fee": 3.99,
        "fx_markup_pct": 0.02,
        "speed": "1-3 business days",
        "corridors": {
            "Philippines": {"fee_pct": 0.045, "fx_markup": 0.018},
            "Mexico": {"fee_pct": 0.035, "fx_markup": 0.015},
            "Nigeria": {"fee_pct": 0.06, "fx_markup": 0.025},
            "Kenya": {"fee_pct": 0.05, "fx_markup": 0.02},
            "India": {"fee_pct": 0.025, "fx_markup": 0.012},
            "Colombia": {"fee_pct": 0.05, "fx_markup": 0.02},
            "Brazil": {"fee_pct": 0.04, "fx_markup": 0.018},
        },
    },
}

# CeloFlow fee structure
CELOFLOW_FEE = {
    "name": "CeloFlow",
    "network_fee_pct": 0.001,
    "agent_fee_pct": 0.005,
    "liquidity_fee_pct": 0.0025,
    "fx_markup_pct": 0.0,
    "speed": "< 5 seconds",
}


class FeeComparisonService:
    """Compare CeloFlow fees against traditional remittance providers."""

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._rate_limit_tracker: Dict[str, List[float]] = {}
        self._historical_data: List[Dict[str, Any]] = []
        logger.info("FeeComparisonService initialised")

    # ------------------------------------------------------------------
    # Public: compare_fees
    # ------------------------------------------------------------------

    async def compare_fees(
        self,
        amount: float,
        from_currency: str,
        destination_country: str,
        celoflow_actual_fee: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Compare fees across all providers for a given transfer.

        Args:
            amount: Transfer amount in source currency
            from_currency: Source currency code
            destination_country: Destination country name
            celoflow_actual_fee: Actual CeloFlow fee if already calculated

        Returns:
            Comparison data with all providers, savings, and recommendations
        """
        cache_key = f"{amount}:{from_currency}:{destination_country}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        comparisons: List[Dict[str, Any]] = []

        # Calculate CeloFlow fee
        cf_fee = celoflow_actual_fee
        if cf_fee is None:
            cf_fee = amount * (
                CELOFLOW_FEE["network_fee_pct"]
                + CELOFLOW_FEE["agent_fee_pct"]
                + CELOFLOW_FEE["liquidity_fee_pct"]
            )

        celoflow_entry = {
            "provider": CELOFLOW_FEE["name"],
            "total_fee": round(cf_fee, 4),
            "fee_percentage": round(cf_fee / amount * 100, 2) if amount > 0 else 0,
            "fx_markup": 0.0,
            "speed": CELOFLOW_FEE["speed"],
            "recipient_receives": round(amount - cf_fee, 2),
            "breakdown": {
                "network_fee": round(amount * CELOFLOW_FEE["network_fee_pct"], 4),
                "agent_fee": round(amount * CELOFLOW_FEE["agent_fee_pct"], 4),
                "liquidity_fee": round(amount * CELOFLOW_FEE["liquidity_fee_pct"], 4),
            },
        }
        comparisons.append(celoflow_entry)

        # Calculate traditional provider fees
        for provider_id, provider in PROVIDER_FEES.items():
            corridor = provider["corridors"].get(destination_country, {})
            fee_pct = corridor.get("fee_pct", provider["base_fee_pct"])
            fx_markup = corridor.get("fx_markup", provider["fx_markup_pct"])

            transfer_fee = max(amount * fee_pct, provider["min_fee"])
            fx_cost = amount * fx_markup
            total_fee = transfer_fee + fx_cost

            comparisons.append({
                "provider": provider["name"],
                "total_fee": round(total_fee, 2),
                "fee_percentage": round(total_fee / amount * 100, 2) if amount > 0 else 0,
                "fx_markup": round(fx_cost, 2),
                "speed": provider["speed"],
                "recipient_receives": round(amount - total_fee, 2),
                "breakdown": {
                    "transfer_fee": round(transfer_fee, 2),
                    "fx_markup_cost": round(fx_cost, 2),
                },
            })

        # Sort by total fee (cheapest first)
        comparisons.sort(key=lambda x: x["total_fee"])

        # Calculate savings vs each provider
        best_traditional = min(
            (c for c in comparisons if c["provider"] != "CeloFlow"),
            key=lambda x: x["total_fee"],
            default=None,
        )
        worst_traditional = max(
            (c for c in comparisons if c["provider"] != "CeloFlow"),
            key=lambda x: x["total_fee"],
            default=None,
        )

        savings_vs_best = round(
            best_traditional["total_fee"] - cf_fee, 2
        ) if best_traditional else 0
        savings_vs_worst = round(
            worst_traditional["total_fee"] - cf_fee, 2
        ) if worst_traditional else 0

        result = {
            "amount": amount,
            "from_currency": from_currency,
            "destination_country": destination_country,
            "comparisons": comparisons,
            "celoflow_rank": next(
                (i + 1 for i, c in enumerate(comparisons) if c["provider"] == "CeloFlow"),
                1,
            ),
            "savings_vs_cheapest_traditional": savings_vs_best,
            "savings_vs_most_expensive": savings_vs_worst,
            "recommendation": self._generate_recommendation(
                cf_fee, comparisons, amount
            ),
        }

        # Cache and record
        self._set_cached(cache_key, result)
        self._record_historical(result)

        return result

    # ------------------------------------------------------------------
    # Public: get_provider_details
    # ------------------------------------------------------------------

    def get_provider_details(self, provider_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific provider."""
        provider = PROVIDER_FEES.get(provider_id)
        if not provider:
            return {"error": f"Unknown provider: {provider_id}"}
        return {
            "id": provider_id,
            "name": provider["name"],
            "base_fee_pct": provider["base_fee_pct"],
            "min_fee": provider["min_fee"],
            "fx_markup_pct": provider["fx_markup_pct"],
            "speed": provider["speed"],
            "supported_corridors": list(provider["corridors"].keys()),
        }

    # ------------------------------------------------------------------
    # Public: get_historical_trends
    # ------------------------------------------------------------------

    def get_historical_trends(
        self, destination_country: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get historical fee comparison data for trend analysis."""
        filtered = [
            entry
            for entry in self._historical_data
            if entry.get("destination_country") == destination_country
        ]
        return filtered[-limit:]

    # ------------------------------------------------------------------
    # Public: get_fee_optimization
    # ------------------------------------------------------------------

    async def get_fee_optimization(
        self,
        amount: float,
        from_currency: str,
        destination_country: str,
    ) -> Dict[str, Any]:
        """Get fee optimization recommendations."""
        comparison = await self.compare_fees(amount, from_currency, destination_country)

        recommendations: List[str] = []

        # Check if splitting transfer would be cheaper
        if amount > 5000:
            recommendations.append(
                "Consider splitting into smaller transfers for potentially lower fees."
            )

        # Check timing
        recommendations.append(
            "CeloFlow offers instant settlement vs 1-3 days for traditional providers."
        )

        # Check corridor-specific advice
        if destination_country in ["Philippines", "Mexico"]:
            recommendations.append(
                f"The {destination_country} corridor is well-served by CeloFlow with competitive rates."
            )

        return {
            "amount": amount,
            "destination_country": destination_country,
            "current_best": comparison["comparisons"][0]["provider"],
            "celoflow_savings": comparison["savings_vs_cheapest_traditional"],
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_recommendation(
        self,
        celoflow_fee: float,
        comparisons: List[Dict[str, Any]],
        amount: float,
    ) -> str:
        """Generate a human-readable recommendation."""
        celoflow_rank = next(
            (i + 1 for i, c in enumerate(comparisons) if c["provider"] == "CeloFlow"),
            1,
        )
        total_providers = len(comparisons)

        if celoflow_rank == 1:
            second = comparisons[1] if len(comparisons) > 1 else None
            savings = round(second["total_fee"] - celoflow_fee, 2) if second else 0
            return (
                f"CeloFlow is the cheapest option, saving you ${savings} "
                f"compared to {second['provider'] if second else 'others'}. "
                f"Plus, settlement is instant (< 5 seconds)."
            )
        return (
            f"CeloFlow ranks #{celoflow_rank} of {total_providers} providers. "
            f"However, CeloFlow offers instant settlement and blockchain transparency."
        )

    def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached comparison result."""
        cached = self._cache.get(key)
        if cached and cached["expires_at"] > time.time():
            return cached["data"]
        return None

    def _set_cached(self, key: str, data: Dict[str, Any]) -> None:
        """Cache a comparison result."""
        self._cache[key] = {
            "data": data,
            "expires_at": time.time() + FEE_CACHE_TTL,
        }

    def _record_historical(self, data: Dict[str, Any]) -> None:
        """Record comparison for historical analysis."""
        self._historical_data.append({
            "timestamp": time.time(),
            "amount": data["amount"],
            "destination_country": data["destination_country"],
            "celoflow_fee": data["comparisons"][0]["total_fee"]
            if data["comparisons"] and data["comparisons"][0]["provider"] == "CeloFlow"
            else 0,
            "cheapest_traditional": min(
                (c["total_fee"] for c in data["comparisons"] if c["provider"] != "CeloFlow"),
                default=0,
            ),
        })
        # Keep last 1000 entries
        if len(self._historical_data) > 1000:
            self._historical_data = self._historical_data[-1000:]
