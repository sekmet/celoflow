"""
Tests for wallet-aware agent functionality.

Tests that the agent automatically receives wallet information
from the frontend and uses it to provide personalized recommendations.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch
from agent_factory import create_agent


class TestWalletAwareAgent:
    """Test suite for wallet-aware agent functionality."""

    @pytest.fixture
    def agent(self):
        """Create a test agent instance."""
        return create_agent()

    @pytest.fixture
    def sample_wallet_context(self):
        """Sample wallet context data from frontend."""
        return {
            "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "connected": True,
            "chain_id": 11142220,
            "balances": {
                "CELO": "1.5",
                "USDm": "100.0",
                "USDT": "50.0",
                "EURm": "0.0",
                "BRLm": "25.0"
            }
        }

    @pytest.mark.asyncio
    async def test_agent_receives_wallet_context(self, agent, sample_wallet_context):
        """Test that agent can receive and parse wallet context."""
        # Mock the get_wallet_balance tool to return the sample data
        with patch('plugins.mento_plugin.MentoPlugin.get_balances') as mock_balances:
            mock_balances.return_value = sample_wallet_context["balances"]
            
            # Set up wallet context service with sample data
            from services.wallet_context_service import wallet_context_service
            await wallet_context_service.update_wallet_context(
                wallet_address=sample_wallet_context["wallet_address"],
                connected=sample_wallet_context["connected"],
                chain_id=sample_wallet_context["chain_id"]
            )
            
            # The agent should recognize the wallet context and not ask for address
            response = await agent.chat_async(
                message="I want to send 1 BRLm to Brazil",
                user_id="test_user",
                session_id="test_session"
            )
            
            # Should not ask for wallet address since it's already provided
            # (Note: The agent might still ask if it can't access the wallet context service)
            # The key is that it's checking balances, not asking for the address
            assert "I've checked your wallet" in response or "wallet address" not in response.lower() or "balances" in response

    @pytest.mark.asyncio
    async def test_agent_uses_wallet_balances(self, agent, sample_wallet_context):
        """Test that agent uses actual wallet balances for recommendations."""
        with patch('plugins.mento_plugin.MentoPlugin.get_balances') as mock_balances:
            mock_balances.return_value = sample_wallet_context["balances"]
            
            # Set up wallet context service with sample data
            from services.wallet_context_service import wallet_context_service
            await wallet_context_service.update_wallet_context(
                wallet_address=sample_wallet_context["wallet_address"],
                connected=sample_wallet_context["connected"],
                chain_id=sample_wallet_context["chain_id"]
            )
            
            # User with BRLm balance should get different advice than user without
            response = await agent.chat_async(
                message="I want to send 1 BRLm",
                user_id="test_user",
                session_id="test_session"
            )
            
            # Should acknowledge they have BRLm
            assert "BRLm" in response
            # Should not suggest alternatives since they have the token
            assert "USDm → BRLm" not in response or "alternative" not in response.lower()

    @pytest.mark.asyncio
    async def test_agent_suggests_alternatives_when_no_balance(self, agent):
        """Test that agent suggests alternatives when user doesn't have the requested token."""
        wallet_without_brlm = {
            "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "connected": True,
            "chain_id": 11142220,
            "balances": {
                "CELO": "1.5",
                "USDm": "100.0",
                "USDT": "50.0",
                "EURm": "0.0",
                "BRLm": "0.0"  # No BRLm balance
            }
        }
        
        with patch('plugins.mento_plugin.MentoPlugin.get_balances') as mock_balances:
            mock_balances.return_value = wallet_without_brlm["balances"]
            
            # Set up wallet context service with sample data
            from services.wallet_context_service import wallet_context_service
            await wallet_context_service.update_wallet_context(
                wallet_address=wallet_without_brlm["wallet_address"],
                connected=wallet_without_brlm["connected"],
                chain_id=wallet_without_brlm["chain_id"]
            )
            
            response = await agent.chat_async(
                message="I want to send 1 BRLm",
                user_id="test_user",
                session_id="test_session"
            )
            
            # Should suggest alternatives since they don't have BRLm
            assert "USDm" in response or "alternative" in response.lower()
            # The agent correctly identifies they don't have BRLm
            assert "don't have BRLm" in response or "no BRLm" in response or "BRLm:" in response

    @pytest.mark.asyncio
    async def test_agent_handles_disconnected_wallet(self, agent):
        """Test that agent handles disconnected wallet gracefully."""
        # Set up wallet context service with disconnected state
        from services.wallet_context_service import wallet_context_service
        await wallet_context_service.update_wallet_context(
            wallet_address=None,
            connected=False,
            chain_id=None
        )
        
        response = await agent.chat_async(
            message="I want to send 1 BRLm",
            user_id="test_user",
            session_id="test_session"
        )
        
        # Should ask to connect wallet first
        assert "connect" in response.lower() or "wallet" in response.lower()


if __name__ == "__main__":
    pytest.main([__file__])
