"""Payment Reward Service — x402 reputation-based agent reward processing.

Processes transfer rewards for agents based on their ERC-8004 reputation score.
Implements retry logic, audit logging, circuit-breaker pattern, and payment caps.

Design decisions:
- Rewards are calculated as base_rate * reputation_modifier * transfer_amount
- Retry uses exponential backoff (max 3 attempts) to handle transient failures
- Circuit breaker trips after 5 consecutive failures, resets after 60s
- All reward transactions are audit-logged for compliance
- Payment is atomic with transfer success — orphaned rewards are prevented
  by only calling this service after confirmed on-chain success
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from integrations.x402_client import X402Client
    from services.reputation_analytics import ReputationAnalyticsService

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds

# Circuit breaker
CIRCUIT_BREAKER_THRESHOLD = 5    # consecutive failures before tripping
CIRCUIT_BREAKER_RESET_SECS = 60  # seconds before auto-reset

# Audit log retention
MAX_AUDIT_ENTRIES = 50_000

# Daily payment cap per agent (USD equivalent)
DEFAULT_DAILY_CAP_USD = 100.0

# Agent fee percentage for x402 service fee (0.5% of transfer)
AGENT_FEE_PCT = 0.005


class PaymentRewardService:
    """Process x402 micropayment rewards for agents after successful transfers.

    Integrates with X402Client for payment calculation and ReputationAnalyticsService
    for reputation-based multipliers. Provides retry logic, circuit breaker, and
    full audit trail.
    """

    def __init__(
        self,
        x402_client: Optional["X402Client"] = None,
        reputation_service: Optional["ReputationAnalyticsService"] = None,
        daily_cap_usd: float = DEFAULT_DAILY_CAP_USD,
        agent_id: int = 0,
    ) -> None:
        self._x402 = x402_client
        self._reputation = reputation_service
        self._daily_cap_usd = daily_cap_usd
        self._agent_id = agent_id

        # Audit log: list of reward records
        self._audit_log: List[Dict[str, Any]] = []

        # Daily tracking: agent_id -> {earned, reset_ts}
        self._daily_tracking: Dict[int, Dict[str, Any]] = {}

        # Circuit breaker state
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_opened_at: Optional[float] = None

        logger.info(
            "PaymentRewardService initialised (agent_id=%d, daily_cap=%.2f USD)",
            agent_id, daily_cap_usd,
        )

    # ------------------------------------------------------------------
    # Public: process_transfer_reward
    # ------------------------------------------------------------------

    async def process_transfer_reward(
        self,
        agent_id: int,
        transfer_amount: float,
        success_status: bool,
        tx_hash: Optional[str] = None,
        token: str = "USDm",
    ) -> Dict[str, Any]:
        """Process a reward payment for a completed transfer.

        Args:
            agent_id: Agent identifier (ERC-8004 agent ID)
            transfer_amount: Transfer amount in USD equivalent
            success_status: True if transfer succeeded on-chain
            tx_hash: Transfer transaction hash for correlation
            token: Token used in the transfer

        Returns:
            Reward result with payment_id, amount, tier, and audit_id
        """
        if not success_status:
            logger.debug("Skipping reward for agent %d — transfer not successful", agent_id)
            return {
                "success": False,
                "reason": "transfer_not_successful",
                "agent_id": agent_id,
            }

        if transfer_amount <= 0:
            return {
                "success": False,
                "reason": "invalid_transfer_amount",
                "agent_id": agent_id,
            }

        # Check circuit breaker
        if self._is_circuit_open():
            logger.warning("Circuit breaker OPEN — skipping reward for agent %d", agent_id)
            return {
                "success": False,
                "reason": "circuit_breaker_open",
                "agent_id": agent_id,
                "circuit_reset_in": self._circuit_reset_in(),
            }

        # Get reputation score
        reputation_score = self._get_reputation_score(agent_id)

        # Check daily cap
        cap_check = self._check_daily_cap(agent_id, transfer_amount)
        if not cap_check["allowed"]:
            logger.info(
                "Agent %d daily cap reached (earned=%.4f, cap=%.4f)",
                agent_id, cap_check["daily_earned"], self._daily_cap_usd,
            )
            return {
                "success": False,
                "reason": "daily_cap_reached",
                "agent_id": agent_id,
                "daily_earned": cap_check["daily_earned"],
                "daily_cap": self._daily_cap_usd,
            }

        # Process reward with retry
        result = await self._process_with_retry(
            agent_id=agent_id,
            transfer_amount=transfer_amount,
            reputation_score=reputation_score,
            tx_hash=tx_hash,
        )

        if result.get("success"):
            self._consecutive_failures = 0
            self._update_daily_tracking(agent_id, result.get("reward_amount", 0.0))
            self._record_audit(
                agent_id=agent_id,
                transfer_amount=transfer_amount,
                reward_amount=result.get("reward_amount", 0.0),
                reputation_score=reputation_score,
                tier=result.get("tier", "unknown"),
                tx_hash=tx_hash,
                payment_id=result.get("payment_id"),
                token=token,
                status="success",
            )
            # Update reputation analytics after successful reward
            if self._reputation:
                try:
                    self._reputation.record_event(
                        agent_id=agent_id,
                        event_type="task_success",
                        score_delta=1.0,
                        metadata={
                            "transfer_amount": transfer_amount,
                            "reward_amount": result.get("reward_amount"),
                            "tx_hash": tx_hash,
                        },
                    )
                except Exception as rep_err:
                    logger.warning("Reputation update failed (non-blocking): %s", rep_err)
        else:
            self._consecutive_failures += 1
            if self._consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
                self._trip_circuit_breaker()
            self._record_audit(
                agent_id=agent_id,
                transfer_amount=transfer_amount,
                reward_amount=0.0,
                reputation_score=reputation_score,
                tier="unknown",
                tx_hash=tx_hash,
                payment_id=None,
                token=token,
                status="failed",
                error=result.get("error"),
            )

        return result

    # ------------------------------------------------------------------
    # Public: calculate_x402_service_fee
    # ------------------------------------------------------------------

    def calculate_x402_service_fee(
        self,
        transfer_amount: float,
        reputation_score: float = 50.0,
    ) -> Dict[str, Any]:
        """Calculate the x402 service fee for a transfer preview.

        The service fee is 0.5% of the transfer amount, adjusted by
        reputation tier (higher reputation = slightly lower fee to user).

        Args:
            transfer_amount: Transfer amount in USD equivalent
            reputation_score: Agent reputation score (0-100)

        Returns:
            Fee breakdown with amount, percentage, and tier
        """
        if self._x402:
            calc = self._x402.calculate_agent_payment(
                agent_id=self._agent_id,
                transfer_amount=transfer_amount,
                reputation_score=reputation_score,
            )
            fee_amount = calc["reward_amount"]
            tier = calc["tier"]
            multiplier = calc["multiplier"]
        else:
            fee_amount = round(transfer_amount * AGENT_FEE_PCT, 6)
            tier = "average"
            multiplier = 1.0

        return {
            "service_fee": fee_amount,
            "fee_percentage": round((fee_amount / transfer_amount * 100) if transfer_amount > 0 else 0, 4),
            "currency": "USDm",
            "tier": tier,
            "multiplier": multiplier,
            "description": "CeloFlow agent service fee (x402)",
        }

    # ------------------------------------------------------------------
    # Public: get_agent_earnings
    # ------------------------------------------------------------------

    def get_agent_earnings(self, agent_id: int) -> Dict[str, Any]:
        """Get earnings summary for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Earnings summary with total, daily, recent history
        """
        agent_entries = [
            e for e in self._audit_log
            if e.get("agent_id") == agent_id and e.get("status") == "success"
        ]

        total_earned = sum(e.get("reward_amount", 0.0) for e in agent_entries)
        daily_data = self._daily_tracking.get(agent_id, {})

        # Recent 10 payments
        recent = sorted(agent_entries, key=lambda x: x.get("timestamp", 0), reverse=True)[:10]

        reputation_score = self._get_reputation_score(agent_id)
        tier_info = self._get_tier_info(reputation_score)

        return {
            "agent_id": agent_id,
            "total_earned": round(total_earned, 6),
            "currency": "USDm",
            "daily_earned": round(daily_data.get("earned", 0.0), 6),
            "daily_cap": self._daily_cap_usd,
            "total_transfers_rewarded": len(agent_entries),
            "reputation_score": reputation_score,
            "tier": tier_info["tier"],
            "multiplier": tier_info["multiplier"],
            "recent_payments": [
                {
                    "timestamp": e.get("timestamp"),
                    "reward_amount": e.get("reward_amount"),
                    "transfer_amount": e.get("transfer_amount"),
                    "tx_hash": e.get("tx_hash"),
                    "payment_id": e.get("payment_id"),
                }
                for e in recent
            ],
        }

    # ------------------------------------------------------------------
    # Public: get_audit_log
    # ------------------------------------------------------------------

    def get_audit_log(self, limit: int = 100, agent_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get audit log entries, optionally filtered by agent.

        Args:
            limit: Maximum entries to return
            agent_id: Filter by agent ID (None = all agents)

        Returns:
            List of audit log entries, most recent first
        """
        entries = self._audit_log
        if agent_id is not None:
            entries = [e for e in entries if e.get("agent_id") == agent_id]
        return sorted(entries, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]

    # ------------------------------------------------------------------
    # Public: get_circuit_breaker_status
    # ------------------------------------------------------------------

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "open": self._circuit_open,
            "consecutive_failures": self._consecutive_failures,
            "threshold": CIRCUIT_BREAKER_THRESHOLD,
            "reset_in_seconds": self._circuit_reset_in() if self._circuit_open else 0,
        }

    # ------------------------------------------------------------------
    # Private: _process_with_retry
    # ------------------------------------------------------------------

    async def _process_with_retry(
        self,
        agent_id: int,
        transfer_amount: float,
        reputation_score: float,
        tx_hash: Optional[str],
    ) -> Dict[str, Any]:
        """Process reward with exponential backoff retry."""
        last_error: Optional[str] = None

        for attempt in range(MAX_RETRIES):
            try:
                if self._x402:
                    result = await self._x402.process_agent_reward(
                        agent_id=agent_id,
                        transfer_amount=transfer_amount,
                        reputation_score=reputation_score,
                        tx_hash=tx_hash,
                    )
                else:
                    # Fallback: calculate locally without x402 client
                    result = self._calculate_local_reward(
                        agent_id=agent_id,
                        transfer_amount=transfer_amount,
                        reputation_score=reputation_score,
                        tx_hash=tx_hash,
                    )

                if result.get("success"):
                    return result

                last_error = result.get("error", "Unknown error")
                logger.warning(
                    "Reward attempt %d/%d failed for agent %d: %s",
                    attempt + 1, MAX_RETRIES, agent_id, last_error,
                )

            except Exception as e:
                last_error = str(e)
                logger.error(
                    "Reward attempt %d/%d exception for agent %d: %s",
                    attempt + 1, MAX_RETRIES, agent_id, e,
                )

            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)

        return {
            "success": False,
            "error": f"All {MAX_RETRIES} attempts failed. Last error: {last_error}",
            "agent_id": agent_id,
        }

    # ------------------------------------------------------------------
    # Private: _calculate_local_reward
    # ------------------------------------------------------------------

    def _calculate_local_reward(
        self,
        agent_id: int,
        transfer_amount: float,
        reputation_score: float,
        tx_hash: Optional[str],
    ) -> Dict[str, Any]:
        """Fallback local reward calculation when x402 client unavailable."""
        import hashlib

        if reputation_score >= 90:
            tier, multiplier = "excellent", 1.5
        elif reputation_score >= 75:
            tier, multiplier = "good", 1.2
        elif reputation_score >= 50:
            tier, multiplier = "average", 1.0
        elif reputation_score >= 30:
            tier, multiplier = "below_average", 0.8
        else:
            tier, multiplier = "poor", 0.6

        reward = min(transfer_amount * AGENT_FEE_PCT * multiplier, 10.0)
        payment_id = hashlib.sha256(
            f"local:{agent_id}:{transfer_amount}:{time.time()}".encode()
        ).hexdigest()[:16]

        return {
            "success": True,
            "payment_id": payment_id,
            "agent_id": agent_id,
            "reward_amount": round(reward, 6),
            "currency": "USDm",
            "tier": tier,
            "multiplier": multiplier,
            "simulated": True,
        }

    # ------------------------------------------------------------------
    # Private: _get_reputation_score
    # ------------------------------------------------------------------

    def _get_reputation_score(self, agent_id: int) -> float:
        """Get current reputation score for an agent."""
        if self._reputation:
            try:
                summary = self._reputation.get_summary(agent_id)
                return summary.get("score", 50.0)
            except Exception as e:
                logger.warning("Failed to get reputation score for agent %d: %s", agent_id, e)
        return 50.0

    # ------------------------------------------------------------------
    # Private: _get_tier_info
    # ------------------------------------------------------------------

    @staticmethod
    def _get_tier_info(reputation_score: float) -> Dict[str, Any]:
        """Map reputation score to tier and multiplier."""
        if reputation_score >= 90:
            return {"tier": "excellent", "multiplier": 1.5}
        elif reputation_score >= 75:
            return {"tier": "good", "multiplier": 1.2}
        elif reputation_score >= 50:
            return {"tier": "average", "multiplier": 1.0}
        elif reputation_score >= 30:
            return {"tier": "below_average", "multiplier": 0.8}
        else:
            return {"tier": "poor", "multiplier": 0.6}

    # ------------------------------------------------------------------
    # Private: _check_daily_cap
    # ------------------------------------------------------------------

    def _check_daily_cap(self, agent_id: int, transfer_amount: float) -> Dict[str, Any]:
        """Check if agent has remaining daily reward capacity."""
        now = time.time()
        tracking = self._daily_tracking.get(agent_id)

        if tracking is None or now >= tracking["reset_ts"] + 86_400:
            self._daily_tracking[agent_id] = {"earned": 0.0, "reset_ts": now}
            tracking = self._daily_tracking[agent_id]

        projected_reward = transfer_amount * AGENT_FEE_PCT * 1.5  # worst case excellent tier
        remaining = self._daily_cap_usd - tracking["earned"]

        return {
            "allowed": remaining > 0,
            "daily_earned": tracking["earned"],
            "remaining": max(0.0, remaining),
        }

    # ------------------------------------------------------------------
    # Private: _update_daily_tracking
    # ------------------------------------------------------------------

    def _update_daily_tracking(self, agent_id: int, reward_amount: float) -> None:
        """Update daily earnings tracker for an agent."""
        now = time.time()
        tracking = self._daily_tracking.get(agent_id)

        if tracking is None or now >= tracking["reset_ts"] + 86_400:
            self._daily_tracking[agent_id] = {"earned": reward_amount, "reset_ts": now}
        else:
            tracking["earned"] += reward_amount

    # ------------------------------------------------------------------
    # Private: circuit breaker helpers
    # ------------------------------------------------------------------

    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open (blocking payments)."""
        if not self._circuit_open:
            return False
        # Auto-reset after timeout
        if self._circuit_opened_at and time.time() >= self._circuit_opened_at + CIRCUIT_BREAKER_RESET_SECS:
            logger.info("Circuit breaker auto-reset after %ds", CIRCUIT_BREAKER_RESET_SECS)
            self._circuit_open = False
            self._consecutive_failures = 0
            self._circuit_opened_at = None
            return False
        return True

    def _trip_circuit_breaker(self) -> None:
        """Trip the circuit breaker after too many consecutive failures."""
        self._circuit_open = True
        self._circuit_opened_at = time.time()
        logger.error(
            "Circuit breaker TRIPPED after %d consecutive failures. "
            "Payments paused for %ds.",
            self._consecutive_failures, CIRCUIT_BREAKER_RESET_SECS,
        )

    def _circuit_reset_in(self) -> float:
        """Seconds until circuit breaker auto-resets."""
        if not self._circuit_opened_at:
            return 0.0
        elapsed = time.time() - self._circuit_opened_at
        return max(0.0, CIRCUIT_BREAKER_RESET_SECS - elapsed)

    # ------------------------------------------------------------------
    # Private: _record_audit
    # ------------------------------------------------------------------

    def _record_audit(
        self,
        agent_id: int,
        transfer_amount: float,
        reward_amount: float,
        reputation_score: float,
        tier: str,
        tx_hash: Optional[str],
        payment_id: Optional[str],
        token: str,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """Record a reward transaction in the audit log."""
        entry = {
            "timestamp": time.time(),
            "agent_id": agent_id,
            "transfer_amount": transfer_amount,
            "reward_amount": reward_amount,
            "reputation_score": reputation_score,
            "tier": tier,
            "token": token,
            "tx_hash": tx_hash,
            "payment_id": payment_id,
            "status": status,
            "error": error,
        }
        self._audit_log.append(entry)

        # Keep bounded
        if len(self._audit_log) > MAX_AUDIT_ENTRIES:
            self._audit_log = self._audit_log[-MAX_AUDIT_ENTRIES // 2:]
