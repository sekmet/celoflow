"""
Wallet Context Service - Provides wallet information to the agent.

This service automatically detects and provides wallet context to the agent
so it can give personalized recommendations without asking for wallet addresses.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WalletContext:
    """Wallet context data structure."""
    wallet_address: Optional[str] = None
    connected: bool = False
    chain_id: Optional[int] = None
    balances: Dict[str, str] = None
    
    def __post_init__(self):
        if self.balances is None:
            self.balances = {}


class WalletContextService:
    """Service for managing wallet context and providing it to the agent."""
    
    def __init__(self):
        self._current_context = WalletContext()
        self._mento_plugin = None
    
    def set_mento_plugin(self, mento_plugin) -> None:
        """Set the Mento plugin for balance fetching."""
        self._mento_plugin = mento_plugin
        logger.info("Mento plugin set for wallet context service")
        
        # Reset the logged flag when plugin is set
        if hasattr(self, '_logged_mento_unavailable'):
            delattr(self, '_logged_mento_unavailable')
        
        # If we have a wallet address, fetch balances now
        if self._current_context.wallet_address and self._current_context.connected:
            import asyncio
            # Create a task to fetch balances asynchronously
            asyncio.create_task(self._fetch_balances(self._current_context.wallet_address))
    
    async def retry_balance_fetch(self) -> None:
        """Retry fetching balances if Mento plugin is now available."""
        if self._current_context.wallet_address and self._current_context.connected and self._mento_plugin:
            await self._fetch_balances(self._current_context.wallet_address)
    
    async def update_wallet_context(
        self, 
        wallet_address: Optional[str] = None,
        connected: bool = False,
        chain_id: Optional[int] = None
    ) -> WalletContext:
        """Update wallet context and fetch balances if connected."""
        self._current_context.wallet_address = wallet_address
        self._current_context.connected = connected
        self._current_context.chain_id = chain_id
        
        # Clear balances if disconnected
        if not connected or not wallet_address:
            self._current_context.balances = {}
            logger.info("Wallet disconnected or no address provided, cleared balances")
        else:
            # Fetch fresh balances
            await self._fetch_balances(wallet_address)
        
        return self._current_context
    
    async def _fetch_balances(self, wallet_address: str) -> None:
        """Fetch token balances for the given wallet address."""
        if not self._mento_plugin:
            # Only log once per session, not on every request
            if not hasattr(self, '_logged_mento_unavailable'):
                logger.info("Mento plugin not yet available - balances will be fetched when agent is ready")
                self._logged_mento_unavailable = True
            return
        
        try:
            balances = await self._mento_plugin.get_balances(wallet_address)
            self._current_context.balances = balances
            logger.info(f"Fetched {len(balances)} token balances for {wallet_address[:8]}…{wallet_address[-4:]}")
        except Exception as e:
            logger.error(f"Failed to fetch balances: {e}")
            self._current_context.balances = {}
    
    def get_wallet_context(self) -> WalletContext:
        """Get the current wallet context."""
        return self._current_context
    
    def get_wallet_context_string(self) -> str:
        """Get wallet context as a formatted string for the agent."""
        context = self._current_context
        
        if not context.connected:
            return "No wallet connected. User needs to connect their wallet first."
        
        context_lines = [
            f"Wallet Status: Connected",
            f"Wallet Address: {context.wallet_address}",
            f"Chain ID: {context.chain_id}",
            f"Token Balances:"
        ]
        
        # Add non-zero balances
        non_zero_balances = {k: v for k, v in context.balances.items() if float(v) > 0}
        
        if non_zero_balances:
            for token, balance in non_zero_balances.items():
                context_lines.append(f"  - {token}: {balance}")
        else:
            context_lines.append("  - No token balances found")
        
        return "\n".join(context_lines)
    
    def has_token(self, token_symbol: str) -> bool:
        """Check if wallet has a specific token."""
        if not self._current_context.connected:
            return False
        
        balance = self._current_context.balances.get(token_symbol, "0")
        return float(balance) > 0
    
    def get_token_balance(self, token_symbol: str) -> float:
        """Get the balance of a specific token."""
        if not self._current_context.connected:
            return 0.0
        
        return float(self._current_context.balances.get(token_symbol, "0"))


# Global instance for the service
wallet_context_service = WalletContextService()
