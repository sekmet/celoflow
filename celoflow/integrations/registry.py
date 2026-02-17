"""On-chain registry client for ERC-8004 contracts."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.contract import Contract

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Minimal ABIs – only the functions we call from the agent
# -------------------------------------------------------------------

IDENTITY_REGISTRY_ABI = json.loads("""[
  {"inputs":[],"name":"register","outputs":[{"name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"name":"tokenUri","type":"string"},{"components":[{"name":"key","type":"string"},{"name":"value","type":"bytes"}],"name":"metadata","type":"tuple[]"}],"name":"register","outputs":[{"name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"name":"agentId","type":"uint256"}],"name":"exists","outputs":[{"name":"","type":"bool"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"tokenId","type":"uint256"}],"name":"ownerOf","outputs":[{"name":"","type":"address"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"agentId","type":"uint256"}],"name":"getAgentWallet","outputs":[{"name":"","type":"address"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"agentId","type":"uint256"},{"name":"key","type":"string"}],"name":"getMetadata","outputs":[{"name":"","type":"bytes"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"agentId","type":"uint256"},{"name":"wallet","type":"address"}],"name":"setAgentWallet","outputs":[],"stateMutability":"nonpayable","type":"function"}
]""")

REPUTATION_REGISTRY_ABI = json.loads("""[
  {"inputs":[{"name":"agentId","type":"uint256"},{"name":"score","type":"uint256"},{"name":"decimals","type":"uint8"},{"name":"comment","type":"string"},{"name":"tags","type":"string[]"}],"name":"giveFeedback","outputs":[],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"name":"agentId","type":"uint256"}],"name":"getSummary","outputs":[{"name":"avgScore","type":"uint256"},{"name":"totalCount","type":"uint256"},{"name":"avgDecimals","type":"uint8"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"agentId","type":"uint256"}],"name":"getFeedbackCount","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"agentId","type":"uint256"}],"name":"hasFeedback","outputs":[{"name":"","type":"bool"}],"stateMutability":"view","type":"function"}
]""")

TEE_REGISTRY_ABI = json.loads("""[
  {"inputs":[{"name":"agentId","type":"uint256"},{"name":"pubkey","type":"address"}],"name":"hasKey","outputs":[{"name":"","type":"bool"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"agentId","type":"uint256"}],"name":"getKeyCount","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"agentId","type":"uint256"}],"name":"getAgentKeys","outputs":[{"name":"","type":"address[]"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"verifier","type":"address"}],"name":"isVerifier","outputs":[{"name":"","type":"bool"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"agentId","type":"uint256"},{"name":"teeArch","type":"bytes32"},{"name":"codeMeasurement","type":"bytes32"},{"name":"pubkey","type":"address"},{"name":"codeConfigUri","type":"string"},{"name":"verifier","type":"address"},{"name":"proof","type":"bytes"}],"name":"addKey","outputs":[],"stateMutability":"nonpayable","type":"function"}
]""")


class RegistryClient:
    """Client for interacting with ERC-8004 registry contracts on-chain."""

    def __init__(
        self,
        rpc_url: str,
        identity_registry_address: str,
        reputation_registry_address: str,
        tee_registry_address: str,
        private_key: Optional[str] = None,
    ) -> None:
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.account: Optional[LocalAccount] = None
        if private_key:
            self.account = Account.from_key(private_key)

        self.identity_registry: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(identity_registry_address),
            abi=IDENTITY_REGISTRY_ABI,
        )
        self.reputation_registry: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(reputation_registry_address),
            abi=REPUTATION_REGISTRY_ABI,
        )
        self.tee_registry: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(tee_registry_address),
            abi=TEE_REGISTRY_ABI,
        )

    # ── Identity ──────────────────────────────────────────────────

    def agent_exists(self, agent_id: int) -> bool:
        return self.identity_registry.functions.exists(agent_id).call()

    def get_agent_owner(self, agent_id: int) -> str:
        return self.identity_registry.functions.ownerOf(agent_id).call()

    def get_agent_wallet(self, agent_id: int) -> str:
        return self.identity_registry.functions.getAgentWallet(agent_id).call()

    def get_agent_metadata(self, agent_id: int, key: str) -> bytes:
        return self.identity_registry.functions.getMetadata(agent_id, key).call()

    def register_agent(self, token_uri: str = "", metadata: Optional[List[Dict]] = None) -> int:
        """Register a new agent on-chain. Returns the new agent ID."""
        if not self.account:
            raise RuntimeError("No private key configured for write operations")

        if token_uri and metadata:
            entries = [(m["key"], m["value"]) for m in metadata]
            tx = self.identity_registry.functions.register(token_uri, entries)
        else:
            tx = self.identity_registry.functions.register()

        return self._send_tx(tx)

    def set_agent_wallet(self, agent_id: int, wallet: str) -> Any:
        """Set the agent wallet address on-chain."""
        if not self.account:
            raise RuntimeError("No private key configured for write operations")
        
        tx = self.identity_registry.functions.setAgentWallet(
            agent_id, Web3.to_checksum_address(wallet)
        )
        return self._send_tx(tx)

    # ── Reputation ────────────────────────────────────────────────

    def get_reputation(self, agent_id: int) -> Dict[str, Any]:
        avg_score, total_count, avg_decimals = (
            self.reputation_registry.functions.getSummary(agent_id).call()
        )
        return {
            "avg_score": avg_score / (10 ** avg_decimals) if avg_decimals > 0 else avg_score,
            "total_count": total_count,
            "raw_score": avg_score,
            "decimals": avg_decimals,
        }

    def has_feedback(self, agent_id: int) -> bool:
        return self.reputation_registry.functions.hasFeedback(agent_id).call()

    def give_feedback(
        self,
        agent_id: int,
        score: int,
        decimals: int = 2,
        comment: str = "",
        tags: Optional[List[str]] = None,
    ) -> Any:
        """Submit reputation feedback for an agent on-chain."""
        if not self.account:
            raise RuntimeError("No private key configured for write operations")

        tx = self.reputation_registry.functions.giveFeedback(
            agent_id,
            score,
            decimals,
            comment,
            tags or [],
        )
        return self._send_tx(tx)

    # ── TEE ───────────────────────────────────────────────────────

    def has_tee_key(self, agent_id: int, pubkey: str) -> bool:
        return self.tee_registry.functions.hasKey(
            agent_id, Web3.to_checksum_address(pubkey)
        ).call()

    def get_tee_key_count(self, agent_id: int) -> int:
        return self.tee_registry.functions.getKeyCount(agent_id).call()

    def get_agent_keys(self, agent_id: int) -> List[str]:
        return self.tee_registry.functions.getAgentKeys(agent_id).call()

    # ── Internal ──────────────────────────────────────────────────

    def _send_tx(self, tx_func: Any) -> Any:
        """Build, sign, and send a transaction. Returns the receipt."""
        if not self.account:
            raise RuntimeError("No private key configured")

        tx = tx_func.build_transaction(
            {
                "from": self.account.address,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
                "gas": 500_000,
                "gasPrice": self.w3.eth.gas_price,
            }
        )
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        logger.info("TX mined: %s (gas used: %d)", tx_hash.hex(), receipt["gasUsed"])
        return receipt
