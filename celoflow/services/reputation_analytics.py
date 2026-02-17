"""Reputation Analytics Service — trend analysis and prediction for agent reputation.

Tracks reputation changes over time, provides trend analysis,
and implements reputation-based pricing and agent selection.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Reputation decay rate per day (0.1% daily decay for inactive agents)
REPUTATION_DECAY_RATE = 0.001

# Minimum reputation score
MIN_REPUTATION = 0.0

# Maximum reputation score
MAX_REPUTATION = 100.0


class ReputationAnalyticsService:
    """Analyze and predict agent reputation trends."""

    def __init__(self) -> None:
        # History: agent_id -> list of {score, timestamp, event_type}
        self._history: Dict[int, List[Dict[str, Any]]] = {}
        # Current scores: agent_id -> {score, last_updated, total_tasks, successful_tasks}
        self._scores: Dict[int, Dict[str, Any]] = {}
        logger.info("ReputationAnalyticsService initialised")

    # ------------------------------------------------------------------
    # Public: record_event
    # ------------------------------------------------------------------

    def record_event(
        self,
        agent_id: int,
        event_type: str,
        score_delta: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a reputation event for an agent.

        Args:
            agent_id: Agent identifier
            event_type: Type of event (task_success, task_failure, feedback, decay)
            score_delta: Change in reputation score
            metadata: Additional event data

        Returns:
            Updated reputation summary
        """
        now = time.time()

        # Initialize if needed
        if agent_id not in self._scores:
            self._scores[agent_id] = {
                "score": 50.0,
                "last_updated": now,
                "total_tasks": 0,
                "successful_tasks": 0,
            }
        if agent_id not in self._history:
            self._history[agent_id] = []

        current = self._scores[agent_id]

        # Apply decay since last update
        self._apply_decay(agent_id)

        # Apply score delta
        new_score = max(MIN_REPUTATION, min(MAX_REPUTATION, current["score"] + score_delta))
        current["score"] = new_score
        current["last_updated"] = now

        # Update task counters
        if event_type == "task_success":
            current["total_tasks"] += 1
            current["successful_tasks"] += 1
        elif event_type == "task_failure":
            current["total_tasks"] += 1

        # Record history
        entry = {
            "timestamp": now,
            "event_type": event_type,
            "score_delta": score_delta,
            "new_score": new_score,
            "metadata": metadata or {},
        }
        self._history[agent_id].append(entry)

        # Keep history bounded
        if len(self._history[agent_id]) > 1000:
            self._history[agent_id] = self._history[agent_id][-1000:]

        return self.get_summary(agent_id)

    # ------------------------------------------------------------------
    # Public: get_summary
    # ------------------------------------------------------------------

    def get_summary(self, agent_id: int) -> Dict[str, Any]:
        """Get reputation summary for an agent."""
        if agent_id not in self._scores:
            return {
                "agent_id": agent_id,
                "score": 0.0,
                "status": "unknown",
                "message": "No reputation data available",
            }

        self._apply_decay(agent_id)
        current = self._scores[agent_id]
        success_rate = (
            current["successful_tasks"] / current["total_tasks"]
            if current["total_tasks"] > 0
            else 0.0
        )

        return {
            "agent_id": agent_id,
            "score": round(current["score"], 2),
            "success_rate": round(success_rate * 100, 1),
            "total_tasks": current["total_tasks"],
            "successful_tasks": current["successful_tasks"],
            "status": self._score_to_status(current["score"]),
            "last_updated": current["last_updated"],
        }

    # ------------------------------------------------------------------
    # Public: get_trend
    # ------------------------------------------------------------------

    def get_trend(
        self,
        agent_id: int,
        period_days: int = 30,
    ) -> Dict[str, Any]:
        """Get reputation trend for an agent over a time period.

        Args:
            agent_id: Agent identifier
            period_days: Number of days to analyze

        Returns:
            Trend data with direction, change, and data points
        """
        history = self._history.get(agent_id, [])
        cutoff = time.time() - (period_days * 86_400)
        recent = [e for e in history if e["timestamp"] >= cutoff]

        if len(recent) < 2:
            return {
                "agent_id": agent_id,
                "period_days": period_days,
                "direction": "stable",
                "change": 0.0,
                "data_points": len(recent),
                "message": "Insufficient data for trend analysis",
            }

        first_score = recent[0]["new_score"]
        last_score = recent[-1]["new_score"]
        change = last_score - first_score

        if change > 2:
            direction = "improving"
        elif change < -2:
            direction = "declining"
        else:
            direction = "stable"

        return {
            "agent_id": agent_id,
            "period_days": period_days,
            "direction": direction,
            "change": round(change, 2),
            "start_score": round(first_score, 2),
            "end_score": round(last_score, 2),
            "data_points": len(recent),
            "events_breakdown": self._count_events(recent),
        }

    # ------------------------------------------------------------------
    # Public: select_best_agent
    # ------------------------------------------------------------------

    def select_best_agent(
        self,
        agent_ids: List[int],
        min_score: float = 30.0,
    ) -> Optional[Dict[str, Any]]:
        """Select the best agent from a list based on reputation.

        Args:
            agent_ids: List of agent IDs to consider
            min_score: Minimum acceptable reputation score

        Returns:
            Best agent info or None if no eligible agents
        """
        candidates = []
        for aid in agent_ids:
            summary = self.get_summary(aid)
            if summary.get("score", 0) >= min_score:
                candidates.append(summary)

        if not candidates:
            return None

        # Sort by score descending, then by success rate
        candidates.sort(
            key=lambda x: (x.get("score", 0), x.get("success_rate", 0)),
            reverse=True,
        )
        return candidates[0]

    # ------------------------------------------------------------------
    # Public: get_pricing_modifier
    # ------------------------------------------------------------------

    def get_pricing_modifier(self, agent_id: int) -> float:
        """Get a pricing modifier based on reputation.

        Higher reputation agents can charge slightly more.
        Lower reputation agents should offer discounts.

        Returns:
            Multiplier (e.g., 1.0 = standard, 0.9 = 10% discount, 1.1 = 10% premium)
        """
        summary = self.get_summary(agent_id)
        score = summary.get("score", 50.0)

        if score >= 90:
            return 1.10
        elif score >= 75:
            return 1.05
        elif score >= 50:
            return 1.00
        elif score >= 30:
            return 0.95
        else:
            return 0.90

    # ------------------------------------------------------------------
    # Public: detect_fraud
    # ------------------------------------------------------------------

    def detect_fraud(self, agent_id: int) -> Dict[str, Any]:
        """Detect potential reputation fraud patterns.

        Checks for suspicious patterns like rapid score changes,
        self-feedback, or coordinated boosting.
        """
        history = self._history.get(agent_id, [])
        flags: List[str] = []

        if not history:
            return {"agent_id": agent_id, "suspicious": False, "flags": []}

        # Check for rapid positive changes
        recent_hour = [
            e for e in history
            if e["timestamp"] > time.time() - 3600
        ]
        if len(recent_hour) > 20:
            flags.append(f"Unusually high activity: {len(recent_hour)} events in last hour")

        # Check for consistent perfect scores
        recent_scores = [e["score_delta"] for e in history[-50:] if e.get("score_delta")]
        if recent_scores and all(s > 0 for s in recent_scores) and len(recent_scores) > 10:
            flags.append("All recent score changes are positive — possible boosting")

        return {
            "agent_id": agent_id,
            "suspicious": len(flags) > 0,
            "flags": flags,
            "risk_level": "high" if len(flags) >= 2 else "medium" if flags else "low",
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_decay(self, agent_id: int) -> None:
        """Apply reputation decay based on inactivity."""
        current = self._scores.get(agent_id)
        if not current:
            return

        now = time.time()
        days_inactive = (now - current["last_updated"]) / 86_400

        if days_inactive > 1:
            decay = days_inactive * REPUTATION_DECAY_RATE * current["score"]
            current["score"] = max(MIN_REPUTATION, current["score"] - decay)

    @staticmethod
    def _score_to_status(score: float) -> str:
        """Convert numeric score to status label."""
        if score >= 90:
            return "excellent"
        elif score >= 75:
            return "good"
        elif score >= 50:
            return "average"
        elif score >= 30:
            return "below_average"
        else:
            return "poor"

    @staticmethod
    def _count_events(events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count events by type."""
        counts: Dict[str, int] = {}
        for e in events:
            et = e.get("event_type", "unknown")
            counts[et] = counts.get(et, 0) + 1
        return counts
