"""Remittance function-tools — exposed to the LLM agent via Contextwise."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict

from agents import function_tool

logger = logging.getLogger(__name__)

# These module-level references are set by main.py after plugin init
_mento_plugin: Any = None
_tee_plugin: Any = None
_remittance_plugin: Any = None
_compliance_plugin: Any = None
_notification_plugin: Any = None
_registry_plugin: Any = None
_kyc_plugin: Any = None
_compliance_agent_plugin: Any = None
_fee_comparison_service: Any = None
_wise_client: Any = None


def set_plugins(
    mento: Any = None,
    tee: Any = None,
    remittance: Any = None,
    compliance: Any = None,
    notification: Any = None,
    registry: Any = None,
    kyc: Any = None,
    compliance_agent: Any = None,
    fee_comparison: Any = None,
    wise: Any = None,
) -> None:
    """Wire up plugin references for tools to use."""
    global _mento_plugin, _tee_plugin, _remittance_plugin
    global _compliance_plugin, _notification_plugin, _registry_plugin
    global _kyc_plugin, _compliance_agent_plugin, _fee_comparison_service
    global _wise_client
    _mento_plugin = mento
    _tee_plugin = tee
    _remittance_plugin = remittance
    _compliance_plugin = compliance
    _notification_plugin = notification
    _registry_plugin = registry
    _kyc_plugin = kyc
    _compliance_agent_plugin = compliance_agent
    _fee_comparison_service = fee_comparison
    _wise_client = wise


# ═══════════════════════════════════════════════════════════════════
# Tool: find_optimal_route
# ═══════════════════════════════════════════════════════════════════

@function_tool
async def find_optimal_route(
    from_currency: str,
    to_currency: str,
    amount: float,
) -> str:
    """Find the optimal currency swap route on the Celo Mento Protocol.

    Args:
        from_currency: Source currency code (e.g. cUSD, USDC)
        to_currency: Destination currency code (e.g. cKES, cEUR)
        amount: Amount in the source currency to convert

    Returns:
        Route details including rate, estimated output, and fees as JSON string
    """
    import json

    if not _mento_plugin:
        return json.dumps({"error": "Mento plugin not configured"})

    route = await _mento_plugin.find_optimal_route(
        from_currency=from_currency,
        to_currency=to_currency,
        amount=Decimal(str(amount)),
    )
    return json.dumps(route)


# ═══════════════════════════════════════════════════════════════════
# Tool: calculate_fees
# ═══════════════════════════════════════════════════════════════════

@function_tool
async def calculate_fees(
    amount: float,
    from_currency: str,
    to_currency: str,
) -> str:
    """Calculate a detailed fee breakdown for a remittance transfer.

    Args:
        amount: Transfer amount in source currency
        from_currency: Source currency code (e.g. cUSD, USDC)
        to_currency: Destination currency code (e.g. cKES, cEUR)

    Returns:
        Fee breakdown with network, agent, and liquidity fees as JSON string
    """
    import json

    if not _mento_plugin:
        return json.dumps({"error": "Mento plugin not configured"})

    # First get the route to extract liquidity_fee
    route = await _mento_plugin.find_optimal_route(
        from_currency=from_currency,
        to_currency=to_currency,
        amount=Decimal(str(amount)),
    )

    amount_dec = Decimal(str(amount))
    network_fee = float(amount_dec * Decimal("0.001"))   # 0.1%
    agent_fee = float(amount_dec * Decimal("0.005"))      # 0.5%
    liquidity_fee = float(route.get("liquidity_fee", 0))
    total = network_fee + agent_fee + liquidity_fee
    total_pct = (total / float(amount_dec) * 100) if float(amount_dec) > 0 else 0

    result = {
        "amount": amount,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "network_fee": round(network_fee, 4),
        "agent_fee": round(agent_fee, 4),
        "liquidity_fee": round(liquidity_fee, 4),
        "total_fee": round(total, 4),
        "total_fee_percentage": round(total_pct, 2),
        "recipient_receives": round(float(route.get("estimated_output", 0)), 4),
        "currency": route.get("to_currency", ""),
    }
    return json.dumps(result)


# ═══════════════════════════════════════════════════════════════════
# Tool: execute_transfer
# ═══════════════════════════════════════════════════════════════════

@function_tool
async def execute_transfer(
    recipient_address: str,
    amount: float,
    from_currency: str,
    to_currency: str,
    user_id: str = "unknown",
) -> str:
    """Execute a cross-border remittance transfer via Mento.

    Args:
        recipient_address: Wallet address of the recipient
        amount: Amount to transfer
        from_currency: Source currency code (e.g. cUSD, USDC)
        to_currency: Destination currency code (e.g. cKES, cEUR)
        user_id: The ID of the user initiating the transfer.

    Returns:
        Transaction result with hash and tracking info as JSON string
    """
    import json

    if not _mento_plugin or not _tee_plugin:
        return json.dumps({"error": "Required plugins not configured"})

    # 1. Check Spending Limits
    if _remittance_plugin:
        if not _remittance_plugin.check_spending_limit(user_id, amount):
             return json.dumps({
                 "error": f"Transaction amount ${amount} exceeds your spending limit.",
                 "status": "failed"
             })

    # 2. KYC Eligibility Check
    if _kyc_plugin:
        try:
            kyc_result = await _kyc_plugin.check_transfer_eligibility(user_id, amount)
            if not kyc_result.get("eligible", True):
                return json.dumps({
                    "error": kyc_result.get("message", "KYC level insufficient for this amount."),
                    "status": "kyc_required",
                    "current_level": kyc_result.get("current_level", "none"),
                    "suggested_upgrade": kyc_result.get("suggested_upgrade"),
                    "upgrade_fee": kyc_result.get("upgrade_fee"),
                })
        except Exception as e:
            logger.warning("KYC check failed (non-blocking): %s", e)

    # 3. Compliance Screening
    if _compliance_agent_plugin:
        try:
            screening = await _compliance_agent_plugin.check_pre_transfer(
                recipient_address=recipient_address,
                destination_country="",
                amount=amount,
            )
            if not screening.get("approved", True):
                return json.dumps({
                    "error": "Transfer blocked by compliance screening.",
                    "status": "compliance_blocked",
                    "screening_id": screening.get("screening_id", ""),
                    "risk_score": screening.get("risk_score", 0),
                    "issues": screening.get("issues", []),
                })
        except Exception as e:
            logger.warning("Compliance screening failed (non-blocking): %s", e)

    # 4. Optimize Route
    try:
        route = await _mento_plugin.find_optimal_route(
            from_currency, to_currency, Decimal(str(amount))
        )
    except Exception as e:
        return json.dumps({"error": f"Route optimization failed: {str(e)}"})

    logger.info(f"Executing transfer: {amount} {from_currency} -> {to_currency} via {route['route']}")

    # 4. Sign and Broadcast (via Mento Plugin which handles TEE signing internally/mocked)
    # The MentoPlugin.execute_swap needs the private key or a signer.
    # Currently MentoPlugin is instantiated with a signer in main.py? 
    # Let's see main.py: mento_plugin = MentoPlugin(..., private_key=AGENT_PRIVATE_KEY)
    # So the AGENT pays. 
    
    try:
        tx_hash = await _mento_plugin.execute_swap(
            token_in=from_currency,
            token_out=to_currency,
            amount_in=Decimal(str(amount)),
            recipient=recipient_address
        )
    except Exception as e:
        return json.dumps({"error": f"Swap execution failed: {str(e)}"})

    result = {
        "status": "success",
        "tx_hash": tx_hash,
        "from_amount": amount,
        "from_currency": from_currency,
        "to_amount": float(route.get("estimated_output", 0)),
        "to_currency": to_currency,
        "recipient": recipient_address,
        "fee_tracking_id": "tx_12345", # simulated
    }

    # 5. Record Transaction
    if _remittance_plugin:
        _remittance_plugin.record_transaction(
            tx_hash=tx_hash,
            user_id=user_id,
            amount=Decimal(str(amount)),
            from_currency=from_currency,
            to_currency=to_currency,
            destination=recipient_address, # loosely using address as destination
            fees={"network_fee": 0.001 * amount}, # estimated
        )

    # 6. Record Reputation Activity
    if _registry_plugin:
        try:
            # We fire and forget or await. Awaiting is safer for now.
            await _registry_plugin.record_successful_task()
        except Exception as e:
            logger.warning(f"Failed to record reputation: {e}")

    # 6. Notify (Optional - if notification plugin hooked separately or called here)
    if _notification_plugin:
        # We can fire and forget, or await.
        # notification_plugin.notify_transfer_complete(...)
        # We'll leave it to the agent/scheduler to notify based on result, 
        # OR we can auto-notify here.
        pass

    return json.dumps(result)



# ═══════════════════════════════════════════════════════════════════
# Tool: get_wallet_balance
# ═══════════════════════════════════════════════════════════════════

@function_tool
async def get_wallet_balance(wallet_address: str) -> str:
    """Get the CELO and stablecoin balances for a wallet address.

    Args:
        wallet_address: The Celo wallet address to check

    Returns:
        Balance information for CELO and stablecoins as JSON string
    """
    import json

    if _mento_plugin:
        balances = await _mento_plugin.get_balances(wallet_address)
        return json.dumps({"address": wallet_address, "balances": balances})

    # Stub when mento plugin is not configured
    return json.dumps({
        "address": wallet_address,
        "balances": {
            "CELO": "0.0",
            "cUSD": "0.0",
            "cEUR": "0.0",
            "cKES": "0.0",
            "USDC": "0.0",
        },
        "note": "Connect to RPC to fetch live balances",
    })


# ═══════════════════════════════════════════════════════════════════
# Tool: compare_fees_with_providers
# ═══════════════════════════════════════════════════════════════════

@function_tool
async def compare_fees_with_providers(
    amount: float,
    from_currency: str,
    destination_country: str,
    prefer_realtime: bool = True,
) -> str:
    """Compare CeloFlow fees against traditional remittance providers with real-time data.

    Uses the Wise Comparison API for live fee data when available,
    with automatic fallback to static provider data.

    Args:
        amount: Transfer amount in source currency
        from_currency: Source currency code (e.g. USD, cUSD)
        destination_country: Destination country (e.g. Philippines, Mexico, Nigeria)
        prefer_realtime: If True, fetch real-time data from Wise API

    Returns:
        Fee comparison data with savings, rankings, confidence scores, and
        data source indicators as JSON string
    """
    import json

    if not _fee_comparison_service:
        return json.dumps({"error": "Fee comparison service not configured"})

    result = await _fee_comparison_service.compare_fees(
        amount=amount,
        from_currency=from_currency,
        destination_country=destination_country,
        prefer_realtime=prefer_realtime,
    )
    return json.dumps(result)


# ═════════════════════════════════════════════════════════════════
# Tool: monitor_fee_changes
# ═════════════════════════════════════════════════════════════════

@function_tool
async def monitor_fee_changes(
    amount: float,
    from_currency: str,
    destination_country: str,
) -> str:
    """Monitor fee changes and trends for a specific remittance corridor.

    Tracks fee variations over time and provides trend analysis,
    predictions, and optimization recommendations.

    Args:
        amount: Transfer amount in source currency
        from_currency: Source currency code (e.g. USD, cUSD)
        destination_country: Destination country (e.g. Philippines, Mexico, Nigeria)

    Returns:
        Fee trend data with change indicators and recommendations as JSON string
    """
    import json

    if not _fee_comparison_service:
        return json.dumps({"error": "Fee comparison service not configured"})

    result = await _fee_comparison_service.monitor_fee_changes(
        amount=amount,
        from_currency=from_currency,
        destination_country=destination_country,
    )
    return json.dumps(result)
