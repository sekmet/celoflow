"""OASP Compliance Tests — Validate OASP configuration and integration."""

import pytest
import json
import os
from integrations.oasp_config import OASFConfig
from integrations.oasp_validator import OASFValidator
from fastapi.testclient import TestClient
from server import app

class TestOASPConfig:
    """Test OASP configuration generation and validation."""
    
    def test_record_structure(self):
        """Test OASP record has required structure."""
        config = OASFConfig()
        record = config.generate_record()
        
        required_fields = ["name", "description", "version", "schema_version", "authors", "created_at", "skills"]
        for field in required_fields:
            assert field in record, f"Missing required field: {field}"
        
        assert record["schema_version"] == "0.8.0"
        assert len(record["skills"]) > 0
        assert len(record["domains"]) > 0
    
    def test_skills_from_catalog(self):
        """Test skills are from official OASP catalog."""
        config = OASFConfig()
        record = config.generate_record()
        
        # Verify skill naming follows catalog pattern
        for skill in record["skills"]:
            assert "/" in skill["name"], f"Skill name should contain category hierarchy: {skill['name']}"
            assert skill["id"] == skill["name"], f"Skill ID should match name: {skill}"
    
    def test_domains_from_catalog(self):
        """Test domains are from official OASP catalog."""
        config = OASFConfig()
        record = config.generate_record()
        
        # Verify domain naming follows catalog pattern
        for domain in record["domains"]:
            assert "/" in domain["name"], f"Domain name should contain category hierarchy: {domain['name']}"
            assert domain["id"] == domain["name"], f"Domain ID should match name: {domain}"
    
    def test_local_validation(self):
        """Test local OASP validation."""
        config = OASFConfig()
        record = config.generate_record()
        
        validation = OASFValidator.validate_locally(record)
        assert validation["valid"], f"Validation failed: {validation['errors']}"
    
    @pytest.mark.asyncio
    async def test_mcp_oasp_integration(self):
        """Test MCP tools expose OASP capabilities."""
        from integrations.mcp_tools import get_oasp_capabilities
        
        capabilities = await get_oasp_capabilities()
        
        assert "oasp_record" in capabilities
        assert "validation" in capabilities
        assert "schema_info" in capabilities
        
        # Verify OASP record is valid
        validation = capabilities["validation"]
        assert validation["valid"], f"OASP record validation failed: {validation['errors']}"

class TestOASPSkillMapping:
    """Test OASP skill to MCP tool mapping."""
    
    def test_skill_tool_mapping(self):
        """Test OASP skills map to correct MCP tools."""
        from integrations.oasp_skill_mapper import OASPSkillMapper
        
        # Test specific mappings
        payment_tools = OASPSkillMapper.get_tools_for_skill("financial_operations/cross_border_payments")
        assert "execute_transfer" in payment_tools
        
        exchange_tools = OASPSkillMapper.get_tools_for_skill("financial_operations/currency_exchange")
        assert "find_optimal_route" in exchange_tools
        
        compliance_tools = OASPSkillMapper.get_tools_for_skill("compliance/risk_assessment")
        assert "check_compliance" in compliance_tools
    
    def test_capability_matrix_generation(self):
        """Test capability matrix generation."""
        from integrations.oasp_skill_mapper import OASPSkillMapper
        
        matrix = OASPSkillMapper.generate_capability_matrix()
        
        assert isinstance(matrix, dict)
        assert len(matrix) > 0
        
        for skill_id, info in matrix.items():
            assert "mcp_tools" in info
            assert "tool_count" in info
            assert isinstance(info["tool_count"], int)

class TestServerEndpoints:
    """Test server endpoints for OASP."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
        
    def test_oasp_endpoint(self, client):
        """Test OASP discovery endpoint."""
        response = client.get("/.well-known/oasp.json")
        assert response.status_code == 200
        data = response.json()
        assert data["schema_version"] == "0.8.0"
        
    def test_agent_card_enrichment(self, client):
        """Test agent card endpoint includes OASP Skills."""
        # Ensure agent_config.json exists or is mocked.
        # It should exist in CWD.
        if not os.path.exists("agent_config.json"):
            pytest.skip("agent_config.json not found")
            
        response = client.get("/.well-known/agent-card.json")
        assert response.status_code == 200
        data = response.json()
        
        assert "capabilities" in data
        assert "oasf" in data["capabilities"]
        assert data["capabilities"]["oasf"]["version"] == "0.8.0"
        assert len(data["capabilities"]["oasf"]["skills"]) > 0
