"""MCP Server — Helper module to expose the FastMCP application."""

from integrations.mcp_tools import mcp

# This variable is imported by the main FastAPI app to mount the MCP server
mcp_app = mcp
