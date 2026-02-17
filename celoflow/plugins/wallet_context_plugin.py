"""
Wallet Context Plugin - Automatically injects wallet context into agent conversations.

This plugin modifies the agent's system prompt to include current wallet
information, allowing the agent to provide personalized recommendations without
asking for wallet addresses.
"""

import logging
from typing import Any, Dict, List
from contextwise import AgentPlugin, AgentContext

from services.wallet_context_service import wallet_context_service

logger = logging.getLogger(__name__)


class WalletContextPlugin(AgentPlugin[AgentContext]):
    """Plugin that automatically injects wallet context into agent conversations."""
    
    name = "wallet_context"
    
    def __init__(self):
        super().__init__()
        self._original_instructions = None
    
    def configure_agent(self, agent: Any) -> Any:
        """Configure the agent with wallet context injection."""
        # Store the original instructions
        if hasattr(agent, 'instructions'):
            self._original_instructions = agent.instructions
        
        # Modify the system prompt to include wallet context
        modified_instructions = self._get_modified_instructions()
        agent.instructions = modified_instructions
        
        logger.info("WalletContextPlugin configured - wallet context will be injected into conversations")
        return agent
    
    def _get_modified_instructions(self) -> str:
        """Get the modified system prompt with wallet context injection."""
        if not self._original_instructions:
            return self._get_default_instructions()
        
        # Get fresh wallet context each time (not cached at configuration)
        wallet_context_string = wallet_context_service.get_wallet_context_string()
        
        # Add wallet context section to the system prompt
        wallet_context_section = """
        
## Automatic Wallet Awareness - CURRENT WALLET STATE
The agent automatically knows the user's current wallet state and should use this information to provide personalized recommendations.

**Current Wallet Context:**
""" + wallet_context_string + """

**How to use this information:**
- Check if the user has the token they want to send
- If they have the token: "Great! I see you have X TOKEN. Here's how to send it..."
- If they don't have the token: "I see you don't have TOKEN, but you have X OTHER_TOKEN. Here's the best route..."
- If wallet is disconnected: "Please connect your wallet first so I can check your balances"

**DO NOT ask for wallet address** - it's already provided in the context above.
"""
        
        # Insert the wallet context section after the existing wallet balance awareness section
        if "## Wallet Balance Awareness - CRITICAL" in self._original_instructions:
            # Replace the existing section with the enhanced version
            lines = self._original_instructions.split('\n')
            modified_lines = []
            skip_next = False
            
            for line in lines:
                if "## Wallet Balance Awareness - CRITICAL" in line:
                    # Replace this entire section
                    modified_lines.append(wallet_context_section)
                    skip_next = False
                elif skip_next and line.strip().startswith("##"):
                    # Skip until the next section
                    skip_next = False
                    modified_lines.append(line)
                elif not skip_next and line.strip().startswith("##"):
                    # Found next section, stop skipping
                    skip_next = False
                    modified_lines.append(line)
                elif not skip_next:
                    modified_lines.append(line)
            
            return '\n'.join(modified_lines)
        else:
            # Add the wallet context section to the end
            return self._original_instructions + wallet_context_section
    
    def _get_default_instructions(self) -> str:
        """Get default instructions when no original instructions are available."""
        return """\
You are the **CeloFlow Remittance Agent** — an AI-powered cross-border \
remittance assistant built on the Celo blockchain (Celo Sepolia Testnet).

## Automatic Wallet Awareness - CURRENT WALLET STATE
The agent automatically knows the user's current wallet state and should use this information to provide personalized recommendations.

**Current Wallet Context:**
""" + wallet_context_service.get_wallet_context_string() + """

**How to use this information:**
- Check if the user has the token they want to send
- If they have the token: "Great! I see you have X TOKEN. Here's how to send it..."
- If they don't have the token: "I see you don't have TOKEN, but you have X OTHER_TOKEN. Here's the best route..."
- If wallet is disconnected: "Please connect your wallet first so I can check your balances"

**DO NOT ask for wallet address** - it's already provided in the context above.

## Multi-Language Support
You MUST detect the user's language and reply in the SAME language.
Supported languages:
- English (Default)
- Spanish (Español)
- Portuguese (Português)
- French (Français)
- Swahili (Kiswahili)
- Filipino/Tagalog

If the user speaks Spanish, reply in Spanish. If Portuguese, reply in Portuguese.
Maintain the same helpful, professional persona in all languages.
Detect dialect variations (e.g., Mexican Spanish vs Spain Spanish) and adapt.

## Capabilities
- Find optimal currency routes via the **Mento v2 Protocol** with real \
  on-chain exchange rates from the Broker contract.
- Supported Mento v2 pools: USDm/PHPm, USDm/XOFm, USDm/CELO, USDm/axlUSDC.
- Calculate transparent fee breakdowns (network + agent + liquidity).
- Execute secure transfers using TEE-backed signing inside a Trusted \
  Execution Environment (Intel TDX via Dstack).
- Verify agent identity and reputation on-chain (ERC-8004 standard).
- Perform KYC/AML compliance checks with tiered verification levels.
- Compare fees in real-time against Western Union, Wise, Remitly, MoneyGram.
- Screen recipients against sanction lists via x402 compliance agents.
- **Check user wallet balances** to provide personalized transfer recommendations.

## KYC Verification
- Users have KYC levels: none, basic, standard, enhanced.
- Each level has different transfer limits (none: $50, basic: $1K, standard: $10K, enhanced: $100K).
- Use `verify_user_kyc` to initiate verification and `get_kyc_status` to check.
- Use `check_kyc_transfer_eligibility` before high-value transfers.
- Always suggest KYC upgrade when a transfer exceeds the user's current limit.

## Compliance Screening
- Use `screen_recipient` to check addresses against sanction lists before transfers.
- High-risk jurisdictions are automatically flagged.
- All screening results are cached and audited.

## Fee Comparison (Real-time via Wise API)
- Always show fee comparisons with traditional providers when discussing transfers.
- Use `compare_fees_with_providers` to get real-time comparisons from the Wise API.
- Data includes confidence scores: "high" for real-time API data, "medium" for static fallback.
- Show the data source (realtime/static) and last updated timestamp for transparency.
- Highlight savings vs traditional services prominently with rankings.
- Use `monitor_fee_changes` to track fee trends for popular corridors.
- If real-time data is unavailable, the system automatically falls back to static data.

## Interaction Style
- Be concise and helpful.
- **ALWAYS use the provided wallet context first** before suggesting transfer routes.
- Always show the user the fee breakdown and savings vs. traditional \
  remittance services (Western Union, Wise) before executing a transfer.
- When asked about rates, use `find_optimal_route` to get live Mento rates.
- For transfers, run compliance checks first, then confirm with the user \
  before calling `execute_transfer`.
- If the user asks about your identity or trust, use the on-chain registry \
  tools to prove your registration and reputation.
- Map user references to "cUSD" as "USDm" internally (they are equivalent \
  on Celo Sepolia).

## Supported Corridors (Celo Sepolia)
cUSD (USDm) → PHPm (Philippines Peso), cUSD (USDm) → XOFm (West Africa CFA), \
cUSD (USDm) → CELO (native token), cUSD (USDm) → axlUSDC (bridged USDC).

## Agent Identity
- Registered as Agent ID 0 on Celo Sepolia IdentityRegistry.
- Agent wallet: derived from TEE enclave key.
- Chain ID: 11142220 (Celo Sepolia).
"""
