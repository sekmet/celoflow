"""Scheduler Plugin for recurring transfers."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore

from contextwise import AgentContext, AgentPlugin
from agents import function_tool

logger = logging.getLogger(__name__)


class SchedulerPlugin(AgentPlugin[AgentContext]):
    """Plugin for scheduling recurring tasks."""

    name = "scheduler"

    def __init__(self) -> None:
        super().__init__()
        self.scheduler = AsyncIOScheduler()
        self.jobs: Dict[str, Dict[str, Any]] = {}

    def initialize(self, agent: Any) -> None:
        """Initialize the scheduler when the agent starts."""
        self.scheduler.start()
        logger.info("SchedulerPlugin: AsyncIOScheduler started")

    def shutdown(self) -> None:
        """Shutdown the scheduler."""
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
        """Callback for the scheduled job."""
        logger.info(
            f"⏰ Executing recurring transfer for {user_id}: {amount} {currency} -> {recipient}"
        )

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
