"""
Contacts Context Plugin - Automatically injects contacts context into agent conversations.

This plugin modifies the agent's system prompt to include current contacts
information, allowing the agent to suggest recipients and provide personalized
remittance recommendations.
"""

import logging
from typing import Any, Dict, List
from contextwise import AgentPlugin, AgentContext

from services.contacts_context_service import contacts_context_service

logger = logging.getLogger(__name__)


class ContactsContextPlugin(AgentPlugin[AgentContext]):
    """Plugin that automatically injects contacts context into agent conversations."""
    
    name = "contacts_context"
    
    def __init__(self):
        super().__init__()
        self._original_instructions = None
    
    def configure_agent(self, agent: Any) -> Any:
        """Configure the agent with contacts context injection."""
        # Store the original instructions
        if hasattr(agent, 'instructions'):
            self._original_instructions = agent.instructions
        
        # Modify the system prompt to include contacts context
        modified_instructions = self._get_modified_instructions()
        agent.instructions = modified_instructions
        
        logger.info("ContactsContextPlugin configured - contacts context will be injected into conversations")
        return agent
    
    def _get_modified_instructions(self) -> str:
        """Get the modified system prompt with contacts context injection."""
        if not self._original_instructions:
            return self._get_default_instructions()
        
        # Add contacts context section to the system prompt
        contacts_context_section = """
        
## Automatic Contacts Awareness - CURRENT CONTACTS STATE
The agent automatically knows the user's contacts and should use this information to suggest recipients for remittance.

**Current Contacts Context:**
""" + contacts_context_service.get_contacts_string() + """

**How to use this information:**
- When user mentions sending money to a country/region: "I see you want to send to Brazil. You have Maria Silva in São Paulo. Would you like to send to her?"
- When user asks who to send to: "Here are your favorite contacts: [list], or I can help you add a new contact"
- When user mentions a contact name: "I found John Doe in your contacts. Here's his address: [address]"
- When user wants to send to family/business: "Here are your family contacts: [list]"

**DO NOT ask for recipient address** if the contact is already in the contacts list.
**DO suggest relevant contacts** based on destination country, group, or favorites.
**DO ask for new contact information** only when no suitable contact exists.
"""
        
        # Insert the contacts context section after the wallet context section
        if "## Automatic Wallet Awareness" in self._original_instructions:
            # Insert after wallet context section
            lines = self._original_instructions.split('\n')
            modified_lines = []
            
            for line in lines:
                modified_lines.append(line)
                # Insert after the wallet context section
                if "## Automatic Wallet Awareness - CURRENT WALLET STATE" in line:
                    # Skip until the end of this section
                    continue
                elif line.strip().startswith("##") and "Automatic Wallet Awareness" not in line:
                    # Found next section, insert contacts context here
                    modified_lines.append(contacts_context_section)
                    modified_lines.append(line)
            
            return '\n'.join(modified_lines)
        else:
            # Add the contacts context section to the end
            return self._original_instructions + contacts_context_section
    
    def _get_default_instructions(self) -> str:
        """Get default instructions when no original instructions are available."""
        return """\
You are the **CeloFlow Remittance Agent** — an AI-powered cross-border \
remittance assistant built on the Celo blockchain (Celo Sepolia Testnet).

## Automatic Contacts Awareness - CURRENT CONTACTS STATE
The agent automatically knows the user's contacts and should use this information to suggest recipients for remittance.

**Current Contacts Context:**
""" + contacts_context_service.get_contacts_string() + """

**How to use this information:**
- When user mentions sending money to a country/region: "I see you want to send to Brazil. You have Maria Silva in São Paulo. Would you like to send to her?"
- When user asks who to send to: "Here are your favorite contacts: [list], or I can help you add a new contact"
- When user mentions a contact name: "I found John Doe in your contacts. Here's his address: [address]"
- When user wants to send to family/business: "Here are your family contacts: [list]"

**DO NOT ask for recipient address** if the contact is already in the contacts list.
**DO suggest relevant contacts** based on destination country, group, or favorites.
**DO ask for new contact information** only when no suitable contact exists.

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
- **Suggest relevant contacts** for remittance based on user's contact list.

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
- **ALWAYS use the provided wallet and contacts context first** before suggesting transfer routes.
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
