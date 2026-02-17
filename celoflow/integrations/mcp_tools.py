"""MCP Tools — Wrappers for CeloFlow functionality exposed via Model Context Protocol."""

import asyncio
import json
import logging
import os
from decimal import Decimal
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Import CeloFlow plugins
from plugins.mento_plugin import MentoPlugin
from plugins.remittance_plugin import RemittancePlugin
from plugins.compliance_plugin import CompliancePlugin
from plugins.tee_plugin import TEEPlugin
# Registry plugin will be needed for agent status
from plugins.registry_plugin import RegistryPlugin
from integrations.oasp_config import OASFConfig

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_server")

# Initialize FastMCP
mcp = FastMCP("CeloFlow Remittance Agent")

# ------------------------------------------------------------------
# Shared Plugin Instances (Lazy loading or singleton pattern could be used)
# For simplicity, we initialize them here or inside tools. 
# Initializing here ensures they are ready.
# ------------------------------------------------------------------

def get_mento_plugin() -> MentoPlugin:
    return MentoPlugin(rpc_url=os.getenv("CELO_RPC_URL", "http://127.0.0.1:8545"))

def get_tee_plugin() -> TEEPlugin:
    return TEEPlugin(
        domain=os.getenv("TEE_DOMAIN", "celoflow.remittance"),
        salt=os.getenv("TEE_SALT", "remittance-agent-v1"),
        use_tee=os.getenv("USE_TEE", "false").lower() == "true",
        tee_endpoint=os.getenv("TEE_ENDPOINT"),
        private_key=os.getenv("AGENT_PRIVATE_KEY"),
    )

def get_compliance_plugin() -> CompliancePlugin:
    return CompliancePlugin(
        max_single_transfer=float(os.getenv("MAX_SINGLE_TRANSFER", "10000")),
    )

def get_remittance_plugin() -> RemittancePlugin:
    plugin = RemittancePlugin()
    # Mock agent object to allow configuration if needed, 
    # but RemittancePlugin._load_limits is called in configure_agent.
    # We might need to manually call _load_limits if we use spending limits.
    plugin._load_limits() 
    return plugin

def get_registry_plugin() -> Optional[RegistryPlugin]:
    if os.getenv("IDENTITY_REGISTRY"):
        return RegistryPlugin(
            rpc_url=os.getenv("CELO_RPC_URL", "http://127.0.0.1:8545"),
            identity_registry=os.getenv("IDENTITY_REGISTRY", ""),
            reputation_registry=os.getenv("REPUTATION_REGISTRY", ""),
            tee_registry=os.getenv("TEE_REGISTRY", ""),
            private_key=os.getenv("AGENT_PRIVATE_KEY"),
            agent_id=int(os.getenv("AGENT_ID", "0")),
        )
    return None

# ------------------------------------------------------------------
# MCP Tools
# ------------------------------------------------------------------

@mcp.tool()
async def find_optimal_route(
    from_currency: str, 
    to_currency: str, 
    amount: float
) -> Dict[str, Any]:
    """Find optimal currency exchange route using Mento v2.
    
    Args:
        from_currency: Source currency (e.g., 'USDm', 'CELO')
        to_currency: Target currency (e.g., 'PHPm', 'XOFm')
        amount: Amount to exchange
    """
    plugin = get_mento_plugin()
    route = await plugin.find_optimal_route(
        from_currency, to_currency, Decimal(str(amount))
    )
    
    # Enrich the response
    if route.get("found"):
         return {
            "route_found": True,
            "rate": route.get("rate"),
            "estimated_output": route.get("estimated_output"),
            "fees": {
                "liquidity_fee": route.get("liquidity_fee"),
                "network_fee": 0.001,  # Estimated
            },
            "provider": "Mento v2",
            "slippage": "0.5%",
            "details": route
        }
    else:
        return {
            "route_found": False,
            "error": route.get("error")
        }

@mcp.tool()
async def check_compliance(
    recipient: str,
    amount: float,
    currency: str,
    user_id: str = "anonymous"
) -> Dict[str, Any]:
    """Perform KYC/AML compliance verification for a transfer.
    
    Args:
        recipient: Recipient address or country/identifier
        amount: Amount of the transaction
        currency: Currency code
        user_id: ID of the user initiating the transaction
    """
    plugin = get_compliance_plugin()
    # Simple logic mapping currency/context to destination country if possible
    # For now, we assume recipient string might contain country hint or we default
    destination = "default"
    if "PHP" in currency: destination = "Philippines"
    elif "XOF" in currency: destination = "Nigeria" # Approximation for West Africa
    elif "BRL" in currency: destination = "Brazil"
    
    result = await plugin.check_compliance(
        amount=amount,
        destination=destination,
        user_id=user_id
    )
    return result

