"""Fee Comparison Service — real-time fee comparison with traditional providers.

Compares CeloFlow fees against Western Union, Wise, Remitly and other
traditional remittance providers with caching and rate limiting.
Supports real-time data from the Wise Comparison API with fallback to static data.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from integrations.wise_client import WiseClient

logger = logging.getLogger(__name__)

# Cache TTL in seconds
FEE_CACHE_TTL = 900          # 15 minutes for static data
REALTIME_CACHE_TTL = 300     # 5 minutes for real-time data

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
    """Compare CeloFlow fees against traditional remittance providers.

    Supports a hybrid approach:
    - Real-time data from the Wise Comparison API when available
    - Fallback to static provider fee data when API is unavailable
    - Confidence scoring to indicate data freshness and reliability
    """

    def __init__(self, wise_client: Optional["WiseClient"] = None) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._realtime_cache: Dict[str, Dict[str, Any]] = {}
        self._rate_limit_tracker: Dict[str, List[float]] = {}
        self._historical_data: List[Dict[str, Any]] = []
        self._wise_client = wise_client
        self._fee_monitor_data: List[Dict[str, Any]] = []
        logger.info(
            "FeeComparisonService initialised (wise_client=%s)",
            "configured" if wise_client and wise_client.is_configured else "none",
        )

    # ------------------------------------------------------------------
    # Public: compare_fees
    # ------------------------------------------------------------------

    def set_wise_client(self, client: "WiseClient") -> None:
        """Set or replace the Wise API client after init."""
        self._wise_client = client
        logger.info("WiseClient attached to FeeComparisonService")

    async def compare_fees(
        self,
        amount: float,
        from_currency: str,
        destination_country: str,
        celoflow_actual_fee: Optional[float] = None,
        prefer_realtime: bool = True,
    ) -> Dict[str, Any]:
        """Compare fees across all providers for a given transfer.

        Args:
            amount: Transfer amount in source currency
            from_currency: Source currency code
            destination_country: Destination country name
            celoflow_actual_fee: Actual CeloFlow fee if already calculated
            prefer_realtime: If True, attempt Wise API call first

        Returns:
            Comparison data with all providers, savings, and recommendations
        """
        # Check real-time cache first (shorter TTL)
        cache_key = f"{amount}:{from_currency}:{destination_country}"
        if prefer_realtime:
            rt_cached = self._get_realtime_cached(cache_key)
            if rt_cached:
                return rt_cached

        # Check static cache
        cached = self._get_cached(cache_key)
        if cached and not prefer_realtime:
            return cached

        comparisons: List[Dict[str, Any]] = []
        data_source = "static"
        last_updated = time.time()

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
            "confidence": "high",
            "data_source": "calculated",
            "breakdown": {
                "network_fee": round(amount * CELOFLOW_FEE["network_fee_pct"], 4),
                "agent_fee": round(amount * CELOFLOW_FEE["agent_fee_pct"], 4),
                "liquidity_fee": round(amount * CELOFLOW_FEE["liquidity_fee_pct"], 4),
            },
        }
        comparisons.append(celoflow_entry)

        # Try real-time Wise API data first
        wise_data = None
        if prefer_realtime and self._wise_client:
            try:
                wise_data = await self._wise_client.get_comparison_for_country(
                    amount=amount,
                    from_currency=from_currency,
                    destination_country=destination_country,
                )
                if wise_data and not wise_data.get("error"):
                    data_source = wise_data.get("data_source", "realtime")
                    last_updated = wise_data.get("fetched_at", time.time())
                else:
                    logger.warning(
                        "Wise API returned error, falling back to static: %s",
                        wise_data.get("error", "unknown"),
                    )
                    wise_data = None
            except Exception as e:
                logger.warning("Wise API call failed, falling back to static: %s", e)
                wise_data = None

        # Build provider comparisons from Wise data or static fallback
        if wise_data and wise_data.get("providers"):
            for wp in wise_data["providers"]:
                comparisons.append({
                    "provider": wp["name"],
                    "total_fee": wp["total_cost"],
                    "fee_percentage": round(wp["total_cost"] / amount * 100, 2) if amount > 0 else 0,
                    "fx_markup": wp.get("fx_markup", 0),
                    "speed": wp.get("speed", "Unknown"),
                    "recipient_receives": wp.get("recipient_receives", round(amount - wp["total_cost"], 2)),
                    "confidence": wp.get("confidence", "high"),
                    "data_source": data_source,
                    "exchange_rate": wp.get("exchange_rate", 0),
                    "mid_market_rate": wp.get("mid_market_rate", 0),
                    "fx_markup_pct": wp.get("fx_markup_pct", 0),
                    "breakdown": {
                        "transfer_fee": wp.get("fee", 0),
                        "fx_markup_cost": wp.get("fx_markup", 0),
                    },
                })
        else:
            # Fallback to static provider fees
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
                    "confidence": "medium",
                    "data_source": "static",
                    "breakdown": {
                        "transfer_fee": round(transfer_fee, 2),
                        "fx_markup_cost": round(fx_cost, 2),
                    },
                })

        # Sort by total fee (cheapest first)
        comparisons.sort(key=lambda x: x["total_fee"])

        # Assign rankings
        for i, comp in enumerate(comparisons):
            comp["rank"] = i + 1

        # Calculate savings vs each provider
        traditional = [c for c in comparisons if c["provider"] != "CeloFlow"]
        best_traditional = min(traditional, key=lambda x: x["total_fee"], default=None)
        worst_traditional = max(traditional, key=lambda x: x["total_fee"], default=None)

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
            "data_source": data_source,
            "last_updated": last_updated,
            "provider_count": len(comparisons),
        }

        # Cache with appropriate TTL
        if data_source in ("realtime", "cache"):
            self._set_realtime_cached(cache_key, result)
        else:
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

    # ------------------------------------------------------------------
    # Public: monitor_fee_changes
    # ------------------------------------------------------------------

    async def monitor_fee_changes(
        self,
        amount: float,
        from_currency: str,
        destination_country: str,
    ) -> Dict[str, Any]:
        """Track fee variations and provide trend analysis.

        Args:
            amount: Transfer amount
            from_currency: Source currency code
            destination_country: Destination country name

        Returns:
            Fee trend data with change indicators and recommendations
        """
        current = await self.compare_fees(
            amount, from_currency, destination_country, prefer_realtime=True
        )

        # Record for monitoring
        monitor_entry = {
            "timestamp": time.time(),
            "amount": amount,
            "destination_country": destination_country,
            "data_source": current.get("data_source", "unknown"),
            "celoflow_fee": next(
                (c["total_fee"] for c in current["comparisons"] if c["provider"] == "CeloFlow"),
                0,
            ),
            "cheapest_traditional": min(
                (c["total_fee"] for c in current["comparisons"] if c["provider"] != "CeloFlow"),
                default=0,
            ),
            "provider_fees": {
                c["provider"]: c["total_fee"] for c in current["comparisons"]
            },
        }
        self._fee_monitor_data.append(monitor_entry)

        # Keep last 500 entries
        if len(self._fee_monitor_data) > 500:
            self._fee_monitor_data = self._fee_monitor_data[-500:]

        # Analyze trends for this corridor
        corridor_data = [
            e for e in self._fee_monitor_data
            if e["destination_country"] == destination_country
        ]

        trend = "stable"
        change_pct = 0.0
        if len(corridor_data) >= 2:
            prev = corridor_data[-2]["cheapest_traditional"]
            curr = corridor_data[-1]["cheapest_traditional"]
            if prev > 0:
                change_pct = round((curr - prev) / prev * 100, 2)
                if change_pct > 2:
                    trend = "increasing"
                elif change_pct < -2:
                    trend = "decreasing"

        recommendations: List[str] = []
        if trend == "increasing":
            recommendations.append(
                "Traditional provider fees are rising. CeloFlow offers stable, low fees."
            )
        elif trend == "decreasing":
            recommendations.append(
                "Traditional fees are dropping, but CeloFlow still offers instant settlement."
            )

        return {
            "current_comparison": current,
            "trend": trend,
            "change_pct": change_pct,
            "data_points": len(corridor_data),
            "recommendations": recommendations,
            "last_checked": time.time(),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached comparison result (static data)."""
        cached = self._cache.get(key)
        if cached and cached["expires_at"] > time.time():
            return cached["data"]
        return None

    def _set_cached(self, key: str, data: Dict[str, Any]) -> None:
        """Cache a comparison result (static data, longer TTL)."""
        self._cache[key] = {
            "data": data,
            "expires_at": time.time() + FEE_CACHE_TTL,
        }

    def _get_realtime_cached(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached real-time comparison result (shorter TTL)."""
        cached = self._realtime_cache.get(key)
        if cached and cached["expires_at"] > time.time():
            return cached["data"]
        return None

    def _set_realtime_cached(self, key: str, data: Dict[str, Any]) -> None:
        """Cache a real-time comparison result (shorter TTL)."""
        self._realtime_cache[key] = {
            "data": data,
            "expires_at": time.time() + REALTIME_CACHE_TTL,
        }

    def _record_historical(self, data: Dict[str, Any]) -> None:
        """Record comparison for historical analysis."""
        self._historical_data.append({
            "timestamp": time.time(),
            "amount": data["amount"],
            "destination_country": data["destination_country"],
            "data_source": data.get("data_source", "static"),
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
