from integrations.mcp_tools import mcp
print(dir(mcp))
try:
    print("mcp.app:", mcp.app)
except:
    print("No mcp.app")
