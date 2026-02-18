"""Route Optimization Service — multi-corridor route finding across Mento pools.

Finds optimal paths for cross-currency transfers, comparing direct vs multi-hop
routes with slippage analysis, liquidity depth scoring, and confidence ratings.
Integrates with the existing FeeComparisonService for total cost analysis.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Known Mento v2 exchange pairs on Celo Sepolia
# Maps "TokenA/TokenB" → True if a direct pool exists
MENTO_POOLS: Dict[str, bool] = {
    "USDm/CELO": True,
    "USDm/PHPm": True,
    "USDm/XOFm": True,
    "USDm/axlUSDC": True,
    "USDm/BRLm": True,
    "USDm/EURm": True,
    "USDm/KESm": True,
    "USDm/COPm": True,
    "USDm/GBPm": True,
    "USDm/CADm": True,
    "USDm/AUDm": True,
    "USDm/ZARm": True,
    "USDm/GHSm": True,
    "USDm/NGNm": True,
    "USDm/JPYm": True,
    "USDm/CHFm": True,
    "EURm/CELO": True,
}

# Estimated liquidity depth per pool (in USD equivalent)
POOL_LIQUIDITY: Dict[str, float] = {
    "USDm/CELO": 500_000,
    "USDm/PHPm": 100_000,
    "USDm/XOFm": 50_000,
    "USDm/axlUSDC": 200_000,
    "USDm/BRLm": 150_000,
    "USDm/EURm": 300_000,
    "USDm/KESm": 80_000,
    "USDm/COPm": 60_000,
    "USDm/GBPm": 200_000,
    "USDm/CADm": 100_000,
    "USDm/AUDm": 80_000,
    "USDm/ZARm": 70_000,
    "USDm/GHSm": 40_000,
    "USDm/NGNm": 90_000,
    "USDm/JPYm": 120_000,
    "USDm/CHFm": 150_000,
    "EURm/CELO": 100_000,
}

# Canonical aliases
CURRENCY_ALIASES: Dict[str, str] = {
    "cUSD": "USDm", "cEUR": "EURm", "cREAL": "BRLm",
    "USDC": "axlUSDC",
}


class RouteOptimizationService:
    """Find optimal multi-corridor routes across Mento pools."""

    def __init__(self, mento_plugin: Optional[Any] = None) -> None:
        self._mento = mento_plugin
        # Route cache: key → {result, expires_at}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 60  # 1 minute
        logger.info("RouteOptimizationService initialised")

    def set_mento_plugin(self, mento_plugin: Any) -> None:
        """Late-bind the Mento plugin after construction."""
        self._mento = mento_plugin

    # ------------------------------------------------------------------
    # Public: find_routes
    # ------------------------------------------------------------------

    async def find_routes(
        self,
        from_currency: str,
        to_currency: str,
        amount: float,
    ) -> Dict[str, Any]:
        """Find all possible routes between two currencies.

        Args:
            from_currency: Source currency symbol
            to_currency: Destination currency symbol
            amount: Amount in source currency

        Returns:
            Dict with routes list, recommended route, and analysis
        """
        src = CURRENCY_ALIASES.get(from_currency, from_currency)
        dst = CURRENCY_ALIASES.get(to_currency, to_currency)

        if src == dst:
            return {
                "routes": [],
                "recommended": None,
                "message": "Source and destination currencies are the same. Use send_token for direct transfer.",
            }

        # Check cache
        cache_key = f"{src}/{dst}/{amount}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        routes: List[Dict[str, Any]] = []

        # 1. Direct route
        direct = self._find_direct_route(src, dst, amount)
        if direct:
            routes.append(direct)

        # 2. Single-hop via USDm
        if src != "USDm" and dst != "USDm":
            hop_route = self._find_single_hop_route(src, dst, amount, "USDm")
            if hop_route:
                routes.append(hop_route)

        # 3. Single-hop via CELO
        if src != "CELO" and dst != "CELO":
            hop_route = self._find_single_hop_route(src, dst, amount, "CELO")
            if hop_route:
                routes.append(hop_route)

        # 4. Two-hop: src → CELO → USDm → dst
        if src != "CELO" and dst != "USDm" and src != "USDm":
            two_hop = self._find_two_hop_route(src, dst, amount, "CELO", "USDm")
            if two_hop:
                routes.append(two_hop)

        # Sort by estimated output (highest first = best rate)
        routes.sort(key=lambda r: r.get("estimated_output", 0), reverse=True)

        # Pick recommended
        recommended = routes[0] if routes else None

        result = {
            "from_currency": src,
            "to_currency": dst,
            "amount": amount,
            "routes": routes,
            "recommended": recommended,
            "route_count": len(routes),
            "timestamp": time.time(),
        }

        if not routes:
            result["message"] = f"No route found from {src} to {dst}. Try swapping via USDm."

        self._set_cached(cache_key, result)
        return result

    # ------------------------------------------------------------------
    # Public: analyze_route
    # ------------------------------------------------------------------

    def analyze_route(self, route: Dict[str, Any], amount: float) -> Dict[str, Any]:
        """Analyze a route for slippage, liquidity impact, and risk.

        Args:
            route: A single route dict from find_routes
            amount: Transfer amount

        Returns:
            Analysis with slippage estimate, liquidity score, risk assessment
        """
        hops = route.get("hops", [])
        total_slippage = 0.0
        min_liquidity = float("inf")

        for hop in hops:
            pool_key = hop.get("pool", "")
            liquidity = POOL_LIQUIDITY.get(pool_key, 50_000)
            min_liquidity = min(min_liquidity, liquidity)

            # Estimate slippage based on amount vs liquidity
            hop_amount_usd = amount  # simplified
            if liquidity > 0:
                impact = hop_amount_usd / liquidity
                slippage = impact * 0.5  # 0.5% per 100% of pool
                total_slippage += slippage

        # Liquidity score: 0-100
        if min_liquidity == float("inf"):
            liquidity_score = 0
        else:
            liquidity_score = min(100, int((min_liquidity / 500_000) * 100))

        # Risk assessment
        if total_slippage > 0.05:
            risk = "high"
        elif total_slippage > 0.02:
            risk = "medium"
        else:
            risk = "low"

        return {
            "route_type": route.get("type", "unknown"),
            "hops": len(hops),
            "estimated_slippage_percent": round(total_slippage * 100, 4),
            "liquidity_score": liquidity_score,
            "min_pool_liquidity_usd": min_liquidity if min_liquidity != float("inf") else 0,
            "risk_level": risk,
            "recommendation": (
                "Good route with low slippage"
                if risk == "low"
                else "Consider splitting into smaller transfers"
                if risk == "high"
                else "Acceptable route, monitor slippage"
            ),
        }

    # ------------------------------------------------------------------
    # Public: compare_routes
    # ------------------------------------------------------------------

    def compare_routes(self, routes: List[Dict[str, Any]], amount: float) -> Dict[str, Any]:
        """Compare multiple routes and provide a summary.

        Args:
            routes: List of route dicts
            amount: Transfer amount

        Returns:
            Comparison with rankings and analysis
        """
        if not routes:
            return {"rankings": [], "message": "No routes to compare"}

        rankings = []
        for i, route in enumerate(routes):
            analysis = self.analyze_route(route, amount)
            output = route.get("estimated_output", 0)
            fee_pct = route.get("total_fee_percent", 0)

            rankings.append({
                "rank": i + 1,
                "route_type": route.get("type", "unknown"),
                "path": " → ".join(route.get("path", [])),
                "estimated_output": output,
                "total_fee_percent": fee_pct,
                "slippage_percent": analysis["estimated_slippage_percent"],
                "liquidity_score": analysis["liquidity_score"],
                "risk_level": analysis["risk_level"],
            })

        # Sort by output descending
        rankings.sort(key=lambda r: r.get("estimated_output", 0), reverse=True)
        for i, r in enumerate(rankings):
            r["rank"] = i + 1

        best = rankings[0] if rankings else None
        worst = rankings[-1] if rankings else None
        savings = 0.0
        if best and worst and worst["estimated_output"] > 0:
            savings = best["estimated_output"] - worst["estimated_output"]

        return {
            "rankings": rankings,
            "best_route": best,
            "potential_savings": round(savings, 4),
            "route_count": len(rankings),
        }

    # ------------------------------------------------------------------
    # Private: route finding helpers
    # ------------------------------------------------------------------

    def _find_direct_route(
        self, src: str, dst: str, amount: float
    ) -> Optional[Dict[str, Any]]:
        """Check for a direct pool between src and dst."""
        pool_key = f"{src}/{dst}"
        reverse_key = f"{dst}/{src}"

        has_pool = MENTO_POOLS.get(pool_key) or MENTO_POOLS.get(reverse_key)
        if not has_pool:
            return None

        actual_key = pool_key if pool_key in MENTO_POOLS else reverse_key
        liquidity = POOL_LIQUIDITY.get(actual_key, 50_000)

        # Estimate output (simplified — in production, query on-chain)
        fee_pct = 0.25  # 0.25% Mento fee
        estimated_output = amount * (1 - fee_pct / 100)

        return {
            "type": "direct",
            "path": [src, dst],
            "hops": [{"pool": actual_key, "from": src, "to": dst}],
            "estimated_output": round(estimated_output, 6),
            "total_fee_percent": fee_pct,
            "liquidity_usd": liquidity,
            "confidence": "high" if liquidity > 100_000 else "medium",
        }

    def _find_single_hop_route(
        self, src: str, dst: str, amount: float, via: str
    ) -> Optional[Dict[str, Any]]:
        """Find a route via an intermediate currency (1 hop)."""
        # Check src → via pool
        pool1 = f"{src}/{via}"
        rev1 = f"{via}/{src}"
        has_pool1 = MENTO_POOLS.get(pool1) or MENTO_POOLS.get(rev1)
        if not has_pool1:
            return None

        # Check via → dst pool
        pool2 = f"{via}/{dst}"
        rev2 = f"{dst}/{via}"
        has_pool2 = MENTO_POOLS.get(pool2) or MENTO_POOLS.get(rev2)
        if not has_pool2:
            return None

        actual_key1 = pool1 if pool1 in MENTO_POOLS else rev1
        actual_key2 = pool2 if pool2 in MENTO_POOLS else rev2

        liq1 = POOL_LIQUIDITY.get(actual_key1, 50_000)
        liq2 = POOL_LIQUIDITY.get(actual_key2, 50_000)

        fee_pct = 0.50  # 2 × 0.25%
        estimated_output = amount * (1 - fee_pct / 100)

        return {
            "type": f"single_hop_via_{via}",
            "path": [src, via, dst],
            "hops": [
                {"pool": actual_key1, "from": src, "to": via},
                {"pool": actual_key2, "from": via, "to": dst},
            ],
            "estimated_output": round(estimated_output, 6),
            "total_fee_percent": fee_pct,
            "liquidity_usd": min(liq1, liq2),
            "confidence": "medium",
        }

    def _find_two_hop_route(
        self, src: str, dst: str, amount: float, via1: str, via2: str
    ) -> Optional[Dict[str, Any]]:
        """Find a route via two intermediate currencies (2 hops)."""
        pools = [
            (src, via1), (via1, via2), (via2, dst)
        ]

        hops = []
        for a, b in pools:
            key = f"{a}/{b}"
            rev = f"{b}/{a}"
            has = MENTO_POOLS.get(key) or MENTO_POOLS.get(rev)
            if not has:
                return None
            actual = key if key in MENTO_POOLS else rev
            hops.append({"pool": actual, "from": a, "to": b})

        fee_pct = 0.75  # 3 × 0.25%
        estimated_output = amount * (1 - fee_pct / 100)
        min_liq = min(
            POOL_LIQUIDITY.get(h["pool"], 50_000) for h in hops
        )

        return {
            "type": f"two_hop_via_{via1}_{via2}",
            "path": [src, via1, via2, dst],
            "hops": hops,
            "estimated_output": round(estimated_output, 6),
            "total_fee_percent": fee_pct,
            "liquidity_usd": min_liq,
            "confidence": "low",
        }

    # ------------------------------------------------------------------
    # Private: caching
    # ------------------------------------------------------------------

    def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        cached = self._cache.get(key)
        if cached and cached["expires_at"] > time.time():
            return cached["result"]
        return None

    def _set_cached(self, key: str, result: Dict[str, Any]) -> None:
        self._cache[key] = {
            "result": result,
            "expires_at": time.time() + self._cache_ttl,
        }
        if len(self._cache) > 500:
            oldest = sorted(self._cache, key=lambda k: self._cache[k]["expires_at"])
            for k in oldest[:100]:
                del self._cache[k]
