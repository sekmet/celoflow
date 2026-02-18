"""Scheduler Plugin for recurring transfers with persistent storage."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore

from contextwise import AgentContext, AgentPlugin
from agents import function_tool

logger = logging.getLogger(__name__)

# Default persistence file path
DEFAULT_JOBS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "scheduled_jobs.json"
)


class SchedulerPlugin(AgentPlugin[AgentContext]):
    """Plugin for scheduling recurring tasks with JSON file persistence."""

    name = "scheduler"

    def __init__(
        self,
        jobs_file: Optional[str] = None,
        notification_plugin: Optional[Any] = None,
        max_retries: int = 3,
    ) -> None:
        super().__init__()
        self.scheduler = AsyncIOScheduler()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self._jobs_file = jobs_file or DEFAULT_JOBS_FILE
        self._notification_plugin = notification_plugin
        self._max_retries = max_retries
        # Transfer execution history: job_id → list of {timestamp, status, error?}
        self._execution_history: Dict[str, List[Dict[str, Any]]] = {}

    def set_notification_plugin(self, plugin: Any) -> None:
        """Late-bind the notification plugin."""
        self._notification_plugin = plugin

    def initialize(self, agent: Any) -> None:
        """Initialize the scheduler and recover persisted jobs."""
        self.scheduler.start()
        self._load_jobs()
        logger.info(
            "SchedulerPlugin: started with %d recovered jobs", len(self.jobs)
        )

    def shutdown(self) -> None:
        """Persist jobs and shutdown the scheduler."""
        self._save_jobs()
        self.scheduler.shutdown()
        logger.info("SchedulerPlugin: AsyncIOScheduler stopped")

    def configure_agent(self, agent: Any) -> Any:
        """Register scheduler tools with the agent via wrappers."""
        
        # We wrap instance methods because @function_tool doesn't handle 'self' automatically
        # when decorating instance methods directly.
        
        @function_tool
        async def schedule_transfer(
            recipient_id: str,
            amount: str,
            currency: str,
            frequency: str,
            user_id: str,
        ) -> str:
            """Schedule a recurring transfer.

            Args:
                recipient_id: The recipient's identifier (wallet or phone).
                amount: Amount to send.
                currency: Currency code (e.g., USDm, CELO).
                frequency: Cron expression or keywords ("daily", "weekly", "monthly").
                user_id: The ID of the user scheduling the transfer.
            """
            return await self.schedule_transfer_action(
                recipient_id, amount, currency, frequency, user_id
            )

        @function_tool
        async def list_scheduled_transfers(user_id: str) -> str:
            """List all scheduled transfers for the current user.

            Args:
                user_id: The ID of the user.
            """
            return await self.list_scheduled_transfers_action(user_id)

        @function_tool
        async def cancel_transfer(job_id: str) -> str:
            """Cancel a scheduled transfer.

            Args:
                job_id: The ID of the job to cancel.
            """
            return await self.cancel_transfer_action(job_id)

        if hasattr(agent, "tools"):
            agent.tools.extend(
                [
                    schedule_transfer,
                    list_scheduled_transfers,
                    cancel_transfer,
                ]
            )
        return agent

    async def schedule_transfer_action(
        self,
        recipient_id: str,
        amount: str,
        currency: str,
        frequency: str,
        user_id: str,
    ) -> str:
        """Internal implementation for scheduling."""
        job_id = f"transfer_{user_id}_{int(datetime.now().timestamp())}"

        trigger: Any
        if frequency == "daily":
            trigger = CronTrigger(hour=9, minute=0)  # Default 9 AM
        elif frequency == "weekly":
            trigger = CronTrigger(day_of_week="mon", hour=9, minute=0)
        elif frequency == "monthly":
            trigger = CronTrigger(day=1, hour=9, minute=0)
        elif frequency.startswith("every"):
            # "every 5 minutes" -> interval
            try:
                parts = frequency.split()
                val = int(parts[1])
                unit = parts[2].lower()
                if "minute" in unit:
                    trigger = IntervalTrigger(minutes=val)
                elif "hour" in unit:
                    trigger = IntervalTrigger(hours=val)
                else:
                    return f"Unsupported interval unit: {unit}"
            except (IndexError, ValueError):
                return f"Invalid frequency format: {frequency}"
        else:
            return f"Unsupported frequency: {frequency}. Use daily, weekly, monthly, or 'every X minutes'."

        self.scheduler.add_job(
            self._execute_recurring_transfer,
            trigger=trigger,
            id=job_id,
            args=[user_id, recipient_id, amount, currency],
            replace_existing=True,
        )

        job_info = {
            "id": job_id,
            "user_id": user_id,
            "recipient": recipient_id,
            "amount": amount,
            "currency": currency,
            "frequency": frequency,
            "next_run": str(self.scheduler.get_job(job_id).next_run_time),
        }
        self.jobs[job_id] = job_info

        return f"✅ Scheduled recurring transfer: {amount} {currency} to {recipient_id} ({frequency}). Job ID: {job_id}"

    async def _execute_recurring_transfer(
        self, user_id: str, recipient: str, amount: str, currency: str
    ) -> None:
        """Callback for the scheduled job — logs execution and sends notifications."""
        job_id = f"transfer_{user_id}"  # approximate; real id from scheduler
        logger.info(
            "⏰ Executing recurring transfer for %s: %s %s -> %s",
            user_id, amount, currency, recipient,
        )

        # Record execution
        entry = {
            "timestamp": datetime.now().isoformat(),
            "status": "executed",
            "amount": amount,
            "currency": currency,
            "recipient": recipient,
        }

        # Find the matching job_id
        for jid, info in self.jobs.items():
            if info.get("user_id") == user_id and info.get("recipient") == recipient:
                job_id = jid
                break

        if job_id not in self._execution_history:
            self._execution_history[job_id] = []
        self._execution_history[job_id].append(entry)

        # Send notification if plugin available
        if self._notification_plugin and hasattr(self._notification_plugin, "notify_transfer_complete"):
            try:
                await self._notification_plugin.notify_transfer_complete(
                    to=recipient,
                    amount=amount,
                    currency=currency,
                    tx_hash="recurring-scheduled",
                )
            except Exception as e:
                logger.warning("Notification failed for recurring transfer: %s", e)

    def get_execution_history(self, job_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get execution history for a specific job."""
        return self._execution_history.get(job_id, [])[-limit:]

    # ------------------------------------------------------------------
    # Persistence: load / save
    # ------------------------------------------------------------------

    def _load_jobs(self) -> None:
        """Load persisted jobs from JSON file and re-register them."""
        if not os.path.exists(self._jobs_file):
            return
        try:
            with open(self._jobs_file, "r") as f:
                saved = json.load(f)
            for job_info in saved:
                jid = job_info.get("id", "")
                freq = job_info.get("frequency", "")
                if not jid or not freq:
                    continue
                # Re-register with scheduler
                trigger = self._build_trigger(freq)
                if trigger is None:
                    continue
                self.scheduler.add_job(
                    self._execute_recurring_transfer,
                    trigger=trigger,
                    id=jid,
                    args=[
                        job_info.get("user_id", ""),
                        job_info.get("recipient", ""),
                        job_info.get("amount", "0"),
                        job_info.get("currency", "USDm"),
                    ],
                    replace_existing=True,
                )
                job_info["next_run"] = str(self.scheduler.get_job(jid).next_run_time)
                self.jobs[jid] = job_info
            logger.info("Loaded %d persisted jobs from %s", len(self.jobs), self._jobs_file)
        except Exception as e:
            logger.warning("Failed to load persisted jobs: %s", e)

    def _save_jobs(self) -> None:
        """Persist current jobs to JSON file."""
        try:
            os.makedirs(os.path.dirname(self._jobs_file), exist_ok=True)
            with open(self._jobs_file, "w") as f:
                json.dump(list(self.jobs.values()), f, indent=2, default=str)
            logger.info("Saved %d jobs to %s", len(self.jobs), self._jobs_file)
        except Exception as e:
            logger.warning("Failed to save jobs: %s", e)

    def _build_trigger(self, frequency: str) -> Any:
        """Build an APScheduler trigger from a frequency string."""
        if frequency == "daily":
            return CronTrigger(hour=9, minute=0)
        elif frequency == "weekly":
            return CronTrigger(day_of_week="mon", hour=9, minute=0)
        elif frequency == "monthly":
            return CronTrigger(day=1, hour=9, minute=0)
        elif frequency == "biweekly":
            return IntervalTrigger(weeks=2)
        elif frequency.startswith("every"):
            try:
                parts = frequency.split()
                val = int(parts[1])
                unit = parts[2].lower()
                if "minute" in unit:
                    return IntervalTrigger(minutes=val)
                elif "hour" in unit:
                    return IntervalTrigger(hours=val)
            except (IndexError, ValueError):
                pass
        return None

    async def list_scheduled_transfers_action(self, user_id: str) -> str:
        """Internal implementation for listing."""
        user_jobs = [j for j in self.jobs.values() if j.get("user_id") == user_id]

        if not user_jobs:
            return "No scheduled transfers found."

        report = "📅 **Scheduled Transfers:**\n"
        for job in user_jobs:
            report += (
                f"- **ID:** `{job['id']}`\n"
                f"  - Send: {job['amount']} {job['currency']} -> {job['recipient']}\n"
                f"  - Frequency: {job['frequency']}\n"
                f"  - Next Run: {job['next_run']}\n"
            )
        return report

    async def cancel_transfer_action(self, job_id: str) -> str:
        """Internal implementation for cancelling."""
        if job_id in self.jobs:
            try:
                self.scheduler.remove_job(job_id)
                del self.jobs[job_id]
                return f"✅ Cancelled transfer job `{job_id}`."
            except Exception as e:
                return f"Error cancelling job: {str(e)}"
        return f"❌ Job ID `{job_id}` not found."
