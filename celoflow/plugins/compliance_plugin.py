"""Compliance Plugin — KYC/AML enforcement for remittance operations."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from contextwise import AgentPlugin, AgentContext
from agents import function_tool

logger = logging.getLogger(__name__)

# Simple corridor limits (USD equivalent)
CORRIDOR_LIMITS: Dict[str, float] = {
    "Nigeria": 5_000.0,
    "Kenya": 5_000.0,
    "Philippines": 10_000.0,
    "Mexico": 10_000.0,
    "India": 25_000.0,
    "Colombia": 5_000.0,
    "Brazil": 10_000.0,
    "default": 3_000.0,
}


class CompliancePlugin(AgentPlugin[AgentContext]):
    """Enforces basic KYC/AML rules for cross-border transfers."""

    name = "compliance"

    def __init__(self, max_single_transfer: float = 10_000.0) -> None:
        super().__init__()
        self.max_single_transfer = max_single_transfer

    def configure_agent(self, agent: Any) -> Any:
        """Register tools with the agent."""
        if hasattr(agent, "tools"):
            
            @function_tool
            async def check_compliance_action(
                amount: float,
                destination: str,
                user_id: str,
            ) -> str:
                """Run compliance checks on a proposed transfer.

                Args:
                    amount: Transfer amount in USD equivalent
                    destination: Destination country or currency
                    user_id: Identifier of the user requesting the transfer
                """
                result = await self.check_compliance(amount, destination, user_id)
                return json.dumps(result)

            agent.tools.append(check_compliance_action)
        return agent

    # ------------------------------------------------------------------
    # Logic: check_compliance
    # ------------------------------------------------------------------

    async def check_compliance(
        self,
        amount: float,
        destination: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Run compliance checks (logic)."""
        issues: list[str] = []

        # 1. Single-transfer limit
        if amount > self.max_single_transfer:
            issues.append(
                f"Amount ${amount:,.2f} exceeds single-transfer limit "
                f"${self.max_single_transfer:,.2f}"
            )

        # 2. Corridor-specific limit
        corridor_limit = CORRIDOR_LIMITS.get(destination, CORRIDOR_LIMITS["default"])
        if amount > corridor_limit:
            issues.append(
                f"Amount ${amount:,.2f} exceeds corridor limit for "
                f"{destination} (${corridor_limit:,.2f})"
            )

        approved = len(issues) == 0
        result: Dict[str, Any] = {
            "approved": approved,
            "amount": amount,
            "destination": destination,
            "user_id": user_id,
        }
        if issues:
            result["issues"] = issues
        return result


