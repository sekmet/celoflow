"""OASP Skill Mapping — Map OASP skills to MCP tools and capabilities."""

from typing import Dict, List, Any
# We don't necessarily need to import mcp here unless we want to dynamically verify tools exist.
# For now, static mapping is sufficient as per plan.

class OASPSkillMapper:
    """Maps OASP skills to actual MCP tool implementations."""
    
    SKILL_TOOL_MAPPING = {
        "financial_operations/cross_border_payments": ["execute_transfer"],
        "financial_operations/currency_exchange": ["find_optimal_route"],
        "compliance/risk_assessment": ["check_compliance"],
        "blockchain/smart_contract_interaction": ["execute_transfer", "find_optimal_route"],
        "natural_language_processing/multilingual_support": []  # Built into agent
    }
    
    @classmethod
    def get_tools_for_skill(cls, skill_id: str) -> List[str]:
        """Get MCP tools that implement a specific OASP skill."""
        return cls.SKILL_TOOL_MAPPING.get(skill_id, [])
    
    @classmethod
    def get_skill_for_tool(cls, tool_name: str) -> List[str]:
        """Get OASP skills implemented by a specific MCP tool."""
        skills = []
        for skill_id, tools in cls.SKILL_TOOL_MAPPING.items():
            if tool_name in tools:
                skills.append(skill_id)
        return skills
    
    @classmethod
    def generate_capability_matrix(cls) -> Dict[str, Any]:
        """Generate matrix showing skill-to-tool mappings."""
        matrix = {}
        for skill_id, tools in cls.SKILL_TOOL_MAPPING.items():
            matrix[skill_id] = {
                "description": skill_id.replace("/", " → ").title(),
                "mcp_tools": tools,
                "tool_count": len(tools)
            }
        return matrix
