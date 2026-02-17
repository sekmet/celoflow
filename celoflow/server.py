"""Server Entry Point — Unified FastAPI app for CeloFlow Agent & MCP."""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from dotenv import load_dotenv
from services.fee_comparison_service import FeeComparisonService
from services.language_detection import LanguageDetectionService
from services.translation_service import TranslationService
from services.reputation_analytics import ReputationAnalyticsService
from services.wallet_context_service import wallet_context_service
from services.contacts_context_service import contacts_context_service

# Contextwise imports
from contextwise.server import create_app

# Import Agent factory
from agent_factory import create_agent

# Import base system prompt
from main import SYSTEM_PROMPT

# Import MCP server module & OASF
from integrations.mcp_server import mcp_app
from integrations.oasp_config import OASFConfig
from integrations.oasp_validator import OASFValidator

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

# 1. Create the Agent
logger.info("Initializing CeloFlow Agent...")
agent = create_agent()

# 2. Create the FastAPI App using Contextwise (handles lifecycle, logging, etc.)
# This includes the agent's chat endpoints and MCP client management
app = create_app(agent)


# ------------------------------------------------------------------
# Per-request context injection middleware
# ------------------------------------------------------------------
# The contextwise framework's ChatCompletionRequest Pydantic model
# silently drops extra fields like wallet_context and contacts.
# This middleware intercepts /chat and /chat/stream POST requests,
# extracts wallet_context + contacts from the body, updates the
# global services, and dynamically rebuilds agent.instructions
# with fresh context BEFORE contextwise processes the request.
# ------------------------------------------------------------------

def _build_dynamic_instructions() -> str:
    """Rebuild agent instructions with fresh wallet + contacts context."""
    wallet_section = wallet_context_service.get_wallet_context_string()
    contacts_section = contacts_context_service.get_contacts_string()

    return SYSTEM_PROMPT + f"""

## LIVE Wallet Context (auto-injected per request)
{wallet_section}

**IMPORTANT**: The wallet data above is LIVE. Use it directly — do NOT say the wallet is disconnected if it shows "Connected" above.
If balances are shown above, present them to the user immediately without calling any tools.
Only use `get_current_wallet_context()` tool if the data above says "No wallet connected" and you want to double-check.

## LIVE Contacts Context (auto-injected per request)
{contacts_section}

**IMPORTANT**: Use the contacts above to suggest recipients. Do NOT ask for recipient addresses if the contact is listed above.
"""


