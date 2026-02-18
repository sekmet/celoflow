"""Server Entry Point — Unified FastAPI app for CeloFlow Agent & MCP."""

import json
import logging
import os
import time
import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.concurrency import iterate_in_threadpool
from dotenv import load_dotenv
from services.fee_comparison_service import FeeComparisonService
from services.language_detection import LanguageDetectionService
from services.translation_service import TranslationService
from services.reputation_analytics import ReputationAnalyticsService
from services.wallet_context_service import wallet_context_service
from services.contacts_context_service import contacts_context_service
from services.auth_service import AuthService, AuthConfig
from services.real_time_status import RealTimeStatusService
from middleware.auth_middleware import AuthMiddleware

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

# 3. Initialize Authentication Service
auth_config = AuthConfig.from_env()
# Wire TEE plugin from agent's plugins list for attestation support
_tee_plugin = None
for p in getattr(agent, 'plugins', []):
    if getattr(p, 'name', '') == 'tee':
        _tee_plugin = p
        break
auth_service = AuthService(config=auth_config, tee_plugin=_tee_plugin)
logger.info("AuthService initialized (tee_attestation=%s)", auth_config.enable_tee_attestation)


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

**CRITICAL RULE — WALLET**: The wallet data above is LIVE and REAL. Use it directly.
- Do NOT say the wallet is disconnected if it shows "Connected" above.
- If balances are shown above, present them to the user immediately without calling any tools.
- Only use `get_current_wallet_context()` tool if the data above says "No wallet connected".

## LIVE User Contacts (auto-injected per request)
{contacts_section}

**CRITICAL RULE — CONTACTS**: The contacts listed above are the user's REAL saved contacts.
- You MUST acknowledge these contacts when the user asks about them.
- Do NOT say "I don't see contacts" or "no contacts list" — the contacts ARE listed above.
- When the user mentions a contact by name (e.g. "send to Maria"), match it to the contact above and use their wallet address directly.
- Always show the contact's name, city, country, and wallet address when referencing them.
- If the user asks "who are my contacts", list ALL contacts shown above with their details.
"""


def _build_context_message() -> str:
    """Build a concise context message to inject into the conversation messages."""
    parts = []

    wallet_ctx = wallet_context_service.get_wallet_context()
    if wallet_ctx and wallet_ctx.connected:
        parts.append(f"[SYSTEM CONTEXT] User wallet {wallet_ctx.wallet_address} is connected on chain {wallet_ctx.chain_id}.")
        if wallet_ctx.balances:
            non_zero = {k: v for k, v in wallet_ctx.balances.items() if float(v) > 0}
            if non_zero:
                bal_str = ", ".join(f"{v} {k}" for k, v in list(non_zero.items())[:10])
                parts.append(f"Balances: {bal_str}")

    contacts_str = contacts_context_service.get_contacts_string()
    if contacts_str and "No contacts" not in contacts_str:
        parts.append(f"\n[USER CONTACTS]\n{contacts_str}")
        parts.append("RULE: When the user mentions a contact name, use their wallet address from the list above. Do NOT say you cannot see contacts.")

    # Inject transfer execution guidance
    parts.append(
        "\n[TRANSFER GUIDANCE]\n"
        "When the user requests a token transfer (e.g. 'Send 1 BRLm to Charles'), "
        "use the `send_token` tool with the contact's wallet address from the list above. "
        "For cross-currency swaps, use `execute_transfer`. "
        "Execute transfers directly without asking for extra confirmation — the user expects immediate action."
    )

    return "\n".join(parts) if parts else ""


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

                # Contextwise only extracts the LAST user message string
                # via agent.chat_async(message=user_message).  System messages
                # in the array are ignored.  To guarantee the LLM sees live
                # context, we prepend it directly to the user's message.
                context_prefix = _build_context_message()
                if context_prefix:
                    messages = body_data.get("messages", [])
                    # Find the last user message and prepend context
                    for i in range(len(messages) - 1, -1, -1):
                        if messages[i].get("role") == "user":
                            original = messages[i]["content"]
                            messages[i]["content"] = (
                                f"[LIVE CONTEXT — use this data to answer]\n"
                                f"{context_prefix}\n"
                                f"[END CONTEXT]\n\n"
                                f"{original}"
                            )
                            break
                    body_data["messages"] = messages
                    body_bytes = json.dumps(body_data).encode("utf-8")
                    logger.info(
                        "Middleware: prepended context (%d chars) to user message",
                        len(context_prefix),
                    )

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

# 4. Add Authentication Middleware (runs BEFORE WalletContextMiddleware in ASGI stack)
# In Starlette, the LAST added middleware runs FIRST on incoming requests.
app.add_middleware(AuthMiddleware, auth_service=auth_service)

# 5. Initialize Real-time Status Service
from services.real_time_status import real_time_status_service
real_time_status_service.start_monitoring()
logger.info("Real-time status monitoring started")

# 5. Mount the MCP Server (Host) for external tools access
# This exposes the "host" MCP server at /mcp (SSE)
app.mount("/mcp", mcp_app.sse_app())
logger.info("Mounted MCP Server at /mcp")

# ------------------------------------------------------------------
# Authentication Endpoints
# ------------------------------------------------------------------

@app.post("/auth/login")
async def auth_login(request: Request):
    """Authenticate and receive JWT tokens.

    Accepts JSON body with optional fields:
    - api_key: API key for service-to-service auth
    - wallet_address: Connected wallet address
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    origin = request.headers.get("origin")
    api_key = body.get("api_key") or request.headers.get("x-api-key")
    wallet_address = body.get("wallet_address")

    result = await auth_service.authenticate(
        origin=origin,
        api_key=api_key,
        wallet_address=wallet_address,
    )

    if not result.success:
        return JSONResponse(
            content={"error": result.message, "success": False},
            status_code=401,
            headers={"Access-Control-Allow-Origin": origin or "*"},
        )

    return JSONResponse(
        content={
            "success": True,
            "message": result.message,
            "access_token": result.access_token,
            "refresh_token": result.refresh_token,
            "expires_in": result.expires_in,
            "token_type": result.token_type,
            "tee_verified": result.tee_verified,
        },
        headers={"Access-Control-Allow-Origin": origin or "*"},
    )


