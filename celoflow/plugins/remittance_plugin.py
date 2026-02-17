"""Remittance Plugin — transaction tracking, fee analytics, and savings calculation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from contextwise import AgentPlugin, AgentContext

logger = logging.getLogger(__name__)

# Traditional remittance fee rates by corridor
TRADITIONAL_RATES: Dict[str, float] = {
    "Nigeria": 0.07,
    "Kenya": 0.06,
    "Philippines": 0.05,
    "Mexico": 0.04,
    "India": 0.03,
    "Colombia": 0.06,
    "Brazil": 0.05,
    "default": 0.07,
}


class RemittancePlugin(AgentPlugin[AgentContext]):
    """Tracks completed remittance transactions and computes savings vs. traditional rails."""

    name = "remittance"

    def __init__(self) -> None:
        super().__init__()
        self.transactions: Dict[str, Dict[str, Any]] = {}
        logger.info("RemittancePlugin initialised")

    # ------------------------------------------------------------------
    # Spending Limits
    # ------------------------------------------------------------------

    def _load_limits(self) -> None:
        """Load user limits from disk."""
        import json
        import os
        try:
            if os.path.exists("user_limits.json"):
                with open("user_limits.json", "r") as f:
                    self.spending_limits = json.load(f)
            else:
                self.spending_limits = {}
        except Exception as e:
            logger.error(f"Error loading limits: {e}")
            self.spending_limits = {}

    def _save_limits(self) -> None:
        """Save user limits to disk."""
        import json
        try:
            with open("user_limits.json", "w") as f:
                json.dump(self.spending_limits, f)
        except Exception as e:
            logger.error(f"Error saving limits: {e}")

    def check_spending_limit(self, user_id: str, amount_usd: float) -> bool:
        """Check if amount exceeds user's daily limit."""
        limit = self.spending_limits.get(user_id, 1000.0)  # Default $1000
        # ideally we track daily usage, but for now just check transaction limit
        return amount_usd <= limit

    def configure_agent(self, agent: Any) -> Any:
        self._load_limits()
        
        # We define tools here because we need 'self' access
        from agents import function_tool
        
        @function_tool
        def compare_fees(amount: float, source_currency: str, target_country: str) -> str:
            """Compare Celo fees vs traditional providers.
            
            Args:
                amount: Amount in source currency (e.g. 100).
                source_currency: Source currency code (e.g. USD).
                target_country: Destination country name (e.g. Philippines, Nigeria).
            """
            # Estimate crypto fee (network + 0.5% agent fee)
            crypto_fee = amount * 0.006 
            
            savings = self.calculate_savings(
                Decimal(str(amount)),
                target_country,
                crypto_fee
            )
            return (
                f"💰 **Fee Comparison for {amount} {source_currency} -> {target_country}**\n"
                f"- 🏦 Traditional Fee: {savings['traditional_fee']} {source_currency} ({savings['traditional_rate']})\n"
                f"- ⚡ CeloFlow Fee: {savings['crypto_fee']} {source_currency}\n"
                f"- ✅ **You Save: {savings['savings']} {source_currency} ({savings['savings_percentage']}%)**"
            )

        @function_tool
        def set_spending_limit(user_id: str, limit: float) -> str:
            """Set a maximum transaction limit for the user.
            
            Args:
                user_id: User ID.
                limit: Maximum amount per transaction in USD.
            """
            self.spending_limits[user_id] = limit
            self._save_limits()
            return f"✅ Transaction limit set to ${limit} for user {user_id}."

        if hasattr(agent, "tools"):
            agent.tools.extend([compare_fees, set_spending_limit])
            
        return agent

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def record_transaction(
        self,
        tx_hash: str,
        user_id: str,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        destination: str,
        fees: Dict[str, Any],
    ) -> None:
        """Store a completed transaction."""
        self.transactions[tx_hash] = {
            "user_id": user_id,
            "amount": str(amount),
            "from_currency": from_currency,
            "to_currency": to_currency,
            "destination": destination,
            "fees": fees,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        }
        logger.info("Recorded tx %s for user %s", tx_hash, user_id)

    # ------------------------------------------------------------------
    def calculate_savings(
        self,
        amount: Decimal,
        destination: str,
        crypto_fee: float,
    ) -> Dict[str, Any]:
        """Compare our fees to traditional remittance providers."""
        trad_rate = TRADITIONAL_RATES.get(destination, TRADITIONAL_RATES["default"])
        traditional_fee = float(amount) * trad_rate
        savings = traditional_fee - crypto_fee
        savings_pct = (savings / traditional_fee * 100) if traditional_fee > 0 else 0.0

        return {
            "traditional_fee": round(traditional_fee, 2),
            "crypto_fee": round(crypto_fee, 4),
            "savings": round(savings, 2),
            "savings_percentage": round(savings_pct, 1),
            "traditional_rate": f"{trad_rate * 100:.1f}%",
        }

    # ------------------------------------------------------------------
    def get_user_transactions(self, user_id: str) -> List[Dict[str, Any]]:
        """Return transaction history for a given user."""
        return [
            {**tx, "tx_hash": h}
            for h, tx in self.transactions.items()
            if tx["user_id"] == user_id
        ]