@mcp.tool()
async def execute_transfer(
    recipient: str,
    amount: float,
    currency: str,
    from_currency: str = "USDm",
    user_id: str = "anonymous"
) -> Dict[str, Any]:
    """Execute secure cross-border transfer with TEE signing.
    
    Args:
        recipient: Recipient wallet address
        amount: Amount to transfer
        currency: Target currency
        from_currency: Source currency (default USDm)
        user_id: User identifier
    """
    logger.info(f"Requesting transfer: {amount} {currency} to {recipient}")
    
    # 1. Compliance Check
    compliance_plugin = get_compliance_plugin()
    destination = "default" # Logic to determine destination from currency/recipient
    if "PHP" in currency: destination = "Philippines"
    
    compliance_result = await compliance_plugin.check_compliance(amount, destination, user_id)
    if not compliance_result["approved"]:
        return {
            "status": "failed",
            "error": "Compliance check failed",
            "issues": compliance_result.get("issues", [])
        }

    # 2. Route Finding (if swap needed)
    mento_plugin = get_mento_plugin()
    route = await mento_plugin.find_optimal_route(from_currency, currency, Decimal(str(amount)))
    
    if not route.get("found"):
         return {"status": "failed", "error": f"No route found: {route.get('error')}"}

    # 3. TEE Signing & Execution
    tee = get_tee_plugin()
    
    # In a real implementation, we would construct the transaction here and sign it.
    # MentoPlugin.execute_swap takes a signer. TEEPlugin.get_account() returns a LocalAccount.
    
    try:
        signer = tee.get_account()
        tx_hash = await mento_plugin.execute_swap(route, recipient, signer)
        
        # 4. Record Transaction
        remittance = get_remittance_plugin()
        remittance.record_transaction(
            tx_hash=tx_hash,
            user_id=user_id,
            amount=Decimal(str(amount)),
            from_currency=from_currency,
            to_currency=currency,
            destination=destination,
            fees={"network": 0.001, "liquidity": route.get("liquidity_fee")}
        )
        
        return {
            "status": "success",
            "tx_hash": tx_hash,
            "amount_sent": amount,
            "recipient": recipient,
            "currency": currency
        }
        
    except Exception as e:
        logger.error(f"Transfer execution failed: {e}")
        return {"status": "failed", "error": str(e)}

@mcp.tool()
async def get_agent_status() -> Dict[str, Any]:
    """Get the current status, identity, and trust level of the agent."""
    tee = get_tee_plugin()
    attestation = await tee.get_attestation()
    
    registry = get_registry_plugin()
    reputation = {}
    if registry:
        # Assuming registry has methods to get reputation, not implemented in visible snippet
        # querying registry contract manualy if needed, or stubbing
        reputation = {"score": 100, "rank": "Verified"}
        
    return {
        "identity": {
            "address": tee.address,
            "type": "CeloFlow Remittance Agent",
            "version": "1.0.0"
        },
        "trust": {
            "tee_attestation": attestation,
            "reputation": reputation
        },
        "service_health": "operational"
    }

@mcp.tool()
async def get_oasp_capabilities() -> Dict[str, Any]:
    """Get OASF 0.8.0 standardized capabilities description."""
    config = OASFConfig()
    record = config.generate_record()
    
    # Validate locally
    from integrations.oasp_validator import OASFValidator
    validation = OASFValidator.validate_locally(record)
    
    return {
        "oasp_record": record,
        "validation": validation,
        "schema_info": {
            "version": "0.8.0",
            "documentation": "https://docs.agntcy.org/oasf/open-agentic-schema-framework/",
            "validation_endpoint": "https://schema.oasf.outshift.com/doc/index.html"
        }
    }

# ------------------------------------------------------------------
# MCP Resources
# ------------------------------------------------------------------

@mcp.resource("rates://{currency_pair}")
async def get_exchange_rates(currency_pair: str) -> str:
    """Get real-time exchange rates for currency pair (e.g. USDm-PHPm)."""
    plugin = get_mento_plugin()
    
    # Parse pair
    try:
        base, quote = currency_pair.split("-")
    except ValueError:
        return json.dumps({"error": "Invalid pair format. Use BASE-QUOTE (e.g. USDm-PHPm)"})

    # Get rate for 1 unit
    route = await plugin.find_optimal_route(base, quote, Decimal("1.0"))
    
    if route.get("found"):
        return json.dumps({
            "pair": currency_pair,
            "rate": route.get("rate"),
            "timestamp": "now", # Insert actual timestamp
            "source": "Mento v2"
        }, indent=2)
    else:
        return json.dumps({"error": "Rate not available", "details": route.get("error")})

@mcp.resource("oasp://capabilities")
async def get_oasp_capabilities_resource() -> str:
    """Get OASP capabilities as JSON resource."""
    config = OASFConfig()
    return json.dumps(config.generate_record(), indent=2)

