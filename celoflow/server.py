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
from services.user_signing_service import UserSigningService
from middleware.auth_middleware import AuthMiddleware

# Contextwise imports
from contextwise.server import create_app

# Import Agent factory
from agent_factory import create_agent

# Import main to access the full create_agent function
import main

# Import base system prompt and services
from main import SYSTEM_PROMPT
from tools import remittance_tools

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
agent = main.create_agent()

# 2. Create the FastAPI App using Contextwise (handles lifecycle, logging, etc.)
# This includes the agent's chat endpoints and MCP client management
app = create_app(agent)

# 3. Initialize Authentication Service
auth_config = AuthConfig.from_env()
# Add earnings and transfer preview endpoints to public paths (not sensitive)
public_paths = auth_config.public_paths + [
    "/api/agent/earnings",
    "/transfer/preview",
    "/transfer/prepare",
    "/transfer/execute",
    "/transfer/quick-prepare",
    "/api/transfers",
    "/wallet/context",
    "/contacts/context",
    "/api/settings",
    "/chat",
    "/v1/chat/completions",
]
auth_config.public_paths = public_paths
# Wire TEE plugin from agent's plugins list for attestation support
_tee_plugin = None
for p in getattr(agent, 'plugins', []):
    if getattr(p, 'name', '') == 'tee':
        _tee_plugin = p
        break
auth_service = AuthService(config=auth_config, tee_plugin=_tee_plugin)
logger.info("AuthService initialized (tee_attestation=%s)", auth_config.enable_tee_attestation)

# 3b. Initialize User Signing Service
_mento_plugin = None
for p in getattr(agent, 'plugins', []):
    if getattr(p, 'name', '') == 'mento':
        _mento_plugin = p
        break
user_signing_service = UserSigningService(mento_plugin=_mento_plugin, tee_plugin=_tee_plugin)
logger.info("UserSigningService initialized")

# 3c. Grab SchedulerPlugin reference for REST API
_scheduler_plugin = None
for p in getattr(agent, 'plugins', []):
    if getattr(p, 'name', '') == 'scheduler':
        _scheduler_plugin = p
        break
logger.info("SchedulerPlugin reference obtained: %s", _scheduler_plugin is not None)

# 3d. In-memory user settings store (keyed by user_id / wallet address)
_user_settings: Dict[str, Dict[str, Any]] = {}


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

def get_user_setting(user_id: str, key: str, default=None):
    """Get a specific user setting value."""
    return _user_settings.get(user_id, {}).get(key, default)


def get_user_fee_comparison_preference(user_id: str = "default") -> bool:
    """Get user's fee comparison preference (defaults to True)."""
    return get_user_setting(user_id, "showFeeComparison", True)


