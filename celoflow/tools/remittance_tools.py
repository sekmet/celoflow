"""Remittance function-tools — exposed to the LLM agent via Contextwise."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict

from agents import function_tool
from services.real_time_status import real_time_status_service, StatusEvent, OperationType

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
_intent_parsing_service: Any = None
_route_optimization_service: Any = None
_x402_client: Any = None
_payment_reward_service: Any = None
_transfer_preview_service: Any = None
_tee_wallet_service: Any = None


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
    intent_parsing: Any = None,
    route_optimization: Any = None,
    x402: Any = None,
    payment_reward: Any = None,
    transfer_preview: Any = None,
    tee_wallet: Any = None,
) -> None:
    """Wire up plugin references for tools to use."""
    global _mento_plugin, _tee_plugin, _remittance_plugin
    global _compliance_plugin, _notification_plugin, _registry_plugin
    global _kyc_plugin, _compliance_agent_plugin, _fee_comparison_service
    global _wise_client, _intent_parsing_service, _route_optimization_service
    global _x402_client, _payment_reward_service, _transfer_preview_service
    global _tee_wallet_service
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
    _intent_parsing_service = intent_parsing
    _route_optimization_service = route_optimization
    _x402_client = x402
    _payment_reward_service = payment_reward
    _transfer_preview_service = transfer_preview
    _tee_wallet_service = tee_wallet


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

    if not route.get("found"):
        return json.dumps({"error": route.get("error", "No route found"), "suggestion": route.get("suggestion", "")})

    logger.info("Executing transfer: %s %s -> %s via Mento v2", amount, from_currency, to_currency)

    # 5. Sign and Broadcast via Mento Broker.swapIn
    # The TEE plugin holds the agent's signing account
    signer = _tee_plugin.get_account() if _tee_plugin else None
    if not signer:
        return json.dumps({"error": "No signing account available (TEE plugin not configured)"})

    try:
        tx_hash = await _mento_plugin.execute_swap(
            route=route,
            recipient=recipient_address,
            signer=signer,
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
            "PHPm": "0.0",
            "XOFm": "0.0",
            "BRLm": "0.0",
            "COPm": "0.0",
            "ZARm": "0.0",
            "NGNm": "0.0",
            "USDT": "0.0",
            "axlUSDC": "0.0"
        }
    })

@function_tool
async def get_current_wallet_context() -> str:
    """Get the current wallet context including connection state and balances.

    Returns:
        Current wallet context as JSON string
    """
    import json
    from services.wallet_context_service import wallet_context_service
    
    context = wallet_context_service.get_wallet_context()
    return json.dumps({
        "wallet_address": context.wallet_address,
        "connected": context.connected,
        "chain_id": context.chain_id,
        "balances": context.balances
    })

# ═══════════════════════════════════════════════════════════════════
# Helper: emit real-time status for auto-swap progress
# ═══════════════════════════════════════════════════════════════════

async def _emit_swap_status(
    operation: str,
    message: str,
    progress: float = 0.0,
    token: str = "",
    tx_hash: str = "",
) -> None:
    """Broadcast a real-time status event for auto-swap progress."""
    try:
        event = StatusEvent(
            operation=OperationType.SWAPPING,
            message=message,
            progress=progress,
            token=token,
            transaction_hash=tx_hash or None,
            details={"auto_swap": True, "step": operation},
        )
        await real_time_status_service.broadcast_status(event)
    except Exception as e:
        logger.debug("Failed to emit swap status: %s", e)


# ═══════════════════════════════════════════════════════════════════
# Helper: auto-swap CELO → target token when agent wallet is short
# ═══════════════════════════════════════════════════════════════════

async def _auto_swap_for_token(
    w3,
    signer,
    target_symbol: str,
    target_address: str,
    deficit_wei: int,
    target_decimals: int,
    config,
) -> Dict[str, Any]:
    """Swap CELO → USDm → target token to cover a deficit in the agent wallet.

    For USDm itself, only one hop is needed (CELO → USDm).
    For other tokens (BRLm, EURm, etc.), two hops: CELO → USDm → target.

    Returns dict with 'summary' on success or 'error' on failure.
    """
    from web3 import Web3
    from plugins.mento_plugin import (
        MENTO_BROKER_ADDRESS, BIPOOL_MANAGER_ADDRESS, EXCHANGE_IDS, BROKER_ABI,
    )

    CELO_ADDR = Web3.to_checksum_address(
        config.token_addresses.get("CELO", "0x471EcE3750Da237f93B8E339c536989b8978a438")
    )
    USDm_ADDR = Web3.to_checksum_address(config.token_addresses.get("USDm", ""))
    BROKER = Web3.to_checksum_address(MENTO_BROKER_ADDRESS)
    PROVIDER = Web3.to_checksum_address(BIPOOL_MANAGER_ADDRESS)

    broker = w3.eth.contract(address=BROKER, abi=BROKER_ABI)

    ERC20_ABI = [
        {"inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
         "name": "approve", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
        {"inputs": [{"name": "account", "type": "address"}],
         "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    ]

    def _nonce():
        return w3.eth.get_transaction_count(signer.address, "pending")

    def _send(tx_dict):
        signed = signer.sign_transaction(tx_dict)
        h = w3.eth.send_raw_transaction(signed.raw_transaction)
        r = w3.eth.wait_for_transaction_receipt(h, timeout=60)
        return h.hex(), r["status"]

    # Determine swap path
    eid_celo_hex = EXCHANGE_IDS.get("USDm/CELO")
    if not eid_celo_hex:
        return {"error": "No CELO/USDm exchange ID configured"}

    eid_celo = bytes.fromhex(eid_celo_hex)

    if target_symbol == "USDm":
        # Single hop: CELO → USDm
        # Reverse-estimate: how much CELO do we need for deficit_wei of USDm?
        # Use a generous estimate: query getAmountOut with increasing CELO amounts
        celo_amount = int(deficit_wei * 4)  # ~$0.31/CELO, so 4x is safe overestimate
        quote = broker.functions.getAmountOut(PROVIDER, eid_celo, CELO_ADDR, USDm_ADDR, celo_amount).call()
        # Scale CELO amount to match deficit
        if quote > 0:
            celo_amount = int(celo_amount * deficit_wei / quote * 1.1)  # 10% extra
        logger.info("Auto-swap: %s CELO -> USDm (need %s USDm)", celo_amount / 1e18, deficit_wei / 1e18)
        await _emit_swap_status("swapping", f"Auto-swapping {celo_amount/1e18:.4f} CELO → USDm", progress=0.3, token="USDm")

        celo_c = w3.eth.contract(address=CELO_ADDR, abi=ERC20_ABI)
        tx = celo_c.functions.approve(BROKER, celo_amount).build_transaction(
            {"from": signer.address, "nonce": _nonce(), "gas": 100_000, "gasPrice": w3.eth.gas_price}
        )
        _, s = _send(tx)
        if s != 1:
            return {"error": "CELO approve failed"}

        quote = broker.functions.getAmountOut(PROVIDER, eid_celo, CELO_ADDR, USDm_ADDR, celo_amount).call()
        tx = broker.functions.swapIn(PROVIDER, eid_celo, CELO_ADDR, USDm_ADDR, celo_amount, int(quote * 0.9)).build_transaction(
            {"from": signer.address, "nonce": _nonce(), "gas": 500_000, "gasPrice": w3.eth.gas_price}
        )
        h, s = _send(tx)
        if s != 1:
            return {"error": f"CELO→USDm swap reverted (tx: {h})"}

        await _emit_swap_status("swapping", f"Auto-swap complete: CELO → USDm", progress=1.0, token="USDm")
        return {"summary": f"Swapped {celo_amount/1e18:.4f} CELO → USDm"}

    else:
        # Two hops: CELO → USDm → target
        # Find the exchange ID for USDm/target
        pair_key = f"USDm/{target_symbol}"
        eid_target_hex = EXCHANGE_IDS.get(pair_key)
        if not eid_target_hex:
            return {"error": f"No Mento pool for {pair_key}. Cannot auto-swap."}
        eid_target = bytes.fromhex(eid_target_hex)
        target_addr = Web3.to_checksum_address(target_address)

        # Step 1: Figure out how much USDm we need for the deficit of target token
        # Query: how much USDm for deficit_wei of target?
        # We reverse-estimate by querying a large USDm amount
        test_usdm = int(10 * 1e18)  # 10 USDm
        test_out = broker.functions.getAmountOut(PROVIDER, eid_target, USDm_ADDR, target_addr, test_usdm).call()
        if test_out == 0:
            return {"error": f"Mento pool {pair_key} returned 0. Pool may be paused."}
        usdm_needed = int(test_usdm * deficit_wei / test_out * 1.1)  # 10% buffer
        logger.info("Auto-swap hop1: need ~%s USDm for %s %s", usdm_needed / 1e18, deficit_wei / (10**target_decimals), target_symbol)
        await _emit_swap_status("swapping", f"Auto-swap hop 1/2: CELO → USDm (need ~{usdm_needed/1e18:.2f} USDm)", progress=0.1, token=target_symbol)

        # Step 2: Figure out how much CELO we need for that USDm
        test_celo = int(5 * 1e18)  # 5 CELO
        test_usdm_out = broker.functions.getAmountOut(PROVIDER, eid_celo, CELO_ADDR, USDm_ADDR, test_celo).call()
        if test_usdm_out == 0:
            return {"error": "CELO→USDm pool returned 0"}
        celo_needed = int(test_celo * usdm_needed / test_usdm_out * 1.1)
        logger.info("Auto-swap hop2: need ~%s CELO for %s USDm", celo_needed / 1e18, usdm_needed / 1e18)

        # Check CELO balance
        celo_c = w3.eth.contract(address=CELO_ADDR, abi=ERC20_ABI)
        celo_bal = celo_c.functions.balanceOf(signer.address).call()
        if celo_bal < celo_needed:
            return {
                "error": f"Insufficient CELO for auto-swap. Have {celo_bal/1e18:.4f}, need ~{celo_needed/1e18:.4f} CELO.",
                "status": "insufficient_celo",
            }

        # Hop 1: CELO → USDm
        tx = celo_c.functions.approve(BROKER, celo_needed).build_transaction(
            {"from": signer.address, "nonce": _nonce(), "gas": 100_000, "gasPrice": w3.eth.gas_price}
        )
        _, s = _send(tx)
        if s != 1:
            return {"error": "CELO approve failed for hop1"}

        quote1 = broker.functions.getAmountOut(PROVIDER, eid_celo, CELO_ADDR, USDm_ADDR, celo_needed).call()
        tx = broker.functions.swapIn(PROVIDER, eid_celo, CELO_ADDR, USDm_ADDR, celo_needed, int(quote1 * 0.9)).build_transaction(
            {"from": signer.address, "nonce": _nonce(), "gas": 500_000, "gasPrice": w3.eth.gas_price}
        )
        h1, s = _send(tx)
        if s != 1:
            return {"error": f"CELO→USDm swap reverted (tx: {h1})"}
        logger.info("Auto-swap hop1 done: CELO→USDm tx=%s", h1)
        await _emit_swap_status("swapping", f"Hop 1/2 complete: CELO → USDm (tx: {h1[:10]}...)", progress=0.5, token=target_symbol)

        # Hop 2: USDm → target
        import time; time.sleep(2)  # Wait for balance to settle
        usdm_c = w3.eth.contract(address=USDm_ADDR, abi=ERC20_ABI)
        usdm_bal = usdm_c.functions.balanceOf(signer.address).call()
        swap_amount = min(usdm_bal, usdm_needed)
        if swap_amount == 0:
            return {"error": "USDm balance is 0 after hop1 swap"}

        tx = usdm_c.functions.approve(BROKER, swap_amount).build_transaction(
            {"from": signer.address, "nonce": _nonce(), "gas": 100_000, "gasPrice": w3.eth.gas_price}
        )
        _, s = _send(tx)
        if s != 1:
            return {"error": "USDm approve failed for hop2"}

        quote2 = broker.functions.getAmountOut(PROVIDER, eid_target, USDm_ADDR, target_addr, swap_amount).call()
        tx = broker.functions.swapIn(PROVIDER, eid_target, USDm_ADDR, target_addr, swap_amount, int(quote2 * 0.9)).build_transaction(
            {"from": signer.address, "nonce": _nonce(), "gas": 500_000, "gasPrice": w3.eth.gas_price}
        )
        h2, s = _send(tx)
        if s != 1:
            return {"error": f"USDm→{target_symbol} swap reverted (tx: {h2})"}
        logger.info("Auto-swap hop2 done: USDm→%s tx=%s", target_symbol, h2)
        await _emit_swap_status("swapping", f"Hop 2/2 complete: USDm → {target_symbol} (tx: {h2[:10]}...)", progress=1.0, token=target_symbol)

        return {"summary": f"Swapped {celo_needed/1e18:.4f} CELO → USDm → {target_symbol} (2 hops)"}


# ═══════════════════════════════════════════════════════════════════
# Tool: send_token
# ═══════════════════════════════════════════════════════════════════

@function_tool
async def send_token(
    recipient_address: str,
    amount: float,
    token: str,
    user_id: str = "unknown",
) -> str:
    """Send an ERC-20 token to a recipient address on Celo with automatic auto-swap.

    Use this for ALL token transfers. If the agent wallet lacks the target token,
    it automatically swaps CELO → USDm → target token via Mento v2.
    Supports all 19 tokens: USDm, EURm, BRLm, KESm, XOFm, PHPm, COPm, GBPm,
    CADm, AUDm, ZARm, GHSm, NGNm, JPYm, CHFm, CELO, USDT, axlUSDC.

    Examples:
    - "Send 1 ZARm to 0x..." → auto-swaps CELO→USDm→ZARm if needed
    - "Send 5 KESm to 0x..." → auto-swaps CELO→USDm→KESm if needed
    - "Send 0.5 CELO to 0x..." → direct transfer (no swap needed)

    Args:
        recipient_address: Wallet address of the recipient (0x...)
        amount: Amount of tokens to send
        token: Token symbol (e.g. BRLm, ZARm, USDm, CELO, etc.)
        user_id: The ID of the user initiating the transfer.

    Returns:
        Transaction result with hash and explorer link as JSON string
    """
    import json
    from integrations.chain_config import ChainConfig

    if not _tee_plugin:
        return json.dumps({"error": "TEE plugin not configured — cannot sign transactions"})

    # 1. Spending limit check
    if _remittance_plugin:
        if not _remittance_plugin.check_spending_limit(user_id, amount):
            return json.dumps({
                "error": f"Transaction amount {amount} exceeds your spending limit.",
                "status": "failed"
            })

    # 2. KYC check
    if _kyc_plugin:
        try:
            kyc_result = await _kyc_plugin.check_transfer_eligibility(user_id, amount)
            if not kyc_result.get("eligible", True):
                return json.dumps({
                    "error": kyc_result.get("message", "KYC level insufficient"),
                    "status": "kyc_required",
                    "current_level": kyc_result.get("current_level", "none"),
                })
        except Exception as e:
            logger.warning("KYC check failed (non-blocking): %s", e)

    # 3. Compliance screening
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
                })
        except Exception as e:
            logger.warning("Compliance screening failed (non-blocking): %s", e)

    # 4. Resolve token address
    config = ChainConfig.celo_sepolia()
    aliases = {"cUSD": "USDm", "cEUR": "EURm", "cREAL": "BRLm"}
    resolved_token = aliases.get(token, token)
    token_address = config.token_addresses.get(resolved_token)

    if not token_address:
        return json.dumps({"error": f"Unknown token '{token}'. Supported: {', '.join(config.token_addresses.keys())}"})

    # 5. Get signer from TEE plugin
    signer = _tee_plugin.get_account()
    if not signer:
        return json.dumps({"error": "No signing account available"})

    # 6. Execute ERC-20 transfer on-chain
    if _mento_plugin and _mento_plugin.w3 and _mento_plugin.w3.is_connected():
        try:
            from web3 import Web3
            from plugins.mento_plugin import (
                MENTO_BROKER_ADDRESS, BIPOOL_MANAGER_ADDRESS, EXCHANGE_IDS, BROKER_ABI,
            )

            w3 = _mento_plugin.w3
            decimals = 6 if "USDC" in resolved_token or "USDT" in resolved_token or "axlUSDC" in resolved_token else 18
            amount_wei = int(Decimal(str(amount)) * (10 ** decimals))

            ERC20_ABI = [
                {
                    "inputs": [
                        {"name": "to", "type": "address"},
                        {"name": "amount", "type": "uint256"},
                    ],
                    "name": "transfer",
                    "outputs": [{"name": "", "type": "bool"}],
                    "stateMutability": "nonpayable",
                    "type": "function",
                },
                {
                    "inputs": [
                        {"name": "account", "type": "address"},
                    ],
                    "name": "balanceOf",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function",
                },
                {
                    "inputs": [
                        {"name": "spender", "type": "address"},
                        {"name": "amount", "type": "uint256"},
                    ],
                    "name": "approve",
                    "outputs": [{"name": "", "type": "bool"}],
                    "stateMutability": "nonpayable",
                    "type": "function",
                },
            ]

            token_contract = w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=ERC20_ABI,
            )

            # 6a. Pre-flight balance check — does the agent wallet hold enough?
            signer_balance = token_contract.functions.balanceOf(signer.address).call()
            if signer_balance < amount_wei:
                logger.info(
                    "Agent wallet has %s but needs %s of %s — attempting auto-swap from CELO",
                    signer_balance / (10 ** decimals), amount, resolved_token,
                )
                await _emit_swap_status(
                    "checking_balance",
                    f"Insufficient {resolved_token} balance — initiating auto-swap from CELO",
                    progress=0.0, token=resolved_token,
                )
                # Auto-swap: CELO -> USDm -> target token (two hops if needed)
                try:
                    deficit_wei = amount_wei - signer_balance
                    # Add 5% buffer for slippage
                    deficit_with_buffer = int(deficit_wei * 1.05)
                    swap_result = await _auto_swap_for_token(
                        w3, signer, resolved_token, token_address, deficit_with_buffer, decimals, config,
                    )
                    if swap_result.get("error"):
                        return json.dumps(swap_result)
                    logger.info("Auto-swap completed: %s", swap_result.get("summary", ""))
                    # Re-check balance after swap
                    signer_balance = token_contract.functions.balanceOf(signer.address).call()
                    if signer_balance < amount_wei:
                        return json.dumps({
                            "error": f"Auto-swap succeeded but agent wallet still has insufficient {resolved_token}. "
                                     f"Balance: {signer_balance / (10 ** decimals)}, needed: {amount}. "
                                     f"Try a smaller amount.",
                            "status": "insufficient_balance",
                        })
                except Exception as swap_err:
                    logger.error("Auto-swap failed: %s", swap_err)
                    return json.dumps({
                        "error": f"Agent wallet has insufficient {resolved_token} "
                                 f"(has {signer_balance / (10 ** decimals)}, needs {amount}). "
                                 f"Auto-swap from CELO failed: {str(swap_err)[:100]}",
                        "status": "insufficient_balance",
                    })

            nonce = w3.eth.get_transaction_count(signer.address)
            tx = token_contract.functions.transfer(
                Web3.to_checksum_address(recipient_address),
                amount_wei,
            ).build_transaction({
                "from": signer.address,
                "nonce": nonce,
                "gas": 100_000,
                "gasPrice": w3.eth.gas_price,
            })
            signed_tx = signer.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            tx_hex = tx_hash.hex()

            logger.info(
                "ERC-20 transfer executed: %s %s -> %s (tx: %s, gas: %d, status: %d)",
                amount, resolved_token, recipient_address[:10], tx_hex, receipt["gasUsed"], receipt["status"],
            )

            if receipt["status"] == 0:
                return json.dumps({
                    "error": f"Transfer reverted on-chain. The agent wallet may not hold enough {token}. "
                             f"Tx: https://sepolia.celoscan.io/tx/{tx_hex}",
                    "status": "reverted",
                    "tx_hash": tx_hex,
                })

            await _emit_swap_status(
                "transferring",
                f"Transfer complete: {amount} {resolved_token} → {recipient_address[:10]}...",
                progress=1.0, token=resolved_token, tx_hash=tx_hex,
            )

            result = {
                "status": "success",
                "tx_hash": tx_hex,
                "amount": amount,
                "token": token,
                "recipient": recipient_address,
                "explorer_url": f"https://sepolia.celoscan.io/tx/{tx_hex}",
            }
        except Exception as e:
            logger.error("ERC-20 transfer failed: %s", e)
            return json.dumps({"error": f"Token transfer failed: {str(e)}"})
    else:
        # Fallback: simulated transfer when RPC not connected
        tx_hex = "0x" + "b3e5f7a9c1d2" * 5 + "0001"
        logger.info("Simulated ERC-20 transfer: %s %s -> %s", amount, resolved_token, recipient_address[:10])
        result = {
            "status": "success",
            "tx_hash": tx_hex,
            "amount": amount,
            "token": token,
            "recipient": recipient_address,
            "note": "Simulated — RPC not connected",
            "explorer_url": f"https://sepolia.celoscan.io/tx/{tx_hex}",
        }

    # 7. Record transaction
    if _remittance_plugin:
        _remittance_plugin.record_transaction(
            tx_hash=result["tx_hash"],
            user_id=user_id,
            amount=Decimal(str(amount)),
            from_currency=token,
            to_currency=token,
            destination=recipient_address,
            fees={"network_fee": 0.0001},
        )

    # 8. Record reputation
    if _registry_plugin:
        try:
            await _registry_plugin.record_successful_task()
        except Exception as e:
            logger.warning("Failed to record reputation: %s", e)

    # 9. Process x402 payment reward for successful transfer
    if _payment_reward_service and result.get("status") == "success":
        try:
            from integrations.chain_config import ChainConfig as _CC
            _config = _CC.celo_sepolia()
            _aliases = {"cUSD": "USDm", "cEUR": "EURm", "cREAL": "BRLm"}
            _resolved = _aliases.get(token, token)
            _decimals = 6 if any(s in _resolved for s in ["USDC", "USDT", "axlUSDC"]) else 18
            _usd_equiv = amount  # 1:1 approximation for stablecoins
            reward_result = await _payment_reward_service.process_transfer_reward(
                agent_id=0,
                transfer_amount=_usd_equiv,
                success_status=True,
                tx_hash=result.get("tx_hash"),
                token=_resolved,
            )
            if reward_result.get("success"):
                result["agent_reward"] = {
                    "payment_id": reward_result.get("payment_id"),
                    "reward_amount": reward_result.get("reward_amount"),
                    "currency": reward_result.get("currency", "USDm"),
                    "tier": reward_result.get("tier"),
                }
                logger.info(
                    "Agent reward processed: %.4f USDm (tier=%s, payment_id=%s)",
                    reward_result.get("reward_amount", 0),
                    reward_result.get("tier"),
                    reward_result.get("payment_id"),
                )
        except Exception as e:
            logger.warning("Agent reward processing failed (non-blocking): %s", e)

    return json.dumps(result)


# ═══════════════════════════════════════════════════════════════════
# Tool: preview_transfer
# ═══════════════════════════════════════════════════════════════════

@function_tool
async def preview_transfer(
    recipient_address: str,
    amount: float,
    token: str,
    destination_country: str = "",
    from_currency: str = "USD",
    user_id: str = "unknown",
) -> str:
    """Preview a transfer before execution — Step 1 of the two-step transfer flow.

    Shows optimal route, fee breakdown, traditional service comparisons,
    and agent x402 service fee. Returns a preview_id valid for 30 seconds
    that can be referenced when executing the transfer.

    Use this BEFORE send_token when the user wants to see fees first,
    or when showing a confirmation dialog with cost breakdown.

    Args:
        recipient_address: Recipient wallet address (0x...)
        amount: Transfer amount
        token: Token to send (e.g. BRLm, ZARm, USDm, CELO)
        destination_country: Destination country for fee comparison (e.g. Brazil, Kenya)
        from_currency: Source currency for comparison (e.g. USD)
        user_id: User identifier

    Returns:
        Preview data with preview_id, route, fees, comparisons, and expiry as JSON string
    """
    import json

    if not _transfer_preview_service:
        return json.dumps({"error": "Transfer preview service not configured"})

    result = await _transfer_preview_service.preview_transfer(
        recipient=recipient_address,
        amount=amount,
        token=token,
        destination_country=destination_country,
        from_currency=from_currency,
        user_id=user_id,
    )
    return json.dumps(result, default=str)


# ═══════════════════════════════════════════════════════════════════
# Tool: get_agent_earnings
# ═══════════════════════════════════════════════════════════════════

@function_tool
async def get_agent_earnings(agent_id: int = 0) -> str:
    """Get earnings summary for the CeloFlow agent from x402 payment rewards.

    Shows total earnings, current reputation tier, daily earnings,
    and recent payment history from successful transfers.

    Args:
        agent_id: Agent identifier (default 0 for the main CeloFlow agent)

    Returns:
        Earnings summary with total, tier, multiplier, and recent payments as JSON string
    """
    import json

    if not _payment_reward_service:
        return json.dumps({"error": "Payment reward service not configured"})

    result = _payment_reward_service.get_agent_earnings(agent_id)
    return json.dumps(result, default=str)


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


# ═════════════════════════════════════════════════════════════════
# Tool: parse_transfer_intent
# ═════════════════════════════════════════════════════════════════

@function_tool
async def parse_transfer_intent(
    user_message: str,
    user_id: str = "",
) -> str:
    """Parse a natural language message into a structured transfer intent.

    Extracts amount, currency, recipient, frequency, and destination
    from free-form text in any supported language (English, Spanish,
    Portuguese, French, Swahili, Filipino).

    Args:
        user_message: The user's natural language message
        user_id: Optional user identifier for language preference

    Returns:
        Structured intent as JSON string with amount, currency, recipient, etc.
    """
    import json

    if not _intent_parsing_service:
        return json.dumps({"error": "Intent parsing service not configured"})

    intent = _intent_parsing_service.parse_intent(user_message, user_id)
    return json.dumps(intent, default=str)


# ═════════════════════════════════════════════════════════════════
# Tool: find_optimal_routes
# ═════════════════════════════════════════════════════════════════

@function_tool
async def find_optimal_routes(
    from_currency: str,
    to_currency: str,
    amount: float,
) -> str:
    """Find all possible routes between two currencies across Mento pools.

    Compares direct, single-hop, and multi-hop routes with slippage
    analysis, liquidity scoring, and fee estimates. Returns a ranked
    list of routes with a recommended best option.

    Args:
        from_currency: Source currency symbol (e.g. USDm, CELO, BRLm)
        to_currency: Destination currency symbol (e.g. PHPm, XOFm, EURm)
        amount: Amount in source currency

    Returns:
        Ranked routes with analysis as JSON string
    """
    import json

    if not _route_optimization_service:
        return json.dumps({"error": "Route optimization service not configured"})

    result = await _route_optimization_service.find_routes(
        from_currency=from_currency,
        to_currency=to_currency,
        amount=amount,
    )

    # Add analysis for the recommended route
    if result.get("recommended"):
        analysis = _route_optimization_service.analyze_route(
            result["recommended"], amount
        )
        result["recommended_analysis"] = analysis

    return json.dumps(result, default=str)