class WalletContextMiddleware:
    """Raw ASGI middleware — intercept chat requests to inject live context.

    Uses a pure ASGI approach (no BaseHTTPMiddleware) to avoid the
    Starlette body-replay RuntimeError when re-reading the request body.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")

        if method != "POST" or path not in ("/chat", "/chat/stream", "/v1/chat/completions"):
            await self.app(scope, receive, send)
            return

        # Buffer the full request body
        body_parts: list[bytes] = []
        while True:
            message = await receive()
            body_parts.append(message.get("body", b""))
            if not message.get("more_body", False):
                break

        body_bytes = b"".join(body_parts)

        # Process wallet_context and contacts from the body
        try:
            if body_bytes:
                body_data = json.loads(body_bytes)

                wc = body_data.get("wallet_context")
                if wc and isinstance(wc, dict):
                    await wallet_context_service.update_wallet_context(
                        wallet_address=wc.get("wallet_address"),
                        connected=wc.get("connected", False),
                        chain_id=wc.get("chain_id"),
                    )
                    logger.info(
                        "Middleware: wallet context updated (connected=%s, addr=%s)",
                        wc.get("connected"),
                        (wc.get("wallet_address") or "")[:10],
                    )

                contacts_list = body_data.get("contacts")
                if contacts_list and isinstance(contacts_list, list):
                    await contacts_context_service.update_contacts(contacts_list)
                    logger.info(
                        "Middleware: contacts updated (%d contacts)",
                        len(contacts_list),
                    )

                # Dynamically rebuild agent instructions with fresh context
                agent.instructions = _build_dynamic_instructions()

        except Exception as e:
            logger.warning("Middleware: failed to process wallet context: %s", e)

        # Replay the buffered body to downstream handlers
        body_sent = False

        async def replay_receive() -> dict:
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            # After body is sent, wait for disconnect
            return await receive()

        await self.app(scope, replay_receive, send)


app.add_middleware(WalletContextMiddleware)

# 3. Mount the MCP Server (Host) for external tools access
# This exposes the "host" MCP server at /mcp (SSE)
app.mount("/mcp", mcp_app.sse_app())
logger.info("Mounted MCP Server at /mcp")

# ------------------------------------------------------------------
# Health & Well-Known Endpoints (8004scan Compliance)
# ------------------------------------------------------------------

@app.get("/.well-known/mcp.json")
async def mcp_metadata():
    """Return valid MCP server metadata with CORS headers."""
    content = {
        "mcp_version": "1.0",
        "server_name": "CeloFlow Remittance Agent",
        "description": "ERC-8004 remittance agent for Celo with Mento v2 integration",
        "version": "1.0.0",
        "capabilities": {
            "tools": ["find_optimal_route", "execute_transfer", "check_compliance", "get_agent_status"],
            "resources": ["rates"],
            "prompts": ["remittance_assistance"]
        },
        "endpoints": {
            "mcp": os.getenv("MCP_ENDPOINT", "https://api-cflw.contextwise.xyz/mcp"),
            "http": os.getenv("API_BASE_URL", "https://api-cflw.contextwise.xyz")
        },
        "cors": {
            "allowed_origins": ["*"],
            "allowed_methods": ["GET", "POST"],
            "allowed_headers": ["Content-Type", "Authorization"]
        }
    }
    return JSONResponse(
        content=content,
        headers={"Access-Control-Allow-Origin": "*"}
    )

@app.get("/.well-known/oasp.json")
async def oasp_metadata():
    """OASP discovery endpoint following well-known URI pattern."""
    config = OASFConfig()
    record = config.generate_record()
    
    return JSONResponse(
        content=record,
        headers={"Access-Control-Allow-Origin": "*"}
    )

@app.post("/oasp/validate")
async def validate_oasp_record(record: Dict[str, Any]):
    """Validate OASP record."""
    validation = OASFValidator.validate_locally(record)
    
    # Optionally validate against official endpoint
    if validation["valid"]:
        # We invoke this as a background task or await it? 
        # Await it to give immediate feedback.
        official_validation = await OASFValidator.validate_record(record)
        return {
            "local_validation": validation,
            "official_validation": official_validation
        }
    
    return JSONResponse(
        content={"validation": validation},
        status_code=400 if not validation["valid"] else 200
    )

@app.post("/contacts/context")
async def update_contacts_context(contacts_data: Dict[str, Any]):
    """Update contacts context from frontend."""
    try:
        contacts = contacts_data.get("contacts", [])
        
        # Update the contacts context service
        await contacts_context_service.update_contacts(contacts)
        
        return {
            "success": True,
            "contacts_count": len(contacts),
            "active_contacts": len([c for c in contacts if not c.get("blocked", False)])
        }
    except Exception as e:
        logger.error(f"Failed to update contacts context: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/contacts/context")
async def get_contacts_context():
    """Get current contacts context."""
    contacts = contacts_context_service.get_contacts()
    return {
        "contacts_count": len(contacts),
        "active_contacts": len([c for c in contacts if not c.blocked]),
        "favorite_contacts": len([c for c in contacts if c.favorite and not c.blocked]),
        "contacts": [
            {
                "id": c.id,
                "name": c.name,
                "address": c.address,
                "city": c.city,
                "country": c.country,
                "favorite": c.favorite,
                "group": c.group,
                "blocked": c.blocked
            }
            for c in contacts
        ]
    }

@app.post("/wallet/context")
async def update_wallet_context(wallet_data: Dict[str, Any]):
    """Update wallet context from frontend."""
    try:
        wallet_address = wallet_data.get("address")
        connected = wallet_data.get("connected", False)
        chain_id = wallet_data.get("chainId")
        
        # Update the wallet context service
        context = await wallet_context_service.update_wallet_context(
            wallet_address=wallet_address,
            connected=connected,
            chain_id=chain_id
        )
        
        return {
            "success": True,
            "context": {
                "wallet_address": context.wallet_address,
                "connected": context.connected,
                "chain_id": context.chain_id,
                "balances": context.balances
            }
        }
    except Exception as e:
        logger.error(f"Failed to update wallet context: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/wallet/context")
async def get_wallet_context():
    """Get current wallet context."""
    context = wallet_context_service.get_wallet_context()
    return {
        "wallet_address": context.wallet_address,
        "connected": context.connected,
        "chain_id": context.chain_id,
        "balances": context.balances
    }

@app.get("/.well-known/agent-card.json")
async def agent_card():
    """Return ERC-8004 agent card metadata."""
    try:
        with open("agent_config.json", "r") as f:
            config = json.load(f)
            
        # Enrich with OASF metadata
        oasp_config = OASFConfig()
        record = oasp_config.generate_record()
        
        # Add OASF capability to capabilities if not present
        if "capabilities" not in config:
            config["capabilities"] = {}
            
        config["capabilities"]["oasf"] = {
            "version": record["schema_version"],
            "domains": [d["name"] for d in record["domains"]],
            "skills": [
                {
                    "name": s["name"].split("/")[-1],
                    "description": s["description"],
                    "oasp_id": s["id"],
                    "category": s["name"].split("/")[0]
                }
                for s in record["skills"]
            ]
        }
        
        # Add dynamic status
        config["status"] = {
            "active": True,
            "x402": True
        }
        
        # Add EVM specific info if missing
        if "evmChains" not in config:
             config["evmChains"] = [
                {
                    "name": "Celo Sepolia",
                    "chainId": 44787
                }
            ]

        # Add registration info from env if available
        if os.getenv("AGENT_ID"):
             config["registration"] = {
                 "agentId": int(os.getenv("AGENT_ID")),
                 "agentRegistry": os.getenv("IDENTITY_REGISTRY")
             }
             
        # Add trust info
        config["trust"] = {
            "supportedTrust": ["tee-attestation", "reputation"],
            "teeAttestation": True,
            "reputation": True
        }

        return JSONResponse(
            content=config,
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except FileNotFoundError:
        return JSONResponse(
            content={"error": "Agent configuration not found"},
            status_code=500
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting Unified CeloFlow Server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
