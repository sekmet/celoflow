"""TEE Wallet Service — manages TEE address derivation, balance tracking, and funding.

Provides a clean abstraction over the TEE plugin for:
- TEE address derivation and balance tracking
- User wallet → TEE address transfer preparation
- Auto-swap for TEE address token shortages (delegates to existing _auto_swap_for_token)
- Balance checks and funding status for transfer previews

Design decisions:
- TEE address is derived from the TEE plugin's get_account() method
- Balance checks use the Mento plugin's w3 connection
- Auto-swap is delegated to the existing mechanism in remittance_tools
- This service is stateless — all state is on-chain
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from plugins.tee_plugin import TEEPlugin
    from plugins.mento_plugin import MentoPlugin

logger = logging.getLogger(__name__)

# Supported tokens and their decimal places
TOKEN_DECIMALS: Dict[str, int] = {
    "USDm": 18, "EURm": 18, "BRLm": 18, "KESm": 18, "XOFm": 18,
    "PHPm": 18, "COPm": 18, "GBPm": 18, "CADm": 18, "AUDm": 18,
    "ZARm": 18, "GHSm": 18, "NGNm": 18, "JPYm": 18, "CHFm": 18,
    "CELO": 18, "USDT": 6, "axlUSDC": 6,
}

# Token aliases
TOKEN_ALIASES: Dict[str, str] = {
    "cUSD": "USDm",
    "cEUR": "EURm",
    "cREAL": "BRLm",
}

ERC20_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class TEEWalletService:
    """Manage TEE wallet address, balance tracking, and funding status.

    Used by TransferPreviewService and send_token to ensure the TEE wallet
    has sufficient token balance before executing transfers.
    """

    def __init__(
        self,
        tee_plugin: Optional["TEEPlugin"] = None,
        mento_plugin: Optional["MentoPlugin"] = None,
    ) -> None:
        self._tee = tee_plugin
        self._mento = mento_plugin
        logger.info("TEEWalletService initialised")

    # ------------------------------------------------------------------
    # Public: get_tee_address
    # ------------------------------------------------------------------

    def get_tee_address(self) -> Optional[str]:
        """Return the TEE wallet address.

        Returns:
            Checksummed TEE wallet address or None if not available
        """
        if not self._tee:
            return None
        try:
            account = self._tee.get_account()
            return account.address
        except Exception as e:
            logger.warning("Failed to get TEE address: %s", e)
            return None

    # ------------------------------------------------------------------
    # Public: get_token_balance
    # ------------------------------------------------------------------

    async def get_token_balance(self, token: str) -> Dict[str, Any]:
        """Get TEE wallet balance for a specific token.

        Args:
            token: Token symbol (e.g. BRLm, ZARm, USDm, CELO)

        Returns:
            Balance info with amount, decimals, and address
        """
        tee_address = self.get_tee_address()
        if not tee_address:
            return {"error": "TEE address not available", "balance": 0.0}

        if not self._mento or not self._mento.w3 or not self._mento.w3.is_connected():
            return {
                "error": "RPC not connected",
                "tee_address": tee_address,
                "balance": 0.0,
                "token": token,
            }

        try:
            from integrations.chain_config import ChainConfig
            from web3 import Web3

            config = ChainConfig.celo_sepolia()
            resolved = TOKEN_ALIASES.get(token, token)
            token_address = config.token_addresses.get(resolved)

            if not token_address:
                return {
                    "error": f"Unknown token: {token}",
                    "tee_address": tee_address,
                    "balance": 0.0,
                }

            decimals = TOKEN_DECIMALS.get(resolved, 18)
            contract = self._mento.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=ERC20_ABI,
            )
            balance_wei = contract.functions.balanceOf(tee_address).call()
            balance = balance_wei / (10 ** decimals)

            return {
                "tee_address": tee_address,
                "token": resolved,
                "token_address": token_address,
                "balance": round(balance, 6),
                "balance_wei": balance_wei,
                "decimals": decimals,
            }

        except Exception as e:
            logger.error("Balance check failed for %s: %s", token, e)
            return {
                "error": str(e),
                "tee_address": tee_address,
                "balance": 0.0,
                "token": token,
            }

    # ------------------------------------------------------------------
    # Public: get_all_balances
    # ------------------------------------------------------------------

    async def get_all_balances(self, tokens: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get TEE wallet balances for multiple tokens.

        Args:
            tokens: List of token symbols (None = all supported tokens)

        Returns:
            Dict of token -> balance info
        """
        if tokens is None:
            tokens = list(TOKEN_DECIMALS.keys())

        tee_address = self.get_tee_address()
        if not tee_address:
            return {"error": "TEE address not available"}

        balances: Dict[str, Any] = {"tee_address": tee_address, "tokens": {}}

        for token in tokens:
            result = await self.get_token_balance(token)
            if "error" not in result:
                balances["tokens"][token] = result["balance"]
            else:
                balances["tokens"][token] = 0.0

        return balances

    # ------------------------------------------------------------------
    # Public: check_funding_status
    # ------------------------------------------------------------------

    async def check_funding_status(
        self,
        token: str,
        required_amount: float,
    ) -> Dict[str, Any]:
        """Check if TEE wallet has sufficient balance for a transfer.

        Args:
            token: Token symbol
            required_amount: Amount needed

        Returns:
            Funding status with sufficient flag, balance, deficit, and auto_swap_needed
        """
        balance_info = await self.get_token_balance(token)

        if "error" in balance_info:
            return {
                "sufficient": True,  # Assume sufficient if we can't check
                "auto_swap_needed": False,
                "reason": balance_info["error"],
                "token": token,
                "required": required_amount,
            }

        balance = balance_info["balance"]
        sufficient = balance >= required_amount
        deficit = max(0.0, required_amount - balance)

        # Check CELO balance for auto-swap
        celo_balance_info = await self.get_token_balance("CELO")
        celo_balance = celo_balance_info.get("balance", 0.0)

        # Estimate CELO needed for swap (rough: 1 CELO ≈ 0.5 USD, add 10% buffer)
        celo_needed_estimate = deficit * 2.2  # 2x rate + 10% slippage buffer

        return {
            "sufficient": sufficient,
            "auto_swap_needed": not sufficient and celo_balance > celo_needed_estimate,
            "auto_swap_possible": celo_balance > celo_needed_estimate,
            "tee_address": balance_info.get("tee_address"),
            "token": token,
            "balance": balance,
            "required": required_amount,
            "deficit": round(deficit, 6),
            "celo_balance": round(celo_balance, 6),
            "celo_needed_estimate": round(celo_needed_estimate, 6),
        }

    # ------------------------------------------------------------------
    # Public: prepare_transfer
    # ------------------------------------------------------------------

    async def prepare_transfer(
        self,
        token: str,
        amount: float,
        recipient: str,
    ) -> Dict[str, Any]:
        """Prepare a transfer by verifying TEE wallet readiness.

        This is called before send_token to ensure the TEE wallet is funded.
        Returns preparation status including whether auto-swap will be needed.

        Args:
            token: Token to transfer
            amount: Amount to transfer
            recipient: Recipient address

        Returns:
            Preparation status with ready flag and any required actions
        """
        tee_address = self.get_tee_address()
        if not tee_address:
            return {
                "ready": False,
                "error": "TEE wallet not available",
            }

        funding = await self.check_funding_status(token, amount)

        actions_required = []
        if not funding["sufficient"]:
            if funding.get("auto_swap_possible"):
                actions_required.append({
                    "action": "auto_swap",
                    "description": f"Auto-swap CELO → USDm → {token}",
                    "celo_needed": funding["celo_needed_estimate"],
                })
            else:
                return {
                    "ready": False,
                    "error": f"Insufficient {token} and CELO for auto-swap",
                    "tee_address": tee_address,
                    "token": token,
                    "balance": funding["balance"],
                    "required": amount,
                    "celo_balance": funding.get("celo_balance", 0.0),
                }

        return {
            "ready": True,
            "tee_address": tee_address,
            "token": token,
            "amount": amount,
            "recipient": recipient,
            "balance": funding["balance"],
            "sufficient": funding["sufficient"],
            "auto_swap_needed": not funding["sufficient"],
            "actions_required": actions_required,
        }

    # ------------------------------------------------------------------
    # Public: get_tee_info
    # ------------------------------------------------------------------

    async def get_tee_info(self) -> Dict[str, Any]:
        """Get comprehensive TEE wallet information.

        Returns:
            TEE wallet info with address, key balances, and status
        """
        tee_address = self.get_tee_address()
        if not tee_address:
            return {"error": "TEE wallet not available"}

        # Get key token balances
        key_tokens = ["CELO", "USDm", "BRLm", "KESm", "EURm"]
        balances = {}
        for token in key_tokens:
            result = await self.get_token_balance(token)
            balances[token] = result.get("balance", 0.0)

        return {
            "tee_address": tee_address,
            "balances": balances,
            "rpc_connected": (
                self._mento is not None
                and self._mento.w3 is not None
                and self._mento.w3.is_connected()
            ),
        }
