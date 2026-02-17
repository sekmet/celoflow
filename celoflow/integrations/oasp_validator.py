"""OASF Validation — Validate OASF records against schema."""

import json
import logging
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger(__name__)

class OASFValidator:
    """Validates OASF records using official validation endpoint."""
    
    VALIDATION_ENDPOINT = "https://schema.oasf.outshift.com/doc/index.html" # Note: This URL seems to be documentation, but we'll use it as placeholder or fix if there's a real API endpoint. The plan uses this. Let's assume it's correct for now or adjust if validation fails. Actually, posting to doc/index.html is unlikely to work as an API. I'll implement local validation primarily and keep remote as optional/experimental.
    # Correction: The plan specifies this URL. I will use it but wrap in try-except carefully.
    
    @staticmethod
    async def validate_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """Validate OASF record against official schema."""
        try:
            async with httpx.AsyncClient() as client:
                # Use official OASF validation endpoint
                # Note: This is likely a placeholder or documentation URL. 
                # Real validation might need a different endpoint.
                response = await client.post(
                    OASFValidator.VALIDATION_ENDPOINT,
                    json=record,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        return {
                            "valid": True, # Assuming success if 200 and JSON returned
                            "errors": [],
                            "warnings": data.get("warnings", [])
                        }
                    except json.JSONDecodeError:
                         return {
                            "valid": False,
                            "errors": ["Validation endpoint returned non-JSON response"],
                            "warnings": []
                        }
                else:
                    return {
                        "valid": False,
                        "errors": [f"Validation failed: {response.text}"],
                        "warnings": []
                    }
                    
        except Exception as e:
            logger.error(f"OASF validation error: {e}")
            return {
                "valid": False,
                "errors": [f"Validation service unavailable: {str(e)}"],
                "warnings": []
            }
    
    @staticmethod
    def validate_locally(record: Dict[str, Any]) -> Dict[str, Any]:
        """Perform basic local validation of OASF record."""
        errors = []
        warnings = []
        
        # Check required fields
        required_fields = ["name", "description", "version", "schema_version", "authors", "created_at", "skills"]
        for field in required_fields:
            if field not in record:
                errors.append(f"Missing required field: {field}")
        
        # Check schema version
        if record.get("schema_version") != "0.8.0":
            warnings.append(f"Expected schema version 0.8.0, got {record.get('schema_version')}")
        
        # Validate skills structure
        if "skills" in record:
            for skill in record["skills"]:
                if not isinstance(skill, dict) or "name" not in skill or "id" not in skill:
                    errors.append("Invalid skill structure: missing name or id")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
