"""TEE Plugin — Trusted Execution Environment identity and attestation.

Uses the Dstack SDK in production or a local private key in dev mode.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional

from eth_account import Account
from eth_account.signers.local import LocalAccount

from contextwise import AgentPlugin, AgentContext
from agents import function_tool

logger = logging.getLogger(__name__)


class TEEPlugin(AgentPlugin[AgentContext]):
    """Plugin for TEE-backed key derivation, attestation, and message signing."""

    name = "tee"

    def __init__(
        self,
        domain: str = "celoflow.remittance",
        salt: str = "remittance-agent-v1",
        use_tee: bool = False,
        tee_endpoint: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.domain = domain
        self.salt = salt
        self.use_tee = use_tee
        self.tee_endpoint = tee_endpoint
        self.tee_client: Any = None
        self.account: Optional[LocalAccount] = None
        self.address: Optional[str] = None

        if use_tee:
            self._init_tee(tee_endpoint)
        elif private_key:
            self.account = Account.from_key(private_key)
            self.address = self.account.address
            logger.info("TEEPlugin: dev-mode with account %s", self.address)
        else:
            # Generate ephemeral key
            self.account = Account.create()
            self.address = self.account.address
            logger.warning("TEEPlugin: no key provided — using ephemeral key %s", self.address)


    # ------------------------------------------------------------------
    # TEE initialisation (only when use_tee=True)
    # ------------------------------------------------------------------

    def _init_tee(self, endpoint: Optional[str]) -> None:
        try:
            from dstack_sdk import DstackClient  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "dstack-sdk is required for TEE mode. "
                "Install with: uv add dstack-sdk"
            )

        # DstackClient accepts either:
        #   - An HTTP URL (http://... or https://...)
        #   - A unix socket path (absolute path to .sock file)
        # If endpoint is None, the SDK looks at DSTACK_SIMULATOR_ENDPOINT env
        # or falls back to /var/run/dstack.sock
        self.tee_client = DstackClient(endpoint) if endpoint else DstackClient()
        logger.info("TEEPlugin: DstackClient connected to %s", endpoint or "(default)")
        self._derive_tee_key()

    def _derive_tee_key(self) -> None:
        """Derive a deterministic key inside the TEE enclave."""
        path = f"{self.domain}/{self.salt}"
        # DstackClient.get_key() returns GetKeyResponse with .key (hex string)
        result = self.tee_client.get_key(path=path, purpose="secp256k1")
        # decode_key() converts hex string to bytes
        key_bytes = result.decode_key()
        # Use first 32 bytes as the private key
        private_key_bytes = key_bytes[:32]
        self.account = Account.from_key(private_key_bytes)
        self.address = self.account.address
        logger.info("TEEPlugin: TEE key derived — %s", self.address)

    # ------------------------------------------------------------------
    # Agent tool: get_attestation
    # ------------------------------------------------------------------

    async def get_attestation(self) -> Dict[str, Any]:
        """Generate a remote attestation (logic)."""
        if not self.use_tee or not self.tee_client:
            return {
                "mode": "development",
                "address": self.address,
                "message": "TEE attestation not available in dev mode",
            }

        # Prepare report data (max 64 bytes for get_quote)
        app_data = hashlib.sha256(
            f"{self.domain}:{self.address}".encode()
        ).digest()
        quote_result = self.tee_client.get_quote(app_data)
        return {
            "quote": quote_result.quote,
            "event_log": quote_result.event_log,
            "address": self.address,
            "domain": self.domain,
        }



    # ------------------------------------------------------------------
    # Logic: sign_message
    # ------------------------------------------------------------------

    async def sign_message(self, message: str) -> Dict[str, str]:
        """Sign a message (logic)."""
        if not self.account:
            return {"error": "No account configured"}

        msg_hash = hashlib.sha256(message.encode()).digest()
        signed = self.account.unsafe_sign_hash(msg_hash)
        return {
            "signature": signed.signature.hex(),
            "signer": self.address or "",
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def configure_agent(self, agent: Any) -> Any:
        """Register tools with the agent."""
        if hasattr(agent, "tools"):
            
            @function_tool
            async def get_attestation_action() -> str:
                """Generate a remote attestation from the TEE enclave proving this agent runs in genuine Intel TDX."""
                result = await self.get_attestation()
                return json.dumps(result)

            @function_tool
            async def sign_message_action(message: str) -> str:
                """Sign a message with the TEE-derived key.

                Args:
                    message: The plaintext message to sign
                """
                result = await self.sign_message(message)
                return json.dumps(result)

            agent.tools.append(get_attestation_action)
            agent.tools.append(sign_message_action)
        return agent
    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_account(self) -> LocalAccount:
        """Return the current signing account."""
        if not self.account:
            raise RuntimeError("TEEPlugin: no account available")
        return self.account
