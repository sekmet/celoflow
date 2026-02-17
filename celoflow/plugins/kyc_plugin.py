"""KYC Plugin — Agent KYC Gateway for identity verification.

Implements Self Protocol API integration for privacy-preserving identity
verification with tiered KYC levels (basic, standard, enhanced).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from contextwise import AgentPlugin, AgentContext
from agents import function_tool

logger = logging.getLogger(__name__)

# KYC level definitions with requirements and limits
KYC_LEVELS: Dict[str, Dict[str, Any]] = {
    "none": {
        "max_single_transfer": 50.0,
        "max_daily_transfer": 200.0,
        "required_documents": [],
        "description": "No verification — limited functionality",
    },
    "basic": {
        "max_single_transfer": 1_000.0,
        "max_daily_transfer": 3_000.0,
        "required_documents": ["selfie", "email"],
        "description": "Basic verification — email and selfie",
    },
    "standard": {
        "max_single_transfer": 10_000.0,
        "max_daily_transfer": 25_000.0,
        "required_documents": ["selfie", "email", "government_id"],
        "description": "Standard verification — government ID required",
    },
    "enhanced": {
        "max_single_transfer": 100_000.0,
        "max_daily_transfer": 500_000.0,
        "required_documents": ["selfie", "email", "government_id", "proof_of_address", "source_of_funds"],
        "description": "Enhanced verification — full due diligence",
    },
}

# Fee structure for KYC verification (in USDT)
KYC_FEES: Dict[str, float] = {
    "basic": 0.0,
    "standard": 2.50,
    "enhanced": 10.00,
}

# Cache TTL in seconds (24 hours)
CREDENTIAL_CACHE_TTL = 86_400


class KYCPlugin(AgentPlugin[AgentContext]):
    """Agent KYC Gateway — privacy-preserving identity verification via Self Protocol."""

    name = "kyc"

    def __init__(
        self,
        self_protocol_api_key: Optional[str] = None,
        self_protocol_base_url: str = "https://api.self.id",
        default_kyc_level: str = "none",
    ) -> None:
        super().__init__()
        self.api_key = self_protocol_api_key
        self.base_url = self_protocol_base_url
        self.default_level = default_kyc_level

        # In-memory credential cache: user_id -> {level, verified_at, expires_at, attestation_hash}
        self._credential_cache: Dict[str, Dict[str, Any]] = {}

        # In-memory user KYC records: user_id -> {level, status, documents, ...}
        self._user_records: Dict[str, Dict[str, Any]] = {}

        logger.info(
            "KYCPlugin initialised (api_configured=%s, default_level=%s)",
            bool(self.api_key),
            self.default_level,
        )

    # ------------------------------------------------------------------
    # Agent tool registration
    # ------------------------------------------------------------------

    def configure_agent(self, agent: Any) -> Any:
        """Register KYC tools with the agent."""
        if hasattr(agent, "tools"):

            @function_tool
            async def verify_user_kyc(
                user_id: str,
                level: str = "basic",
            ) -> str:
                """Initiate or check KYC verification for a user.

                Args:
                    user_id: Unique identifier of the user
                    level: KYC level to verify (basic, standard, enhanced)
                """
                result = await self.verify_kyc(user_id, level)
                return json.dumps(result)

            @function_tool
            async def get_kyc_status(user_id: str) -> str:
                """Get the current KYC verification status for a user.

                Args:
                    user_id: Unique identifier of the user
                """
                result = await self.get_status(user_id)
                return json.dumps(result)

            @function_tool
            async def get_kyc_requirements(level: str = "standard") -> str:
                """Get the requirements and limits for a KYC level.

                Args:
                    level: KYC level to query (basic, standard, enhanced)
                """
                result = self.get_level_requirements(level)
                return json.dumps(result)

            @function_tool
            async def check_kyc_transfer_eligibility(
                user_id: str,
                amount: float,
            ) -> str:
                """Check if a user's KYC level allows a transfer of the given amount.

                Args:
                    user_id: Unique identifier of the user
                    amount: Transfer amount in USD equivalent
                """
                result = await self.check_transfer_eligibility(user_id, amount)
                return json.dumps(result)

            agent.tools.extend([
                verify_user_kyc,
                get_kyc_status,
                get_kyc_requirements,
                check_kyc_transfer_eligibility,
            ])
        return agent

    # ------------------------------------------------------------------
    # Logic: verify_kyc
    # ------------------------------------------------------------------

    async def verify_kyc(self, user_id: str, level: str = "basic") -> Dict[str, Any]:
        """Initiate or check KYC verification for a user."""
        if level not in KYC_LEVELS or level == "none":
            return {"error": f"Invalid KYC level: {level}. Use basic, standard, or enhanced."}

        # Check cache first
        cached = self._get_cached_credential(user_id)
        if cached and self._level_rank(cached["level"]) >= self._level_rank(level):
            return {
                "user_id": user_id,
                "status": "verified",
                "level": cached["level"],
                "cached": True,
                "expires_at": cached["expires_at"],
                "message": f"User already verified at {cached['level']} level (cached).",
            }

        # Check existing record
        record = self._user_records.get(user_id, {})
        current_level = record.get("level", "none")

        if self._level_rank(current_level) >= self._level_rank(level):
            # Already verified at this level or higher
            self._cache_credential(user_id, current_level)
            return {
                "user_id": user_id,
                "status": "verified",
                "level": current_level,
                "message": f"User verified at {current_level} level.",
            }

        # Initiate verification via Self Protocol
        verification_result = await self._call_self_protocol(user_id, level)

        if verification_result.get("verified"):
            self._user_records[user_id] = {
                "level": level,
                "status": "verified",
                "verified_at": time.time(),
                "attestation_hash": verification_result.get("attestation_hash", ""),
                "documents": KYC_LEVELS[level]["required_documents"],
            }
            self._cache_credential(user_id, level)
            return {
                "user_id": user_id,
                "status": "verified",
                "level": level,
                "fee_charged": KYC_FEES.get(level, 0),
                "attestation_hash": verification_result.get("attestation_hash", ""),
                "message": f"KYC verification successful at {level} level.",
            }

        return {
            "user_id": user_id,
            "status": "pending",
            "level": level,
            "required_documents": KYC_LEVELS[level]["required_documents"],
            "fee": KYC_FEES.get(level, 0),
            "message": verification_result.get("message", "Verification pending — documents required."),
        }

    # ------------------------------------------------------------------
    # Logic: get_status
    # ------------------------------------------------------------------

    async def get_status(self, user_id: str) -> Dict[str, Any]:
        """Get the current KYC status for a user."""
        record = self._user_records.get(user_id)
        if not record:
            return {
                "user_id": user_id,
                "level": "none",
                "status": "unverified",
                "limits": KYC_LEVELS["none"],
                "message": "No KYC verification on record. Use verify_user_kyc to start.",
            }

        level_info = KYC_LEVELS.get(record["level"], KYC_LEVELS["none"])
        return {
            "user_id": user_id,
            "level": record["level"],
            "status": record["status"],
            "verified_at": record.get("verified_at"),
            "max_single_transfer": level_info["max_single_transfer"],
            "max_daily_transfer": level_info["max_daily_transfer"],
        }

    # ------------------------------------------------------------------
    # Logic: get_level_requirements
    # ------------------------------------------------------------------

    def get_level_requirements(self, level: str) -> Dict[str, Any]:
        """Get requirements and limits for a KYC level."""
        if level not in KYC_LEVELS:
            return {"error": f"Unknown KYC level: {level}"}

        info = KYC_LEVELS[level]
        return {
            "level": level,
            "description": info["description"],
            "required_documents": info["required_documents"],
            "max_single_transfer": info["max_single_transfer"],
            "max_daily_transfer": info["max_daily_transfer"],
            "fee": KYC_FEES.get(level, 0),
        }

    # ------------------------------------------------------------------
    # Logic: check_transfer_eligibility
    # ------------------------------------------------------------------

    async def check_transfer_eligibility(
        self, user_id: str, amount: float
    ) -> Dict[str, Any]:
        """Check if a user's KYC level permits a transfer amount."""
        record = self._user_records.get(user_id)
        level = record["level"] if record and record.get("status") == "verified" else "none"
        level_info = KYC_LEVELS[level]

        eligible = amount <= level_info["max_single_transfer"]
        result: Dict[str, Any] = {
            "user_id": user_id,
            "amount": amount,
            "current_level": level,
            "eligible": eligible,
            "max_single_transfer": level_info["max_single_transfer"],
        }

        if not eligible:
            # Suggest upgrade
            for upgrade_level in ["basic", "standard", "enhanced"]:
                if KYC_LEVELS[upgrade_level]["max_single_transfer"] >= amount:
                    result["suggested_upgrade"] = upgrade_level
                    result["upgrade_fee"] = KYC_FEES.get(upgrade_level, 0)
                    result["message"] = (
                        f"Amount ${amount:,.2f} exceeds {level} limit "
                        f"(${level_info['max_single_transfer']:,.2f}). "
                        f"Upgrade to {upgrade_level} level to proceed."
                    )
                    break
        else:
            result["message"] = f"Transfer of ${amount:,.2f} is within {level} level limits."

        return result

    # ------------------------------------------------------------------
    # Private: Self Protocol API integration
    # ------------------------------------------------------------------

    async def _call_self_protocol(
        self, user_id: str, level: str
    ) -> Dict[str, Any]:
        """Call Self Protocol API for identity verification.

        In production, this makes an HTTP call to the Self Protocol API.
        Currently returns a simulated response for development.
        """
        if self.api_key:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/verify",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "user_id": user_id,
                            "level": level,
                            "required_documents": KYC_LEVELS[level]["required_documents"],
                        },
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return {
                            "verified": data.get("verified", False),
                            "attestation_hash": data.get("attestation_hash", ""),
                            "message": data.get("message", ""),
                        }
                    logger.warning(
                        "Self Protocol API returned %d: %s",
                        response.status_code,
                        response.text,
                    )
                    return {
                        "verified": False,
                        "message": f"Verification API error: {response.status_code}",
                    }
            except Exception as e:
                logger.error("Self Protocol API call failed: %s", e)
                return {"verified": False, "message": f"API error: {str(e)}"}

        # Simulated verification for development
        logger.info(
            "KYC (simulated) verification for user %s at level %s", user_id, level
        )
        import hashlib

        attestation = hashlib.sha256(
            f"{user_id}:{level}:{time.time()}".encode()
        ).hexdigest()
        return {
            "verified": True,
            "attestation_hash": attestation,
            "message": "Simulated verification successful",
        }

    # ------------------------------------------------------------------
    # Private: credential caching
    # ------------------------------------------------------------------

    def _cache_credential(self, user_id: str, level: str) -> None:
        """Cache a verified credential."""
        now = time.time()
        self._credential_cache[user_id] = {
            "level": level,
            "verified_at": now,
            "expires_at": now + CREDENTIAL_CACHE_TTL,
        }

    def _get_cached_credential(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached credential if still valid."""
        cached = self._credential_cache.get(user_id)
        if cached and cached["expires_at"] > time.time():
            return cached
        if cached:
            del self._credential_cache[user_id]
        return None

    @staticmethod
    def _level_rank(level: str) -> int:
        """Return numeric rank for KYC level comparison."""
        ranks = {"none": 0, "basic": 1, "standard": 2, "enhanced": 3}
        return ranks.get(level, 0)
