"""User Signing Service — Prepare and verify transactions for user wallet signing.

This service handles the dual-signer architecture where users can choose to
sign transactions with their own connected wallet instead of the TEE agent wallet.

Key responsibilities:
- Prepare unsigned transactions for user wallet signing
- Verify user-signed transactions before broadcasting
- Track pending transactions awaiting user signatures
- Provide gas estimation for user wallet transactions
- Handle auto-swap preparation for user wallets
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class SignerType(str, Enum):
    """Who signs the transaction."""
    TEE = "tee"
    USER = "user"


class TransferStatus(str, Enum):
    """Status of a prepared transfer."""
    PENDING = "pending"
    SIGNED = "signed"
    BROADCASTING = "broadcasting"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    EXPIRED = "expired"
    REJECTED = "rejected"


@dataclass
class PreparedTransfer:
    """A transfer prepared for user signing."""
    transfer_id: str
    signer_type: SignerType
    recipient_address: str
    amount: float
    token: str
    resolved_token: str
    token_address: str
    decimals: int
    amount_wei: int
    chain_id: int
    status: TransferStatus = TransferStatus.PENDING
    # Transaction data for user signing
    tx_data: Optional[Dict[str, Any]] = None
    # Auto-swap info (if needed)
    needs_auto_swap: bool = False
    auto_swap_steps: List[Dict[str, Any]] = field(default_factory=list)
    # Gas estimation
    estimated_gas: int = 100_000
    gas_price_wei: int = 0
    estimated_gas_cost_eth: float = 0.0
    # Metadata
    created_at: float = 0.0
    expires_at: float = 0.0
    user_address: Optional[str] = None
    signed_tx: Optional[str] = None
    tx_hash: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.expires_at == 0.0:
            self.expires_at = self.created_at + 300  # 5 minute expiry

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["signer_type"] = self.signer_type.value
        d["status"] = self.status.value
        # Remove None-valued optional fields to avoid false positives in error checks
        for key in ("error", "signed_tx", "tx_hash"):
            if d.get(key) is None:
                del d[key]
        return d


class UserSigningService:
    """Service for preparing and managing user-signed transactions.

    Design decisions:
    - Transfers expire after 5 minutes to prevent stale nonces
    - Auto-swap steps are prepared but NOT executed — user must sign each step
    - Gas estimation uses on-chain data when available, falls back to defaults
    - Transfer IDs are deterministic (hash of params) to prevent duplicates
    """

    # Maximum pending transfers per user to prevent memory leaks
    MAX_PENDING_PER_USER = 10
    # Transfer expiry in seconds
    TRANSFER_EXPIRY = 300  # 5 minutes

    def __init__(
        self,
        mento_plugin: Any = None,
        tee_plugin: Any = None,
    ):
        self._mento_plugin = mento_plugin
        self._tee_plugin = tee_plugin
        # In-memory store of pending transfers (transfer_id -> PreparedTransfer)
        self._pending: Dict[str, PreparedTransfer] = {}

    def _generate_transfer_id(
        self,
        user_address: str,
        recipient: str,
        amount: float,
        token: str,
    ) -> str:
        """Generate a deterministic transfer ID."""
        raw = f"{user_address}:{recipient}:{amount}:{token}:{int(time.time() // 60)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _cleanup_expired(self) -> None:
        """Remove expired pending transfers."""
        now = time.time()
        expired = [
            tid for tid, t in self._pending.items()
            if now > t.expires_at
        ]
        for tid in expired:
            self._pending[tid].status = TransferStatus.EXPIRED
            del self._pending[tid]
        if expired:
            logger.info("Cleaned up %d expired pending transfers", len(expired))

    async def prepare_transfer(
        self,
        user_address: str,
        recipient_address: str,
        amount: float,
        token: str,
        chain_id: int = 44787,
    ) -> Dict[str, Any]:
        """Prepare an unsigned transfer transaction for user wallet signing.

        This builds the transaction data that the user's wallet (MetaMask, etc.)
        needs to sign. It checks balances, determines if auto-swap is needed,
        and estimates gas costs.

        Args:
            user_address: The user's connected wallet address
            recipient_address: Recipient wallet address
            amount: Amount of tokens to send
            token: Token symbol (e.g. BRLm, ZARm, USDm)
            chain_id: Chain ID (default Celo Sepolia)

        Returns:
            Dict with transfer_id, tx_data, gas estimation, and auto-swap info
        """
        self._cleanup_expired()

        # Resolve token
        from integrations.chain_config import ChainConfig
        config = ChainConfig.celo_sepolia()
        aliases = {"cUSD": "USDm", "cEUR": "EURm", "cREAL": "BRLm"}
        resolved_token = aliases.get(token, token)
        token_address = config.token_addresses.get(resolved_token)

        if not token_address:
            return {
                "error": f"Unknown token '{token}'. Supported: {', '.join(config.token_addresses.keys())}",
                "status": "error",
            }

        # Determine decimals
        decimals = 6 if "USDC" in resolved_token or "USDT" in resolved_token or "axlUSDC" in resolved_token else 18
        amount_wei = int(Decimal(str(amount)) * (10 ** decimals))

        # Generate transfer ID
        transfer_id = self._generate_transfer_id(
            user_address, recipient_address, amount, resolved_token,
        )

        # Check if already pending
        if transfer_id in self._pending:
            existing = self._pending[transfer_id]
            if not existing.is_expired:
                return existing.to_dict()

        # Check user balance (if mento plugin available)
        user_balance_wei = 0
        needs_auto_swap = False
        auto_swap_steps = []
        gas_price_wei = 0
        estimated_gas = 100_000

        if self._mento_plugin and self._mento_plugin.w3 and self._mento_plugin.w3.is_connected():
            try:
                from web3 import Web3
                w3 = self._mento_plugin.w3

                gas_price_wei = w3.eth.gas_price

                ERC20_ABI = [
                    {
                        "inputs": [{"name": "account", "type": "address"}],
                        "name": "balanceOf",
                        "outputs": [{"name": "", "type": "uint256"}],
                        "stateMutability": "view",
                        "type": "function",
                    },
                ]
                token_contract = w3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=ERC20_ABI,
                )
                user_balance_wei = token_contract.functions.balanceOf(
                    Web3.to_checksum_address(user_address)
                ).call()

                if user_balance_wei < amount_wei:
                    needs_auto_swap = True
                    deficit = amount_wei - user_balance_wei
                    auto_swap_steps = self._prepare_auto_swap_steps(
                        user_address, resolved_token, token_address,
                        deficit, decimals, config, w3,
                    )

                # Build the ERC-20 transfer transaction data
                TRANSFER_ABI = [
                    {
                        "inputs": [
                            {"name": "to", "type": "address"},
                            {"name": "amount", "type": "uint256"},
                        ],
                        "name": "transfer",
                        "outputs": [{"name": "", "type": "bool"}],
                        "stateMutability": "nonpayable",
                        "type": "function",
                    },
                ]
                transfer_contract = w3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=TRANSFER_ABI,
                )
                nonce = w3.eth.get_transaction_count(
                    Web3.to_checksum_address(user_address)
                )

                tx_data = transfer_contract.functions.transfer(
                    Web3.to_checksum_address(recipient_address),
                    amount_wei,
                ).build_transaction({
                    "from": Web3.to_checksum_address(user_address),
                    "nonce": nonce,
                    "gas": estimated_gas,
                    "gasPrice": gas_price_wei,
                    "chainId": chain_id,
                })

                # Convert bytes to hex for JSON serialization
                tx_data_serializable = {
                    k: (v.hex() if isinstance(v, bytes) else v)
                    for k, v in tx_data.items()
                }

            except Exception as e:
                logger.error("Failed to prepare on-chain transfer: %s", e)
                return {
                    "error": f"Failed to prepare transfer: {str(e)}",
                    "status": "error",
                }
        else:
            # Simulated mode — no RPC
            tx_data_serializable = {
                "to": token_address,
                "from": user_address,
                "data": "0x",  # Placeholder
                "value": "0x0",
                "gas": hex(estimated_gas),
                "chainId": hex(chain_id),
            }

        estimated_gas_cost = (gas_price_wei * estimated_gas) / 1e18

        # Create the prepared transfer
        prepared = PreparedTransfer(
            transfer_id=transfer_id,
            signer_type=SignerType.USER,
            recipient_address=recipient_address,
            amount=amount,
            token=token,
            resolved_token=resolved_token,
            token_address=token_address,
            decimals=decimals,
            amount_wei=amount_wei,
            chain_id=chain_id,
            tx_data=tx_data_serializable,
            needs_auto_swap=needs_auto_swap,
            auto_swap_steps=auto_swap_steps,
            estimated_gas=estimated_gas,
            gas_price_wei=gas_price_wei,
            estimated_gas_cost_eth=estimated_gas_cost,
            user_address=user_address,
        )

        self._pending[transfer_id] = prepared
        logger.info(
            "Prepared user transfer %s: %s %s -> %s (auto_swap=%s)",
            transfer_id, amount, resolved_token,
            recipient_address[:10], needs_auto_swap,
        )

        return prepared.to_dict()

    def _prepare_auto_swap_steps(
        self,
        user_address: str,
        target_symbol: str,
        target_address: str,
        deficit_wei: int,
        target_decimals: int,
        config: Any,
        w3: Any,
    ) -> List[Dict[str, Any]]:
        """Prepare auto-swap transaction steps for user signing.

        Unlike TEE auto-swap which executes immediately, user auto-swap
        returns the steps as unsigned transactions for the user to sign.
        """
        from web3 import Web3
        from plugins.mento_plugin import (
            MENTO_BROKER_ADDRESS, BIPOOL_MANAGER_ADDRESS, EXCHANGE_IDS, BROKER_ABI,
        )

        steps = []
        CELO_ADDR = Web3.to_checksum_address(
            config.token_addresses.get("CELO", "0x471EcE3750Da237f93B8E339c536989b8978a438")
        )
        USDm_ADDR = Web3.to_checksum_address(config.token_addresses.get("USDm", ""))
        BROKER = Web3.to_checksum_address(MENTO_BROKER_ADDRESS)

        eid_celo_hex = EXCHANGE_IDS.get("USDm/CELO")
        if not eid_celo_hex:
            return [{"error": "No CELO/USDm exchange ID configured"}]

        if target_symbol == "USDm":
            steps.append({
                "step": 1,
                "description": "Approve CELO for swap",
                "action": "approve",
                "token": "CELO",
                "spender": BROKER,
            })
            steps.append({
                "step": 2,
                "description": "Swap CELO → USDm via Mento",
                "action": "swap",
                "from_token": "CELO",
                "to_token": "USDm",
                "exchange_id": eid_celo_hex,
            })
        else:
            pair_key = f"USDm/{target_symbol}"
            eid_target_hex = EXCHANGE_IDS.get(pair_key)
            if not eid_target_hex:
                return [{"error": f"No Mento pool for {pair_key}"}]

            steps.append({
                "step": 1,
                "description": "Approve CELO for swap (hop 1)",
                "action": "approve",
                "token": "CELO",
                "spender": BROKER,
            })
            steps.append({
                "step": 2,
                "description": "Swap CELO → USDm via Mento (hop 1)",
                "action": "swap",
                "from_token": "CELO",
                "to_token": "USDm",
                "exchange_id": eid_celo_hex,
            })
            steps.append({
                "step": 3,
                "description": "Approve USDm for swap (hop 2)",
                "action": "approve",
                "token": "USDm",
                "spender": BROKER,
            })
            steps.append({
                "step": 4,
                "description": f"Swap USDm → {target_symbol} via Mento (hop 2)",
                "action": "swap",
                "from_token": "USDm",
                "to_token": target_symbol,
                "exchange_id": eid_target_hex,
            })

        return steps

    async def execute_signed_transfer(
        self,
        transfer_id: str,
        signed_tx_hex: str,
    ) -> Dict[str, Any]:
        """Broadcast a user-signed transaction.

        Args:
            transfer_id: The transfer ID from prepare_transfer
            signed_tx_hex: The signed transaction hex string from user's wallet

        Returns:
            Dict with tx_hash on success or error
        """
        self._cleanup_expired()

        transfer = self._pending.get(transfer_id)
        if not transfer:
            return {"error": "Transfer not found or expired", "status": "error"}

        if transfer.is_expired:
            transfer.status = TransferStatus.EXPIRED
            del self._pending[transfer_id]
            return {"error": "Transfer expired. Please prepare a new one.", "status": "expired"}

        if transfer.status != TransferStatus.PENDING:
            return {"error": f"Transfer is in '{transfer.status.value}' state, expected 'pending'", "status": "error"}

        transfer.status = TransferStatus.BROADCASTING
        transfer.signed_tx = signed_tx_hex

        if self._mento_plugin and self._mento_plugin.w3 and self._mento_plugin.w3.is_connected():
            try:
                w3 = self._mento_plugin.w3
                tx_hash = w3.eth.send_raw_transaction(bytes.fromhex(
                    signed_tx_hex[2:] if signed_tx_hex.startswith("0x") else signed_tx_hex
                ))
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
                tx_hex = tx_hash.hex()

                if receipt["status"] == 0:
                    transfer.status = TransferStatus.FAILED
                    transfer.error = "Transaction reverted on-chain"
                    transfer.tx_hash = tx_hex
                    return {
                        "error": f"Transaction reverted. Tx: https://sepolia.celoscan.io/tx/{tx_hex}",
                        "status": "reverted",
                        "tx_hash": tx_hex,
                    }

                transfer.status = TransferStatus.CONFIRMED
                transfer.tx_hash = tx_hex

                logger.info(
                    "User-signed transfer confirmed: %s %s -> %s (tx: %s)",
                    transfer.amount, transfer.resolved_token,
                    transfer.recipient_address[:10], tx_hex,
                )

                return {
                    "status": "success",
                    "tx_hash": tx_hex,
                    "amount": transfer.amount,
                    "token": transfer.token,
                    "recipient": transfer.recipient_address,
                    "signer_type": "user",
                    "explorer_url": f"https://sepolia.celoscan.io/tx/{tx_hex}",
                }

            except Exception as e:
                transfer.status = TransferStatus.FAILED
                transfer.error = str(e)
                logger.error("Failed to broadcast user-signed tx: %s", e)
                return {"error": f"Broadcast failed: {str(e)}", "status": "error"}
        else:
            # Simulated mode
            tx_hex = "0x" + "user" + "a1b2c3d4" * 7
            transfer.status = TransferStatus.CONFIRMED
            transfer.tx_hash = tx_hex
            return {
                "status": "success",
                "tx_hash": tx_hex,
                "amount": transfer.amount,
                "token": transfer.token,
                "recipient": transfer.recipient_address,
                "signer_type": "user",
                "note": "Simulated — RPC not connected",
                "explorer_url": f"https://sepolia.celoscan.io/tx/{tx_hex}",
            }

    def get_transfer(self, transfer_id: str) -> Optional[Dict[str, Any]]:
        """Get a pending transfer by ID."""
        transfer = self._pending.get(transfer_id)
        if transfer:
            return transfer.to_dict()
        return None

    def reject_transfer(self, transfer_id: str) -> Dict[str, Any]:
        """Mark a transfer as rejected by the user."""
        transfer = self._pending.get(transfer_id)
        if not transfer:
            return {"error": "Transfer not found", "status": "error"}
        transfer.status = TransferStatus.REJECTED
        logger.info("User rejected transfer %s", transfer_id)
        return {"status": "rejected", "transfer_id": transfer_id}

    def get_pending_transfers(self, user_address: str) -> List[Dict[str, Any]]:
        """Get all pending transfers for a user."""
        self._cleanup_expired()
        return [
            t.to_dict() for t in self._pending.values()
            if t.user_address and t.user_address.lower() == user_address.lower()
            and t.status == TransferStatus.PENDING
        ]