@app.post("/auth/refresh")
async def auth_refresh(request: Request):
    """Refresh an access token using a refresh token.

    Accepts JSON body with:
    - refresh_token: The refresh token to use
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={"error": "Invalid request body", "success": False},
            status_code=400,
        )

    refresh_token = body.get("refresh_token")
    if not refresh_token:
        return JSONResponse(
            content={"error": "refresh_token is required", "success": False},
            status_code=400,
        )

    origin = request.headers.get("origin")
    success, new_access_token, error = auth_service.refresh_access_token(
        refresh_token=refresh_token,
        origin=origin,
    )

    if not success:
        return JSONResponse(
            content={"error": error, "success": False},
            status_code=401,
        )

    return JSONResponse(
        content={
            "success": True,
            "access_token": new_access_token,
            "expires_in": auth_service.config.access_token_expiry,
            "token_type": "Bearer",
        },
        headers={"Access-Control-Allow-Origin": origin or "*"},
    )


@app.post("/auth/logout")
async def auth_logout(request: Request):
    """Revoke the current access token (logout).

    Reads the Bearer token from the Authorization header.
    """
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        return JSONResponse(
            content={"error": "No token provided", "success": False},
            status_code=400,
        )

    token = authorization[7:].strip()
    success, message = auth_service.revoke_token(token)

    return JSONResponse(
        content={"success": success, "message": message},
        status_code=200 if success else 400,
    )


@app.get("/auth/attestation")
async def auth_attestation():
    """Get TEE attestation information.

    Returns attestation status and details. When ENABLE_TEE_ATTESTATION=true,
    includes the full TEE quote for verification.
    """
    info = await auth_service.get_attestation_info()
    return JSONResponse(
        content=info,
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/auth/status")
async def auth_status(request: Request):
    """Check authentication status for the current request."""
    auth_info = request.scope.get("auth", {})
    if not auth_info:
        return JSONResponse(
            content={
                "authenticated": False,
                "message": "Not authenticated",
            },
            status_code=401,
        )

    return JSONResponse(
        content={
            "authenticated": True,
            "method": auth_info.get("method"),
            "subject": auth_info.get("subject"),
            "tee_verified": auth_info.get("tee_verified", False),
            "scopes": auth_info.get("scopes", []),
        }
    )


# ------------------------------------------------------------------
# Real-time Status Endpoints
# ------------------------------------------------------------------

@app.get("/status/stream")
async def status_stream():
    """Server-Sent Events endpoint for real-time operation status.
    
    Provides live updates of backend operations including:
    - Auto-swaps (hop1/hop2 progress)
    - Balance checks and token swaps
    - Transfer execution with transaction details
    - TEE attestation and compliance checks
    """
    async def event_generator():
        # Subscribe to status updates
        queue = await real_time_status_service.subscribe()
        
        try:
            # Send initial connection event
            connection_data = {
                'type': 'connection',
                'message': 'Real-time status connected',
                'timestamp': time.time()
            }
            yield f"event: connected\ndata: {json.dumps(connection_data)}\n\n"
            
            # Send current status if available
            current_status = real_time_status_service.get_current_status()
            if current_status:
                yield f"event: status\ndata: {json.dumps(current_status)}\n\n"
            
            # Listen for status updates
            while True:
                try:
                    # Wait for status update with timeout
                    status_event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    yield f"event: status\ndata: {json.dumps(status_event)}\n\n"
                    
                except asyncio.TimeoutError:
                    # Send heartbeat every 30 seconds
                    heartbeat_data = {
                        'type': 'heartbeat',
                        'timestamp': time.time()
                    }
                    yield f"event: heartbeat\ndata: {json.dumps(heartbeat_data)}\n\n"
                    
        except asyncio.CancelledError:
            # Client disconnected
            logger.info("Status stream client disconnected")
            
        finally:
            # Clean up subscription
            real_time_status_service.unsubscribe(queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        }
    )


@app.get("/status/current")
async def status_current():
    """Get current operation status."""
    current_status = real_time_status_service.get_current_status()
    return JSONResponse(
        content={
            "current": current_status,
            "timestamp": time.time()
        },
        headers={"Access-Control-Allow-Origin": "*"}
    )


@app.get("/status/history")
async def status_history(limit: int = 50):
    """Get recent status history."""
    if limit > 200:
        limit = 200  # Cap maximum history
    
    history = real_time_status_service.get_status_history(limit)
    return JSONResponse(
        content={
            "history": history,
            "count": len(history),
            "timestamp": time.time()
        },
        headers={"Access-Control-Allow-Origin": "*"}
    )


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