def _build_dynamic_instructions() -> str:
    """Rebuild agent instructions with fresh wallet + contacts context.

    Conditionally includes fee comparison instructions based on the user's
    showFeeComparison preference stored in _user_settings.
    """
    wallet_section = wallet_context_service.get_wallet_context_string()
    contacts_section = contacts_context_service.get_contacts_string()

    # Determine fee comparison preference (default True for backward compat)
    show_fee_comparison = get_user_fee_comparison_preference("default")

    # Build fee comparison section conditionally
    if show_fee_comparison:
        fee_comparison_section = """
## Fee Comparison Behavior (User Preference: ENABLED)
- **ALWAYS** show fee comparisons with traditional providers (Western Union, Wise, Remitly, MoneyGram) when discussing transfers.
- Use `compare_fees_with_providers` to get real-time comparisons before or alongside transfer execution.
- Highlight savings vs traditional services prominently.
- Show the data source (realtime/static) and confidence scores for transparency.
"""
    else:
        fee_comparison_section = """
## Fee Comparison Behavior (User Preference: DISABLED)
- The user has **disabled** fee comparisons. Do NOT show fee comparison tables or call `compare_fees_with_providers` unless explicitly asked.
- Execute transfers directly without showing provider comparisons.
- If the user explicitly asks "compare fees" or "show fee comparison", you may show it once.
"""

    return SYSTEM_PROMPT + fee_comparison_section + f"""

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

    # Inject transfer execution guidance with universal auto-swap info
    parts.append(
        "\n[TRANSFER GUIDANCE — UNIVERSAL AUTO-SWAP]\n"
        "CRITICAL: `send_token` has BUILT-IN AUTO-SWAP for ALL 19 supported tokens. "
        "When the user says 'Send X [TOKEN] to [NAME]', ALWAYS use `send_token` directly. "
        "If the agent wallet lacks the target token, `send_token` automatically swaps "
        "CELO → USDm → target token via Mento v2 (transparent to user).\n"
        "Supported tokens: USDm, EURm, BRLm, KESm, XOFm, PHPm, COPm, GBPm, CADm, "
        "AUDm, ZARm, GHSm, NGNm, JPYm, CHFm, CELO, USDT, axlUSDC.\n"
        "NEVER suggest manual currency conversion — auto-swap handles it automatically.\n"
        "Use contact wallet addresses from the list above. Execute immediately without extra confirmation."
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

                # Process user_settings
                user_settings = body_data.get("user_settings")
                if user_settings and isinstance(user_settings, dict):
                    # Store user settings globally for agent access
                    user_id = user_settings.get("userId", user_settings.get("user_id", "default"))
                    _user_settings[user_id] = {
                        **_user_settings.get(user_id, {}),
                        **{k: v for k, v in user_settings.items() if k not in ("userId", "user_id")}
                    }
                    logger.info(
                        "Middleware: user settings updated for user %s (showFeeComparison=%s)",
                        user_id,
                        user_settings.get("showFeeComparison", "not set"),
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

# ------------------------------------------------------------------
# User Wallet Signing Endpoints
# ------------------------------------------------------------------

@app.post("/transfer/prepare")
async def prepare_user_transfer(request: Request):
    """Prepare an unsigned transfer for user wallet signing.

    Accepts JSON body with:
    - user_address: Connected wallet address
    - recipient_address: Recipient wallet address
    - amount: Amount of tokens to send
    - token: Token symbol (e.g. BRLm, ZARm, USDm)
    - chain_id: Optional chain ID (default Celo Sepolia)

    Returns transaction data for the user's wallet to sign.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={"error": "Invalid request body"},
            status_code=400,
        )

    user_address = body.get("user_address")
    recipient_address = body.get("recipient_address")
    amount = body.get("amount")
    token = body.get("token")
    chain_id = body.get("chain_id", 44787)

    if not all([user_address, recipient_address, amount, token]):
        return JSONResponse(
            content={"error": "Missing required fields: user_address, recipient_address, amount, token"},
            status_code=400,
        )

    result = await user_signing_service.prepare_transfer(
        user_address=user_address,
        recipient_address=recipient_address,
        amount=float(amount),
        token=token,
        chain_id=int(chain_id),
    )

    status_code = 200 if "error" not in result else 400
    return JSONResponse(
        content=result,
        status_code=status_code,
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/transfer/execute")
async def execute_user_transfer(request: Request):
    """Execute a user-signed transfer by broadcasting it.

    Accepts JSON body with:
    - transfer_id: The transfer ID from /transfer/prepare
    - signed_tx: The signed transaction hex from user's wallet
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={"error": "Invalid request body"},
            status_code=400,
        )

    transfer_id = body.get("transfer_id")
    signed_tx = body.get("signed_tx")

    if not transfer_id or not signed_tx:
        return JSONResponse(
            content={"error": "Missing required fields: transfer_id, signed_tx"},
            status_code=400,
        )

    result = await user_signing_service.execute_signed_transfer(
        transfer_id=transfer_id,
        signed_tx_hex=signed_tx,
    )

    status_code = 200 if result.get("status") == "success" else 400
    return JSONResponse(
        content=result,
        status_code=status_code,
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/transfer/{transfer_id}")
async def get_transfer_status(transfer_id: str):
    """Get the status of a prepared transfer."""
    result = user_signing_service.get_transfer(transfer_id)
    if not result:
        return JSONResponse(
            content={"error": "Transfer not found"},
            status_code=404,
            headers={"Access-Control-Allow-Origin": "*"},
        )
    return JSONResponse(
        content=result,
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/transfer/{transfer_id}/reject")
async def reject_transfer(transfer_id: str):
    """Reject/cancel a pending transfer."""
    result = user_signing_service.reject_transfer(transfer_id)
    return JSONResponse(
        content=result,
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/transfer/pending/{user_address}")
async def get_pending_transfers(user_address: str):
    """Get all pending transfers for a user address."""
    transfers = user_signing_service.get_pending_transfers(user_address)
    return JSONResponse(
        content={"transfers": transfers, "count": len(transfers)},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/transfer/quick-prepare")
async def quick_prepare_transfer(request: Request):
    """Prepare a quick transfer from the QuickTransferModal UI.

    Identical to /transfer/prepare but also accepts an optional memo field
    and returns a pre-computed USD estimate for display.

    Accepts JSON body with:
    - user_address: Connected wallet address
    - recipient_address: Recipient wallet address
    - amount: Amount of tokens to send
    - token: Token symbol (e.g. BRLm, ZARm, USDm)
    - chain_id: Optional chain ID (default Celo Sepolia 44787)
    - memo: Optional transfer note (stored for audit, not on-chain)

    Returns transaction data for the user's wallet to sign plus metadata.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={"error": "Invalid request body"},
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    user_address = body.get("user_address")
    recipient_address = body.get("recipient_address")
    amount = body.get("amount")
    token = body.get("token")
    chain_id = body.get("chain_id", 44787)
    memo = body.get("memo", "")

    if not all([user_address, recipient_address, amount, token]):
        return JSONResponse(
            content={"error": "Missing required fields: user_address, recipient_address, amount, token"},
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    try:
        float_amount = float(amount)
        if float_amount <= 0:
            return JSONResponse(
                content={"error": "Amount must be greater than 0"},
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*"},
            )
    except (TypeError, ValueError):
        return JSONResponse(
            content={"error": "Invalid amount value"},
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    result = await user_signing_service.prepare_transfer(
        user_address=user_address,
        recipient_address=recipient_address,
        amount=float_amount,
        token=token,
        chain_id=int(chain_id),
    )

    # Attach memo to result metadata (not broadcast on-chain)
    if memo:
        result["memo"] = str(memo)[:120]

    logger.info(
        "Quick transfer prepared: user=%s recipient=%s amount=%s %s memo=%s",
        (user_address or "")[:10],
        (recipient_address or "")[:10],
        float_amount,
        token,
        bool(memo),
    )

    status_code = 200 if "error" not in result else 400
    return JSONResponse(
        content=result,
        status_code=status_code,
        headers={"Access-Control-Allow-Origin": "*"},
    )


# ------------------------------------------------------------------
# Transfer Preview Endpoints (two-step transfer flow)
# ------------------------------------------------------------------

@app.post("/transfer/preview")
async def create_transfer_preview(request: Request):
    """Generate a transfer preview — Step 1 of the two-step transfer flow.

    Returns route, fee breakdown, traditional provider comparisons,
    and a preview_id valid for 30 seconds to link with execution.

    Accepts JSON body with:
    - recipient_address: Recipient wallet address (0x...)
    - amount: Transfer amount
    - token: Token to send (e.g. BRLm, ZARm, USDm)
    - destination_country: Optional destination country for fee comparison
    - from_currency: Optional source currency (default USD)
    - user_id: Optional user identifier
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={"error": "Invalid request body"},
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    recipient_address = body.get("recipient_address")
    amount = body.get("amount")
    token = body.get("token")
    destination_country = body.get("destination_country", "")
    from_currency = body.get("from_currency", "USD")
    user_id = body.get("user_id", "unknown")

    if not all([recipient_address, amount, token]):
        return JSONResponse(
            content={"error": "Missing required fields: recipient_address, amount, token"},
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    try:
        float_amount = float(amount)
        if float_amount <= 0:
            return JSONResponse(
                content={"error": "Amount must be greater than 0"},
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*"},
            )
    except (TypeError, ValueError):
        return JSONResponse(
            content={"error": "Invalid amount value"},
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    transfer_preview_service = getattr(remittance_tools, '_transfer_preview_service', None)
    if not transfer_preview_service:
        return JSONResponse(
            content={"error": "Transfer preview service not available"},
            status_code=503,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    try:
        preview = await transfer_preview_service.preview_transfer(
            recipient=str(recipient_address),
            amount=float_amount,
            token=str(token),
            destination_country=str(destination_country),
            from_currency=str(from_currency),
            user_id=str(user_id),
        )
        logger.info(
            "Transfer preview created via REST: id=%s, %s %s → %s",
            preview.get("preview_id", "?"),
            float_amount,
            token,
            (str(recipient_address))[:10],
        )
        return JSONResponse(
            content=preview,
            headers={"Access-Control-Allow-Origin": "*"},
        )
    except Exception as e:
        logger.error("Transfer preview failed: %s", e)
        return JSONResponse(
            content={"error": f"Preview generation failed: {str(e)}"},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )


@app.get("/transfer/preview/{preview_id}")
async def get_transfer_preview(preview_id: str):
    """Validate and retrieve a cached transfer preview by ID.

    Returns validation status and remaining seconds until expiry.
    Use this before executing a transfer to confirm the preview is still valid.
    """
    transfer_preview_service = getattr(remittance_tools, '_transfer_preview_service', None)
    if not transfer_preview_service:
        return JSONResponse(
            content={"error": "Transfer preview service not available"},
            status_code=503,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    validation = transfer_preview_service.validate_preview(preview_id)
    status_code = 200 if validation.get("valid") else 404
    return JSONResponse(
        content=validation,
        status_code=status_code,
        headers={"Access-Control-Allow-Origin": "*"},
    )


# ------------------------------------------------------------------
# Scheduled Transfers API Endpoints
# ------------------------------------------------------------------

@app.get("/api/transfers/scheduled")
async def get_scheduled_transfers(user_id: str = ""):
    """List all scheduled recurring transfers for a user."""
    if not _scheduler_plugin:
        return JSONResponse(
            content={"transfers": [], "count": 0, "error": "Scheduler not available"},
            headers={"Access-Control-Allow-Origin": "*"},
        )
    user_jobs = [
        j for j in _scheduler_plugin.jobs.values()
        if not user_id or j.get("user_id") == user_id
    ]
    return JSONResponse(
        content={"transfers": user_jobs, "count": len(user_jobs)},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/api/transfers/schedule")
async def schedule_recurring_transfer(request: Request):
    """Create a new recurring transfer schedule."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={"error": "Invalid request body"},
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    recipient = body.get("recipient")
    amount = body.get("amount")
    currency = body.get("currency", "USDm")
    frequency = body.get("frequency", "monthly")
    user_id = body.get("user_id", "default")

    if not recipient or not amount:
        return JSONResponse(
            content={"error": "Missing required fields: recipient, amount"},
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    if not _scheduler_plugin:
        return JSONResponse(
            content={"error": "Scheduler not available"},
            status_code=503,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    result = await _scheduler_plugin.schedule_transfer_action(
        recipient_id=str(recipient),
        amount=str(amount),
        currency=str(currency),
        frequency=str(frequency),
        user_id=str(user_id),
    )

    success = result.startswith("✅")
    return JSONResponse(
        content={"success": success, "message": result},
        status_code=200 if success else 400,
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.delete("/api/transfers/scheduled/{job_id}")
async def cancel_scheduled_transfer(job_id: str):
    """Cancel a scheduled recurring transfer by job ID."""
    if not _scheduler_plugin:
        return JSONResponse(
            content={"error": "Scheduler not available"},
            status_code=503,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    result = await _scheduler_plugin.cancel_transfer_action(job_id)
    success = result.startswith("✅")
    return JSONResponse(
        content={"success": success, "message": result},
        status_code=200 if success else 404,
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/api/transfers/history")
async def get_transfer_history(user_id: str = "", limit: int = 50):
    """Get transfer execution history for a user."""
    if not _scheduler_plugin:
        return JSONResponse(
            content={"history": [], "count": 0},
            headers={"Access-Control-Allow-Origin": "*"},
        )

    all_history: List[Dict[str, Any]] = []
    for job_id, job_info in _scheduler_plugin.jobs.items():
        if user_id and job_info.get("user_id") != user_id:
            continue
        executions = _scheduler_plugin.get_execution_history(job_id, limit=limit)
        for entry in executions:
            all_history.append({
                **entry,
                "job_id": job_id,
                "recipient": job_info.get("recipient"),
                "currency": job_info.get("currency"),
                "frequency": job_info.get("frequency"),
            })

    all_history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return JSONResponse(
        content={"history": all_history[:limit], "count": len(all_history)},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/api/transfers/execute")
async def execute_agent_transfer(request: Request):
    """Execute an immediate transfer via the TEE agent wallet."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={"error": "Invalid request body"},
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    recipient = body.get("recipient")
    amount = body.get("amount")
    currency = body.get("currency", "USDm")
    user_id = body.get("user_id", "default")

    if not recipient or not amount:
        return JSONResponse(
            content={"error": "Missing required fields: recipient, amount"},
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    # Use the agent's chat to execute the transfer
    try:
        from tools import remittance_tools
        result = await remittance_tools.send_token(
            recipient_address=str(recipient),
            amount=float(amount),
            token=str(currency),
        )
        return JSONResponse(
            content={"success": True, "result": result, "user_id": user_id},
            headers={"Access-Control-Allow-Origin": "*"},
        )
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )


# ------------------------------------------------------------------
# User Settings API Endpoints
# ------------------------------------------------------------------

_DEFAULT_SETTINGS: Dict[str, Any] = {
    "showFeeComparison": True,
    "defaultCurrency": "USDm",
    "language": "en",
    "theme": "auto",
    "notifications": {
        "transfers": True,
        "recurring": True,
        "failures": True,
    },
    "privacy": {
        "shareAnalytics": False,
        "saveHistory": True,
    },
}


@app.get("/api/settings")
async def get_user_settings(user_id: str = "default"):
    """Get user settings/preferences."""
    settings = _user_settings.get(user_id, {})
    merged = {**_DEFAULT_SETTINGS, **settings}
    merged["userId"] = user_id
    return JSONResponse(
        content=merged,
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.put("/api/settings")
async def update_user_settings(request: Request):
    """Update user settings/preferences."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={"error": "Invalid request body"},
            status_code=400,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    user_id = body.get("userId", body.get("user_id", "default"))
    existing = _user_settings.get(user_id, {})

    # Deep merge notifications and privacy sub-objects
    updated = {**existing}
    for key, value in body.items():
        if key in ("userId", "user_id"):
            continue
        if isinstance(value, dict) and isinstance(updated.get(key), dict):
            updated[key] = {**updated.get(key, {}), **value}
        else:
            updated[key] = value

    _user_settings[user_id] = updated
    merged = {**_DEFAULT_SETTINGS, **updated, "userId": user_id}
    return JSONResponse(
        content={"success": True, "settings": merged},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/api/agent/earnings")
async def get_agent_earnings_api(agent_id: int = 0):
    """Get earnings summary for an agent."""
    payment_reward_service = getattr(remittance_tools, '_payment_reward_service', None)
    
    if not payment_reward_service:
        return JSONResponse(
            content={"error": "Payment reward service not available"},
            status_code=503,
            headers={"Access-Control-Allow-Origin": "*"},
        )
    
    try:
        earnings = payment_reward_service.get_agent_earnings(agent_id)
        return JSONResponse(
            content=earnings,
            headers={"Access-Control-Allow-Origin": "*"},
        )
    except Exception as e:
        logger.error(f"Error fetching agent earnings: {e}")
        return JSONResponse(
            content={"error": "Failed to fetch earnings", "details": str(e)},
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"},
        )


# ------------------------------------------------------------------
# Well-Known & Agent Card Endpoints
# ------------------------------------------------------------------

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
