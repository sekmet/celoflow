"""Server Entry Point — Unified FastAPI app for CeloFlow Agent & MCP."""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Contextwise imports
from contextwise.server import create_app

# Import Agent factory
from agent_factory import create_agent

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
            "mcp": os.getenv("MCP_ENDPOINT", "https://api.celoflow.com/mcp"),
            "http": os.getenv("API_BASE_URL", "https://api.celoflow.com")
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
