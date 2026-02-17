"""OASF Configuration — Open Agentic Schema Framework compliance for CeloFlow."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json
import os

class OASFConfig:
    """Manages OASF 0.8.0 compliant configuration for CeloFlow agent."""
    
    SCHEMA_VERSION = "0.8.0"
    
    def __init__(self, agent_name: str = "CeloFlow Remittance Agent"):
        self.agent_name = agent_name
        self.version = "1.0.0"
        self.created_at = datetime.now(timezone.utc).isoformat()
        
    def generate_record(self) -> Dict[str, Any]:
        """Generate complete OASF record for CeloFlow."""
        return {
            "name": self.agent_name,
            "description": "AI-powered cross-border remittance assistant on Celo blockchain with real-time Mento v2 rates, TEE-backed security, and multi-language support",
            "version": self.version,
            "schema_version": self.SCHEMA_VERSION,
            "authors": [
                {
                    "name": "CeloFlow Team",
                    "email": "team@celoflow.com"
                }
            ],
            "created_at": self.created_at,
            "skills": self._get_skills(),
            "domains": self._get_domains(),
            "locators": self._get_locators(),
            "modules": self._get_modules()
        }
    
    def _get_skills(self) -> List[Dict[str, Any]]:
        """Define OASF skills from official catalog."""
        return [
            {
                "name": "financial_operations/cross_border_payments",
                "id": "financial_operations/cross_border_payments",
                "description": "Execute secure cross-border payments with blockchain settlement"
            },
            {
                "name": "financial_operations/currency_exchange", 
                "id": "financial_operations/currency_exchange",
                "description": "Find optimal currency exchange routes using decentralized protocols"
            },
            {
                "name": "blockchain/smart_contract_interaction",
                "id": "blockchain/smart_contract_interaction", 
                "description": "Interact with smart contracts for financial operations"
            },
            {
                "name": "compliance/risk_assessment",
                "id": "compliance/risk_assessment",
                "description": "Perform KYC/AML compliance checks and risk assessment"
            },
            {
                "name": "natural_language_processing/multilingual_support",
                "id": "natural_language_processing/multilingual_support",
                "description": "Provide multilingual user interface and support"
            }
        ]
    
    def _get_domains(self) -> List[Dict[str, Any]]:
        """Define OASF domains from official catalog."""
        return [
            {
                "name": "finance/financial_services",
                "id": "finance/financial_services",
                "description": "Financial services and payment processing"
            },
            {
                "name": "technology/blockchain",
                "id": "technology/blockchain", 
                "description": "Blockchain technology and cryptocurrency operations"
            },
            {
                "name": "technology/decentralized_finance",
                "id": "technology/decentralized_finance",
                "description": "Decentralized finance protocols and applications"
            }
        ]
    
    def _get_locators(self) -> List[Dict[str, Any]]:
        """Define source code and deployment locators."""
        return [
            {
                "type": "source_code",
                "url": "https://github.com/celoflow/celoflow-agent",
                "description": "Main source code repository"
            },
            {
                "type": "docker_image",
                "url": "celoflow/agent:latest",
                "description": "Docker container image"
            },
            {
                "type": "mcp_endpoint",
                "url": os.getenv("MCP_ENDPOINT", "https://api.celoflow.com/mcp"),
                "description": "MCP protocol endpoint"
            }
        ]
    
    def _get_modules(self) -> List[Dict[str, Any]]:
        """Define extended capability modules."""
        return [
            {
                "name": "mento_v2_integration",
                "description": "Mento v2 protocol integration for currency exchange",
                "version": "1.0.0",
                "capabilities": [
                    "real_time_rate_lookup",
                    "optimal_route_finding", 
                    "liquidity_provision"
                ]
            },
            {
                "name": "tee_security",
                "description": "Trusted Execution Environment for secure operations",
                "version": "1.0.0",
                "capabilities": [
                    "secure_key_management",
                    "attestation_generation",
                    "tee_backed_signing"
                ]
            },
            {
                "name": "compliance_engine",
                "description": "KYC/AML compliance checking and risk assessment",
                "version": "1.0.0",
                "capabilities": [
                    "transaction_screening",
                    "risk_scoring",
                    "regulatory_compliance"
                ]
            }
        ]
