"""Transfer Preview Service — two-step transfer flow with fee transparency.

Implements Step 1 of the TEE-mediated two-step transfer:
- Calculate optimal route via Mento
- Fetch fee comparisons vs traditional providers
- Calculate agent x402 service fee (0.5% of transfer)
- Return structured preview with 30-second TTL

Design decisions:
- Preview data expires in 30s to ensure rate accuracy
- Preview ID links Step 1 (preview) to Step 2 (execution)
- Fallback to direct transfer if preview service unavailable
- TEE address balance is checked before showing preview
- Auto-swap status is included in preview for transparency
"""

from __future__ import annotations

import hashlib
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from plugins.mento_plugin import MentoPlugin
    from services.fee_comparison_service import FeeComparisonService
    from services.payment_reward_service import PaymentRewardService
    from plugins.tee_plugin import TEEPlugin

logger = logging.getLogger(__name__)

# Preview TTL in seconds
PREVIEW_TTL_SECONDS = 30

# Agent service fee percentage (x402)
AGENT_FEE_PCT = 0.005

# Max cached previews (memory bound)
MAX_CACHED_PREVIEWS = 1_000


class TransferPreviewService:
    """Generate and cache transfer previews for the two-step transfer flow.

    Step 1: preview_transfer() → returns preview_id + full cost breakdown
    Step 2: validate_preview(preview_id) → confirms preview is still valid
    """

    def __init__(
        self,
        mento_plugin: Optional["MentoPlugin"] = None,
        fee_comparison_service: Optional["FeeComparisonService"] = None,
        payment_reward_service: Optional["PaymentRewardService"] = None,
        tee_plugin: Optional["TEEPlugin"] = None,
    ) -> None:
        self._mento = mento_plugin
        self._fee_comparison = fee_comparison_service
        self._payment_reward = payment_reward_service
        self._tee = tee_plugin

        # preview_id -> preview data
        self._preview_cache: Dict[str, Dict[str, Any]] = {}

        logger.info("TransferPreviewService initialised")

    # ------------------------------------------------------------------
    # Public: preview_transfer
    # ------------------------------------------------------------------

    async def preview_transfer(
        self,
        recipient: str,
        amount: float,
        token: str,
        destination_country: str = "",
        from_currency: str = "USD",
        user_id: str = "unknown",
        reputation_score: float = 50.0,
    ) -> Dict[str, Any]:
        """Generate a transfer preview with full cost breakdown.

        Args:
            recipient: Recipient wallet address (0x...)
            amount: Transfer amount
            token: Token to send (e.g. BRLm, ZARm, USDm)
            destination_country: Destination country for fee comparison
            from_currency: Source currency for fee comparison
            user_id: User identifier
            reputation_score: Agent reputation score for fee calculation

        Returns:
            Preview dict with:
            - preview_id: Unique ID linking preview to execution
            - route: Optimal Mento route
            - fees: Breakdown of all fees
            - comparisons: Traditional provider comparison
            - tee_balance: TEE wallet balance status
            - expires_at: Unix timestamp when preview expires
            - expires_in_seconds: Seconds until expiry
        """
        preview_id = self._generate_preview_id(recipient, amount, token, user_id)

        # 1. Get optimal route
        route = await self._get_route(token, amount)

        # 2. Get fee comparisons (non-blocking)
        comparisons = await self._get_fee_comparisons(amount, from_currency, destination_country)

        # 3. Calculate agent service fee
        service_fee = self._calculate_service_fee(amount, reputation_score)

        # 4. Check TEE wallet balance
        tee_balance = await self._check_tee_balance(token, amount)

        # 5. Build fee breakdown
        network_fee = 0.0001  # ~0.01 cent on Celo
        fees = {
            "network_fee": network_fee,
            "network_fee_currency": "CELO",
            "service_fee": service_fee["service_fee"],
            "service_fee_currency": "USDm",
            "service_fee_pct": service_fee["fee_percentage"],
            "service_fee_tier": service_fee["tier"],
            "total_fee_usd": round(service_fee["service_fee"] + network_fee, 6),
            "total_fee_pct": service_fee["fee_percentage"],
        }

        # 6. Calculate savings vs cheapest traditional provider
        savings = self._calculate_savings(amount, fees["total_fee_usd"], comparisons)

        now = time.time()
        expires_at = now + PREVIEW_TTL_SECONDS

        preview = {
            "preview_id": preview_id,
            "recipient": recipient,
            "amount": amount,
            "token": token,
            "destination_country": destination_country,
            "route": route,
            "fees": fees,
            "comparisons": comparisons,
            "savings": savings,
            "tee_balance": tee_balance,
            "created_at": now,
            "expires_at": expires_at,
            "expires_in_seconds": PREVIEW_TTL_SECONDS,
            "user_id": user_id,
        }

        # Cache preview
        self._preview_cache[preview_id] = preview
        self._evict_expired_previews()

        logger.info(
            "Transfer preview created: id=%s, %s %s → %s, fee=%.4f USDm, expires_in=%ds",
            preview_id, amount, token, recipient[:10] + "...",
            fees["service_fee"], PREVIEW_TTL_SECONDS,
        )

        return preview

    # ------------------------------------------------------------------
    # Public: validate_preview
    # ------------------------------------------------------------------

    def validate_preview(self, preview_id: str) -> Dict[str, Any]:
        """Validate that a preview is still valid (not expired).

        Args:
            preview_id: Preview identifier from preview_transfer()

        Returns:
            Validation result with valid flag and remaining seconds
        """
        preview = self._preview_cache.get(preview_id)

        if not preview:
            return {
                "valid": False,
                "reason": "preview_not_found",
                "preview_id": preview_id,
            }

        now = time.time()
        if now >= preview["expires_at"]:
            del self._preview_cache[preview_id]
            return {
                "valid": False,
                "reason": "preview_expired",
                "preview_id": preview_id,
                "expired_at": preview["expires_at"],
            }

        remaining = preview["expires_at"] - now
        return {
            "valid": True,
            "preview_id": preview_id,
            "expires_in_seconds": round(remaining, 1),
            "amount": preview["amount"],
            "token": preview["token"],
            "recipient": preview["recipient"],
            "service_fee": preview["fees"]["service_fee"],
        }

    # ------------------------------------------------------------------
    # Public: get_preview
    # ------------------------------------------------------------------

    def get_preview(self, preview_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached preview by ID (without validation).

        Args:
            preview_id: Preview identifier

        Returns:
            Preview dict or None if not found/expired
        """
        preview = self._preview_cache.get(preview_id)
        if not preview:
            return None
        if time.time() >= preview["expires_at"]:
            del self._preview_cache[preview_id]
            return None
        return preview

    # ------------------------------------------------------------------
    # Public: invalidate_preview
    # ------------------------------------------------------------------

    def invalidate_preview(self, preview_id: str) -> None:
        """Explicitly invalidate a preview after execution."""
        self._preview_cache.pop(preview_id, None)
        logger.debug("Preview %s invalidated after execution", preview_id)

    # ------------------------------------------------------------------
    # Private: _get_route
    # ------------------------------------------------------------------

    async def _get_route(self, token: str, amount: float) -> Dict[str, Any]:
        """Get optimal Mento route for the token."""
        if not self._mento:
            return {
                "available": False,
                "reason": "mento_not_configured",
                "estimated_rate": 1.0,
                "token": token,
                "amount": amount,
            }

        try:
            route = await self._mento.find_optimal_route(
                from_currency="USDm",
                to_currency=token,
                amount=Decimal(str(amount)),
            )
            return {
                "available": True,
                "from_currency": "USDm",
                "to_currency": token,
                "amount": amount,
                "estimated_output": route.get("estimated_output", amount),
                "rate": route.get("rate", 1.0),
                "route_type": route.get("route_type", "direct"),
                "pool": route.get("pool", ""),
                "slippage_pct": route.get("slippage_pct", 0.1),
            }
        except Exception as e:
            logger.warning("Route lookup failed (non-blocking): %s", e)
            return {
                "available": False,
                "reason": str(e),
                "token": token,
                "amount": amount,
            }

    # ------------------------------------------------------------------
    # Private: _get_fee_comparisons
    # ------------------------------------------------------------------

    async def _get_fee_comparisons(
        self,
        amount: float,
        from_currency: str,
        destination_country: str,
    ) -> List[Dict[str, Any]]:
        """Get fee comparisons from traditional providers."""
        if not self._fee_comparison or not destination_country:
            return []

        try:
            result = await self._fee_comparison.compare_fees(
                amount=amount,
                from_currency=from_currency,
                destination_country=destination_country,
                prefer_realtime=False,  # Use cached data for speed
            )
            providers = result.get("providers", [])
            # Return top 3 providers for display
            return providers[:3] if providers else []
        except Exception as e:
            logger.warning("Fee comparison failed (non-blocking): %s", e)
            return []

    # ------------------------------------------------------------------
    # Private: _calculate_service_fee
    # ------------------------------------------------------------------

    def _calculate_service_fee(
        self,
        amount: float,
        reputation_score: float,
    ) -> Dict[str, Any]:
        """Calculate the x402 agent service fee."""
        if self._payment_reward:
            return self._payment_reward.calculate_x402_service_fee(
                transfer_amount=amount,
                reputation_score=reputation_score,
            )

        # Fallback calculation
        fee = round(amount * AGENT_FEE_PCT, 6)
        return {
            "service_fee": fee,
            "fee_percentage": round(AGENT_FEE_PCT * 100, 4),
            "currency": "USDm",
            "tier": "average",
            "multiplier": 1.0,
            "description": "CeloFlow agent service fee (x402)",
        }

    # ------------------------------------------------------------------
    # Private: _check_tee_balance
    # ------------------------------------------------------------------

    async def _check_tee_balance(self, token: str, amount: float) -> Dict[str, Any]:
        """Check if TEE wallet has sufficient balance for the transfer."""
        if not self._tee or not self._mento:
            return {
                "sufficient": True,
                "auto_swap_needed": False,
                "reason": "balance_check_unavailable",
            }

        try:
            account = self._tee.get_account()
            tee_address = account.address

            if not self._mento.w3 or not self._mento.w3.is_connected():
                return {
                    "sufficient": True,
                    "auto_swap_needed": False,
                    "tee_address": tee_address,
                    "reason": "rpc_not_connected",
                }

            from integrations.chain_config import ChainConfig
            from web3 import Web3

            config = ChainConfig.celo_sepolia()
            aliases = {"cUSD": "USDm", "cEUR": "EURm", "cREAL": "BRLm"}
            resolved_token = aliases.get(token, token)
            token_address = config.token_addresses.get(resolved_token)

            if not token_address:
                return {
                    "sufficient": True,
                    "auto_swap_needed": False,
                    "tee_address": tee_address,
                    "reason": "unknown_token",
                }

            decimals = 6 if any(s in resolved_token for s in ["USDC", "USDT", "axlUSDC"]) else 18
            amount_wei = int(Decimal(str(amount)) * (10 ** decimals))

            ERC20_BALANCE_ABI = [{
                "inputs": [{"name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function",
            }]

            contract = self._mento.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=ERC20_BALANCE_ABI,
            )
            balance_wei = contract.functions.balanceOf(tee_address).call()
            balance = balance_wei / (10 ** decimals)
            sufficient = balance_wei >= amount_wei

            return {
                "sufficient": sufficient,
                "auto_swap_needed": not sufficient,
                "tee_address": tee_address,
                "token": resolved_token,
                "balance": round(balance, 6),
                "required": amount,
                "deficit": round(max(0.0, amount - balance), 6) if not sufficient else 0.0,
            }

        except Exception as e:
            logger.warning("TEE balance check failed (non-blocking): %s", e)
            return {
                "sufficient": True,
                "auto_swap_needed": False,
                "reason": f"check_failed: {str(e)[:50]}",
            }

    # ------------------------------------------------------------------
    # Private: _calculate_savings
    # ------------------------------------------------------------------

    def _calculate_savings(
        self,
        amount: float,
        celoflow_fee: float,
        comparisons: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Calculate savings vs traditional providers."""
        if not comparisons:
            return {
                "available": False,
                "celoflow_fee": celoflow_fee,
                "celoflow_fee_pct": round((celoflow_fee / amount * 100) if amount > 0 else 0, 4),
            }

        # Find cheapest traditional provider
        provider_fees = []
        for provider in comparisons:
            total_fee = provider.get("total_fee", 0.0)
            if total_fee > 0:
                provider_fees.append({
                    "name": provider.get("name", "Unknown"),
                    "total_fee": total_fee,
                })

        if not provider_fees:
            return {
                "available": False,
                "celoflow_fee": celoflow_fee,
            }

        cheapest = min(provider_fees, key=lambda x: x["total_fee"])
        most_expensive = max(provider_fees, key=lambda x: x["total_fee"])

        savings_vs_cheapest = max(0.0, cheapest["total_fee"] - celoflow_fee)
        savings_vs_expensive = max(0.0, most_expensive["total_fee"] - celoflow_fee)
        savings_pct = round((savings_vs_cheapest / cheapest["total_fee"] * 100) if cheapest["total_fee"] > 0 else 0, 1)

        return {
            "available": True,
            "celoflow_fee": celoflow_fee,
            "celoflow_fee_pct": round((celoflow_fee / amount * 100) if amount > 0 else 0, 4),
            "cheapest_provider": cheapest["name"],
            "cheapest_provider_fee": cheapest["total_fee"],
            "savings_vs_cheapest": round(savings_vs_cheapest, 4),
            "savings_vs_cheapest_pct": savings_pct,
            "most_expensive_provider": most_expensive["name"],
            "savings_vs_most_expensive": round(savings_vs_expensive, 4),
        }

    # ------------------------------------------------------------------
    # Private: _generate_preview_id
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_preview_id(
        recipient: str,
        amount: float,
        token: str,
        user_id: str,
    ) -> str:
        """Generate a unique preview ID."""
        raw = f"{recipient}:{amount}:{token}:{user_id}:{time.time()}"
        return "prev_" + hashlib.sha256(raw.encode()).hexdigest()[:12]

    # ------------------------------------------------------------------
    # Private: _evict_expired_previews
    # ------------------------------------------------------------------

    def _evict_expired_previews(self) -> None:
        """Remove expired previews from cache."""
        now = time.time()
        expired = [pid for pid, p in self._preview_cache.items() if now >= p["expires_at"]]
        for pid in expired:
            del self._preview_cache[pid]

        # Also enforce max size
        if len(self._preview_cache) > MAX_CACHED_PREVIEWS:
            oldest = sorted(
                self._preview_cache.items(),
                key=lambda x: x[1]["created_at"],
            )
            for pid, _ in oldest[:len(self._preview_cache) - MAX_CACHED_PREVIEWS]:
                del self._preview_cache[pid]
