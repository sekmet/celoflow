"""Registry Plugin — ERC-8004 on-chain identity and reputation integration."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from contextwise import AgentPlugin, AgentContext
from agents import function_tool

from integrations.registry import RegistryClient

logger = logging.getLogger(__name__)


class RegistryPlugin(AgentPlugin[AgentContext]):
    """On-chain identity and reputation management via ERC-8004 registries."""

    name = "registry"

    def __init__(
        self,
        rpc_url: str,
        identity_registry: str,
        reputation_registry: str,
        tee_registry: str,
        private_key: Optional[str] = None,
        agent_id: Optional[int] = None,
    ) -> None:
        super().__init__()
        self.client = RegistryClient(
            rpc_url=rpc_url,
            identity_registry_address=identity_registry,
            reputation_registry_address=reputation_registry,
            tee_registry_address=tee_registry,
            private_key=private_key,
        )
        self.agent_id = agent_id
        logger.info(
            "RegistryPlugin initialised (agent_id=%s)", agent_id
        )

    def configure_agent(self, agent: Any) -> Any:
        """Register tools with the agent."""
        if hasattr(agent, "tools"):
            
            @function_tool
            async def get_agent_reputation_tool(agent_id: int = 0) -> str:
                """Get the on-chain reputation score for an agent."""
                result = await self.get_agent_reputation(agent_id)
                return json.dumps(result)

            @function_tool
            async def verify_agent_tee_tool(agent_id: int = 0) -> str:
                """Check whether an agent has registered TEE keys."""
                result = await self.verify_agent_tee(agent_id)
                return json.dumps(result)

            @function_tool
            async def get_agent_info_tool(agent_id: int = 0) -> str:
                """Get full agent information from the on-chain registry."""
                result = await self.get_agent_info(agent_id)
                return json.dumps(result)

            @function_tool
            async def submit_feedback_tool(
                target_agent_id: int,
                rating: int,
                comment: str = "",
            ) -> str:
                """Submit reputation feedback for another agent on-chain."""
                result = await self.submit_feedback(target_agent_id, rating, comment)
                return json.dumps(result)

            @function_tool
            async def register_agent_tool(token_uri: str = "") -> str:
                """Register a new agent identity on-chain in the IdentityRegistry."""
                result = await self.register_agent_onchain(token_uri)
                return json.dumps(result)

            agent.tools.append(get_agent_reputation_tool)
            agent.tools.append(verify_agent_tee_tool)
            agent.tools.append(get_agent_info_tool)
            agent.tools.append(submit_feedback_tool)
            agent.tools.append(register_agent_tool)
        return agent

    # ------------------------------------------------------------------
    # Logic: get_agent_reputation
    # ------------------------------------------------------------------

    async def get_agent_reputation(self, agent_id: int = 0) -> Dict[str, Any]:
        """Get agent reputation (logic)."""
        aid = agent_id if agent_id > 0 else self.agent_id
        if aid is None or aid == 0:
            return {"error": "No agent_id provided"}

        if not self.client.agent_exists(aid):
            return {"error": f"Agent {aid} not found on-chain"}

        rep = self.client.get_reputation(aid)
        return {
            "agent_id": aid,
            "score": rep["avg_score"],
            "total_reviews": rep["total_count"],
            "verified": True,
        }



    # ------------------------------------------------------------------
    # Logic: verify_agent_tee
    # ------------------------------------------------------------------

    async def verify_agent_tee(self, agent_id: int = 0) -> Dict[str, Any]:
        """Verify TEE keys (logic)."""
        aid = agent_id if agent_id > 0 else self.agent_id
        if aid is None or aid == 0:
            return {"error": "No agent_id provided"}

        key_count = self.client.get_tee_key_count(aid)
        keys = self.client.get_agent_keys(aid) if key_count > 0 else []
        return {
            "agent_id": aid,
            "tee_verified": key_count > 0,
            "key_count": key_count,
            "keys": keys,
        }



    # ------------------------------------------------------------------
    # Logic: get_agent_info
    # ------------------------------------------------------------------

    async def get_agent_info(self, agent_id: int = 0) -> Dict[str, Any]:
        """Get full agent info (logic)."""
        aid = agent_id if agent_id > 0 else self.agent_id
        if aid is None or aid == 0:
            return {"error": "No agent_id provided"}

        if not self.client.agent_exists(aid):
            return {"error": f"Agent {aid} not found"}

        owner = self.client.get_agent_owner(aid)
        wallet = self.client.get_agent_wallet(aid)
        rep = self.client.get_reputation(aid)
        key_count = self.client.get_tee_key_count(aid)

        return {
            "agent_id": aid,
            "owner": owner,
            "wallet": wallet,
            "reputation": rep,
            "tee_key_count": key_count,
        }



    # ------------------------------------------------------------------
    # Logic: submit_feedback
    # ------------------------------------------------------------------

    async def submit_feedback(
        self,
        target_agent_id: int,
        rating: int,
        comment: str = "",
    ) -> Dict[str, Any]:
        """Submit feedback (logic)."""
        if rating < 1 or rating > 5:
            return {"error": "Rating must be 1-5"}

        try:
            score = rating * 20
            receipt = self.client.give_feedback(
                agent_id=target_agent_id,
                score=score,
                decimals=2,
                comment=comment,
                tags=["remittance"],
            )
            return {
                "success": True,
                "target_agent_id": target_agent_id,
                "rating": rating,
                "score": score,
                "tx_hash": receipt.get("transactionHash", "").hex()
                if hasattr(receipt.get("transactionHash", ""), "hex")
                else str(receipt),
            }
        except Exception as e:
            return {"error": str(e)}



    # ------------------------------------------------------------------
    # Logic: register_agent_onchain
    # ------------------------------------------------------------------

    async def register_agent_onchain(self, token_uri: str = "") -> Dict[str, Any]:
        """Register agent (logic)."""
        try:
            receipt = self.client.register_agent(token_uri=token_uri)
            return {
                "success": True,
                "receipt": str(receipt),
            }
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Logic: record_successful_task
    # ------------------------------------------------------------------

    async def record_successful_task(self, agent_id: int = 0) -> Dict[str, Any]:
        """Record a successful task completion to build reputation history.
        
        In a full implementation, this would submit a proof of task completion
        to an oracle or the reputation registry directly.
        """
        aid = agent_id if agent_id > 0 else self.agent_id
        logger.info(f"Registry: Recording successful task for Agent {aid}")
        
        # Simulation of on-chain interaction
        # In reality, this might call self.client.submit_task_proof(...)
        return {
            "success": True,
            "agent_id": aid,
            "action": "task_completion_recorded", 
            "timestamp": "now"
        }

