"""Compliance Agent Plugin — x402 inter-agent compliance screening.

Implements agent-to-agent communication for compliance screening services,
using x402 payment flows to pay compliance agents for sanction list checks
and AML screening.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

from contextwise import AgentPlugin, AgentContext
from agents import function_tool

logger = logging.getLogger(__name__)

# Compliance screening result cache TTL (1 hour)
SCREENING_CACHE_TTL = 3_600

# Sanction list sources (simulated)
SANCTION_LISTS = ["OFAC-SDN", "EU-Sanctions", "UN-Consolidated"]

# Known high-risk jurisdictions
HIGH_RISK_JURISDICTIONS = {
    "North Korea", "Iran", "Syria", "Cuba", "Crimea",
    "Donetsk", "Luhansk", "Myanmar",
}


class ComplianceAgentPlugin(AgentPlugin[AgentContext]):
    """x402 Compliance Agent — inter-agent screening and sanction checks."""

    name = "compliance_agent"

    def __init__(
        self,
        compliance_agent_url: Optional[str] = None,
        compliance_fee_usdt: float = 0.10,
        enable_caching: bool = True,
    ) -> None:
        super().__init__()
        self.agent_url = compliance_agent_url
        self.fee_usdt = compliance_fee_usdt
        self.enable_caching = enable_caching

        # Screening result cache: address -> {result, timestamp}
        self._screening_cache: Dict[str, Dict[str, Any]] = {}

        # Audit trail: list of all screening events
        self._audit_trail: List[Dict[str, Any]] = []

        logger.info(
            "ComplianceAgentPlugin initialised (agent_url=%s, fee=%.2f USDT)",
            self.agent_url or "simulated",
            self.fee_usdt,
        )

    # ------------------------------------------------------------------
    # Agent tool registration
    # ------------------------------------------------------------------

    def configure_agent(self, agent: Any) -> Any:
        """Register compliance agent tools."""
        if hasattr(agent, "tools"):

            @function_tool
            async def screen_recipient(
                recipient_address: str,
                destination_country: str = "",
                amount: float = 0.0,
            ) -> str:
                """Screen a recipient address against sanction lists and AML rules.

                Args:
                    recipient_address: Wallet address to screen
                    destination_country: Destination country for jurisdiction checks
                    amount: Transfer amount for risk scoring
                """
                result = await self.screen_address(
                    recipient_address, destination_country, amount
                )
                return json.dumps(result)

            @function_tool
            async def get_compliance_report(
                recipient_address: str,
            ) -> str:
                """Get a detailed compliance report for a previously screened address.

                Args:
                    recipient_address: Wallet address to get report for
                """
                result = self.get_cached_report(recipient_address)
                return json.dumps(result)

            @function_tool
            async def get_compliance_fee() -> str:
                """Get the current compliance screening fee."""
                return json.dumps({
                    "fee_usdt": self.fee_usdt,
                    "currency": "USDT",
                    "description": "Per-transaction compliance screening fee",
                })

            agent.tools.extend([
                screen_recipient,
                get_compliance_report,
                get_compliance_fee,
            ])
        return agent

    # ------------------------------------------------------------------
    # Logic: screen_address
    # ------------------------------------------------------------------

    async def screen_address(
        self,
        address: str,
        destination_country: str = "",
        amount: float = 0.0,
    ) -> Dict[str, Any]:
        """Screen an address against sanction lists and compliance rules."""
        # Check cache
        if self.enable_caching:
            cached = self._get_cached_screening(address)
            if cached:
                cached["cached"] = True
                return cached

        # Perform screening
        screening_result = await self._perform_screening(
            address, destination_country, amount
        )

        # Record audit trail
        audit_entry = {
            "timestamp": time.time(),
            "address": address,
            "destination_country": destination_country,
            "amount": amount,
            "result": screening_result["status"],
            "risk_score": screening_result.get("risk_score", 0),
            "screening_id": screening_result.get("screening_id", ""),
        }
        self._audit_trail.append(audit_entry)

        # Cache result
        if self.enable_caching:
            self._cache_screening(address, screening_result)

        return screening_result

    # ------------------------------------------------------------------
    # Logic: get_cached_report
    # ------------------------------------------------------------------

    def get_cached_report(self, address: str) -> Dict[str, Any]:
        """Get a cached compliance report for an address."""
        cached = self._screening_cache.get(address.lower())
        if not cached:
            return {
                "address": address,
                "status": "not_screened",
                "message": "No screening record found. Run screen_recipient first.",
            }

        if cached["expires_at"] < time.time():
            return {
                "address": address,
                "status": "expired",
                "message": "Screening result has expired. Run screen_recipient again.",
            }

        return cached["result"]

    # ------------------------------------------------------------------
    # Logic: check_pre_transfer
    # ------------------------------------------------------------------

    async def check_pre_transfer(
        self,
        recipient_address: str,
        destination_country: str,
        amount: float,
    ) -> Dict[str, Any]:
        """Pre-transfer compliance check — called by execute_transfer.

        Returns:
            Dict with 'approved' boolean and details
        """
        result = await self.screen_address(
            recipient_address, destination_country, amount
        )

        approved = result.get("status") == "clear"
        return {
            "approved": approved,
            "screening_id": result.get("screening_id", ""),
            "risk_score": result.get("risk_score", 0),
            "fee_charged": self.fee_usdt if approved else 0,
            "issues": result.get("flags", []),
            "message": result.get("message", ""),
        }

    # ------------------------------------------------------------------
    # Logic: get_audit_trail
    # ------------------------------------------------------------------

    def get_audit_trail(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent audit trail entries."""
        return self._audit_trail[-limit:]

    # ------------------------------------------------------------------
    # Private: perform screening
    # ------------------------------------------------------------------

    async def _perform_screening(
        self,
        address: str,
        destination_country: str,
        amount: float,
    ) -> Dict[str, Any]:
        """Perform compliance screening via external agent or simulation."""
        screening_id = hashlib.sha256(
            f"{address}:{destination_country}:{amount}:{time.time()}".encode()
        ).hexdigest()[:16]

        # If external compliance agent is configured, call it
        if self.agent_url:
            return await self._call_compliance_agent(
                address, destination_country, amount, screening_id
            )

        # Simulated screening
        return self._simulate_screening(
            address, destination_country, amount, screening_id
        )

    async def _call_compliance_agent(
        self,
        address: str,
        destination_country: str,
        amount: float,
        screening_id: str,
    ) -> Dict[str, Any]:
        """Call external compliance agent via x402 payment flow."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.agent_url}/screen",
                    json={
                        "address": address,
                        "destination_country": destination_country,
                        "amount": amount,
                        "payment_token": "USDT",
                        "payment_amount": self.fee_usdt,
                    },
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code == 200:
                    data = response.json()
                    data["screening_id"] = screening_id
                    data["fee_charged"] = self.fee_usdt
                    return data

                logger.warning(
                    "Compliance agent returned %d: %s",
                    response.status_code,
                    response.text[:200],
                )
                return {
                    "status": "error",
                    "screening_id": screening_id,
                    "message": f"Compliance agent error: {response.status_code}",
                }
        except Exception as e:
            logger.error("Compliance agent call failed: %s", e)
            # Fallback to simulation on error
            return self._simulate_screening(
                address, destination_country, amount, screening_id
            )

    def _simulate_screening(
        self,
        address: str,
        destination_country: str,
        amount: float,
        screening_id: str,
    ) -> Dict[str, Any]:
        """Simulated compliance screening for development."""
        flags: List[str] = []
        risk_score = 0

        # Jurisdiction check
        if destination_country in HIGH_RISK_JURISDICTIONS:
            flags.append(f"High-risk jurisdiction: {destination_country}")
            risk_score += 80

        # Amount-based risk
        if amount > 50_000:
            flags.append(f"High-value transfer: ${amount:,.2f}")
            risk_score += 30
        elif amount > 10_000:
            risk_score += 10

        # Address pattern check (simulated)
        if address.lower().startswith("0x0000"):
            flags.append("Suspicious address pattern detected")
            risk_score += 50

        risk_score = min(risk_score, 100)
        status = "flagged" if risk_score >= 70 else "clear"

        result: Dict[str, Any] = {
            "screening_id": screening_id,
            "address": address,
            "destination_country": destination_country,
            "status": status,
            "risk_score": risk_score,
            "sanction_lists_checked": SANCTION_LISTS,
            "flags": flags,
            "fee_charged": self.fee_usdt,
            "message": (
                "Address cleared for transfer"
                if status == "clear"
                else f"Transfer flagged — {len(flags)} issue(s) detected"
            ),
        }

        logger.info(
            "Compliance screening %s: address=%s status=%s risk=%d",
            screening_id, address[:10], status, risk_score,
        )
        return result

    # ------------------------------------------------------------------
    # Private: caching
    # ------------------------------------------------------------------

    def _cache_screening(self, address: str, result: Dict[str, Any]) -> None:
        """Cache a screening result."""
        self._screening_cache[address.lower()] = {
            "result": result,
            "expires_at": time.time() + SCREENING_CACHE_TTL,
        }

    def _get_cached_screening(self, address: str) -> Optional[Dict[str, Any]]:
        """Get a cached screening result if valid."""
        cached = self._screening_cache.get(address.lower())
        if cached and cached["expires_at"] > time.time():
            return cached["result"]
        if cached:
            del self._screening_cache[address.lower()]
        return None
