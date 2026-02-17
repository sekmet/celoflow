"""Mento Plugin — Celo Mento Protocol currency routing and swaps."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from contextwise import AgentPlugin, AgentContext

logger = logging.getLogger(__name__)

# Mento v2 Broker Address (Celo Sepolia)
# Uses BiPoolManager as the ExchangeProvider for these pairs
MENTO_BROKER_ADDRESS = "0xB9Ae2065142EB79b6c5EB1E8778F883fad6B07Ba"

# Discovered Exchange IDs for Celo Sepolia
EXCHANGE_IDS: Dict[str, str] = {
    # Direction is important; Mento v2 pools are often bi-directional but ID is unique per pair
    "USDm/PHPm": "7952984d7278ca3417febf52815c321984ac3147ced2c02bb6a02b0bcab08413",
    "USDm/XOFm": "c9664df358594c5eaf2f410ab371e2deb8b532ca26162d2bc36d99b8d174567b",
    "USDm/CELO": "3135b662c38265d0655177091f1b647b4fef511103d06c016efdf18b46930d2c",
    "USDm/axlUSDC": "0d739efbfc30f303e8d1976c213b4040850d1af40f174f4169b846f6fd3d2f20",
}

# Broker ABI for getAmountOut and swapIn
BROKER_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "exchangeProvider", "type": "address"},
            {"name": "exchangeId", "type": "bytes32"},
            {"name": "tokenIn", "type": "address"},
            {"name": "tokenOut", "type": "address"},
            {"name": "amountIn", "type": "uint256"}
        ],
        "name": "getAmountOut",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "exchangeId", "type": "bytes32"}],
        "name": "getExchangeProvider",
        "outputs": [{"name": "provider", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "exchangeProvider", "type": "address"},
            {"name": "exchangeId", "type": "bytes32"},
            {"name": "tokenIn", "type": "address"},
            {"name": "tokenOut", "type": "address"},
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"}
        ],
        "name": "swapIn",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

class MentoPlugin(AgentPlugin[AgentContext]):
    """Currency routing and swap estimation via the Celo Mento Protocol."""

    name = "mento"

    def __init__(self, rpc_url: Optional[str] = None) -> None:
        super().__init__()
        self.rpc_url = rpc_url
        self.w3 = None
        self.broker = None
        
        if rpc_url:
            try:
                from web3 import Web3
                self.w3 = Web3(Web3.HTTPProvider(rpc_url))
                if self.w3.is_connected():
                    self.broker = self.w3.eth.contract(
                        address=Web3.to_checksum_address(MENTO_BROKER_ADDRESS),
                        abi=BROKER_ABI
                    )
                    logger.info("MentoPlugin connected to Broker at %s", MENTO_BROKER_ADDRESS)
                else:
                    logger.warning("MentoPlugin failed to connect to RPC: %s", rpc_url)
            except ImportError:
                logger.error("web3 package not installed. MentoPlugin disabled.")

    def configure_agent(self, agent: Any) -> Any:
        return agent

    # ------------------------------------------------------------------

    async def get_amount_out(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        exchange_id_hex: str,
    ) -> int:
        """Call Mento Broker.getAmountOut on-chain.
        
        Args:
            token_in: Checksum address of the input token
            token_out: Checksum address of the output token
            amount_in: Amount in wei (smallest denomination)
            exchange_id_hex: Hex string of the exchange ID (without 0x prefix)
        
        Returns:
            Amount out in wei, or 0 on error
        """
        if not self.broker:
            logger.warning("get_amount_out called but broker not connected")
            return 0
        try:
            from web3 import Web3
            exchange_id = bytes.fromhex(exchange_id_hex)
            provider = self.broker.functions.getExchangeProvider(exchange_id).call()
            amount_out = self.broker.functions.getAmountOut(
                provider,
                exchange_id,
                Web3.to_checksum_address(token_in),
                Web3.to_checksum_address(token_out),
                amount_in,
            ).call()
            logger.info(
                "Broker.getAmountOut: %s → %s (amount_in=%d, amount_out=%d)",
                token_in[:10], token_out[:10], amount_in, amount_out
            )
            return amount_out
        except Exception as e:
            logger.error("Broker.getAmountOut failed: %s", e)
            return 0

    async def find_optimal_route(
        self,
        from_currency: str,
        to_currency: str,
        amount: Decimal,
    ) -> Dict[str, Any]:
        """Find the optimal swap route on Mento."""
        from integrations.chain_config import ChainConfig
        
        # Alias mapping for user convenience (expand with new tokens)
        aliases = {
            "cUSD": "USDm",
            "cEUR": "EURm",
            "cREAL": "BRLm",
            "cKES": "KESm",
            "cCOP": "COPm",
            # Add other c-tokens if commonly used
        }
        src = aliases.get(from_currency, from_currency)
        dst = aliases.get(to_currency, to_currency)
        
        # Support both directions (Pools are bi-directional in v2)
        pair_key = f"{src}/{dst}"
        reverse_key = f"{dst}/{src}"
        
        exchange_id_hex = EXCHANGE_IDS.get(pair_key) or EXCHANGE_IDS.get(reverse_key)
        
        if not exchange_id_hex:
            # We support balances for many tokens, but swaps only for configured pairs
            return {
                "found": False,
                "error": f"No direct Mento v2 pool configuration found for {src} -> {dst}",
                "suggestion": f"Swap capability currently limited. Check balances instead or use {src}/{dst} on a DEX."
            }

        if not self.broker:
             return {
                "found": False,
                "error": "Mento Plugin not connected to RPC",
            }
            
        try:
            config = ChainConfig.celo_sepolia()
            # Dynamic token lookup from expanded ChainConfig
            token_in_addr = config.token_addresses.get(src)
            token_out_addr = config.token_addresses.get(dst)
            
            if not token_in_addr or not token_out_addr:
                 return {"found": False, "error": f"Token addresses not found for {src} or {dst} in ChainConfig"}

            # Standard decimals
            input_decimals = 6 if "USDC" in src or "USDT" in src or "axlUSDC" in src else 18
            output_decimals = 6 if "USDC" in dst or "USDT" in dst or "axlUSDC" in dst else 18
            
            amount_wei = int(amount * (10 ** input_decimals))
            
            # Use get_amount_out (calls Broker on-chain)
            amount_out_wei = await self.get_amount_out(
                token_in=token_in_addr,
                token_out=token_out_addr,
                amount_in=amount_wei,
                exchange_id_hex=exchange_id_hex,
            )
            
            if amount_out_wei == 0:
                return {
                    "found": False,
                    "error": f"Broker returned 0 for {src} → {dst}. Pool may be empty/paused or pair invalid.",
                }
            
            estimated_output = Decimal(amount_out_wei) / Decimal(10 ** output_decimals)
            rate = estimated_output / amount if amount > 0 else 0
            
            return {
                "found": True,
                "exchange": "Mento v2",
                "exchange_id": exchange_id_hex,
                "provider": token_in_addr,  # for execute_swap, provider logic handles logic
                "token_in": token_in_addr,
                "token_out": token_out_addr,
                "input_decimals": input_decimals,
                "output_decimals": output_decimals,
                "from_currency": from_currency,
                "to_currency": to_currency,
                "amount": str(amount),
                "amount_in_wei": amount_wei,
                "amount_out_wei": amount_out_wei,
                "rate": float(rate),
                "estimated_output": float(estimated_output),
                "price_impact": 0.001,
                "liquidity_fee": float(amount) * 0.0025,
                "liquidity": "high",
            }
            
        except Exception as e:
            logger.error("Error finding route: %s", e)
            return {
                "found": False,
                "error": f"RPC Error during route finding: {str(e)}",
            }

    def get_supported_pairs(self) -> list[str]:
        """Return a list of supported swap pairs."""
        return list(EXCHANGE_IDS.keys())

    # ------------------------------------------------------------------

    async def execute_swap(
        self,
        route: Dict[str, Any],
        recipient: str,
        signer: Any,
    ) -> str:
        """Execute a Mento swap on-chain via Broker.swapIn.
        
        Args:
            route: Route dict from find_optimal_route (must contain exchange_id,
                   token_in, token_out, amount_in_wei, amount_out_wei)
            recipient: Wallet address to send the output tokens to
            signer: eth_account LocalAccount for signing the transaction
        
        Returns:
            Transaction hash hex string
        """
        logger.info(
            "Executing Mento swap: %s %s → %s for recipient %s",
            route.get("amount"),
            route.get("from_currency"),
            route.get("to_currency"),
            recipient,
        )
        
        if not self.broker or not self.w3:
            logger.warning("execute_swap: broker not connected, returning stub")
            return "0x" + "a1b2c3d4e5f6" * 5 + "0000"
        
        try:
            from web3 import Web3
            
            exchange_id_hex = route.get("exchange_id", "")
            token_in = route.get("token_in", "")
            token_out = route.get("token_out", "")
            amount_in_wei = route.get("amount_in_wei", 0)
            amount_out_wei = route.get("amount_out_wei", 0)
            
            if not exchange_id_hex or not token_in or not token_out or amount_in_wei == 0:
                logger.error("execute_swap: missing route parameters")
                return "0x" + "0" * 64
            
            exchange_id = bytes.fromhex(exchange_id_hex)
            provider = self.broker.functions.getExchangeProvider(exchange_id).call()
            
            # Apply 1% slippage tolerance
            amount_out_min = int(amount_out_wei * 0.99)
            
            # First, approve the Broker to spend our tokenIn
            ERC20_APPROVE_ABI = [
                {
                    "inputs": [
                        {"name": "spender", "type": "address"},
                        {"name": "amount", "type": "uint256"},
                    ],
                    "name": "approve",
                    "outputs": [{"name": "", "type": "bool"}],
                    "stateMutability": "nonpayable",
                    "type": "function",
                }
            ]
            token_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_in),
                abi=ERC20_APPROVE_ABI,
            )
            nonce = self.w3.eth.get_transaction_count(signer.address)
            approve_tx = token_contract.functions.approve(
                Web3.to_checksum_address(MENTO_BROKER_ADDRESS),
                amount_in_wei,
            ).build_transaction({
                "from": signer.address,
                "nonce": nonce,
                "gas": 100_000,
                "gasPrice": self.w3.eth.gas_price,
            })
            signed_approve = signer.sign_transaction(approve_tx)
            approve_hash = self.w3.eth.send_raw_transaction(signed_approve.raw_transaction)
            self.w3.eth.wait_for_transaction_receipt(approve_hash)
            logger.info("Token approval tx: %s", approve_hash.hex())
            
            # Execute Broker.swapIn
            nonce = self.w3.eth.get_transaction_count(signer.address)
            swap_tx = self.broker.functions.swapIn(
                provider,
                exchange_id,
                Web3.to_checksum_address(token_in),
                Web3.to_checksum_address(token_out),
                amount_in_wei,
                amount_out_min,
            ).build_transaction({
                "from": signer.address,
                "nonce": nonce,
                "gas": 500_000,
                "gasPrice": self.w3.eth.gas_price,
            })
            signed_swap = signer.sign_transaction(swap_tx)
            swap_hash = self.w3.eth.send_raw_transaction(signed_swap.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(swap_hash)
            
            tx_hex = swap_hash.hex()
            logger.info(
                "Mento swap executed: %s (gas used: %d, status: %d)",
                tx_hex, receipt["gasUsed"], receipt["status"]
            )
            return tx_hex
            
        except Exception as e:
            logger.error("execute_swap failed: %s", e)
            return f"0xERROR_{str(e)[:50]}"

    # ------------------------------------------------------------------

    async def get_balances(self, address: str) -> Dict[str, str]:
        """Get ERC-20 balances for all Mento stablecoins."""
        from integrations.chain_config import ChainConfig
        
        if not self.w3 or not self.w3.is_connected():
            return {}

        ERC20_BALANCE_ABI = [
            {
                "inputs": [{"name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function",
            }
        ]

        try:
            from web3 import Web3
            config = ChainConfig.celo_sepolia()
            checksum_addr = Web3.to_checksum_address(address)
            balances: Dict[str, str] = {}

            for symbol, token_addr in config.token_addresses.items():
                try:
                    contract = self.w3.eth.contract(
                        address=Web3.to_checksum_address(token_addr),
                        abi=ERC20_BALANCE_ABI,
                    )
                    raw = contract.functions.balanceOf(checksum_addr).call()
                    decimals = 6 if "USDC" in symbol or "USDT" in symbol or "axlUSDC" in symbol else 18
                    balances[symbol] = str(raw / (10**decimals))
                except Exception:
                    balances[symbol] = "0.0"

            return balances
        except Exception as e:
            logger.warning("Failed to fetch on-chain balances: %s", e)
            return {}
