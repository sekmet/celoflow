"""CeloFlow — ERC-8004 Remittance Intent Agent.

Entry point for the Contextwise-based remittance agent on Celo.
"""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv

from contextwise.models import AzureForgeModel
from contextwise import Agent

# Plugins
from plugins.tee_plugin import TEEPlugin
from plugins.remittance_plugin import RemittancePlugin
from plugins.registry_plugin import RegistryPlugin
from plugins.compliance_plugin import CompliancePlugin
from plugins.mento_plugin import MentoPlugin
from plugins.notification_plugin import NotificationPlugin
from plugins.scheduler_plugin import SchedulerPlugin
from plugins.kyc_plugin import KYCPlugin
from plugins.compliance_agent_plugin import ComplianceAgentPlugin

# Services
from services.fee_comparison_service import FeeComparisonService
from services.language_detection import LanguageDetectionService
from services.translation_service import TranslationService
from services.reputation_analytics import ReputationAnalyticsService
from services.wallet_context_service import wallet_context_service
from services.contacts_context_service import contacts_context_service
from services.intent_parsing_service import IntentParsingService
from services.route_optimization_service import RouteOptimizationService

# Integrations
from integrations.wise_client import WiseClient
from integrations.x402_client import X402Client

# Tools
from tools import remittance_tools
from agents import set_tracing_disabled

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("celoflow")

# ═══════════════════════════════════════════════════════════════════
# System prompt
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """\
You are the **CeloFlow Remittance Agent** — an AI-powered cross-border \
remittance assistant built on the Celo blockchain (Celo Sepolia Testnet).

# Multi-Language Support
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

## Wallet Balance Awareness - CRITICAL
**ALWAYS check the user's wallet balances before giving transfer advice!**

When a user mentions wanting to send a specific token (e.g., "send 1 BRLm") or asks for balances, you MUST:

1. **First**: Use `get_current_wallet_context()` to check if a wallet is connected and get current balances
2. **Check**: If no wallet is connected, ask the user to connect their wallet
3. **Analyze**: Review their actual balances and suggest realistic transfer options
4. **Personalize**: Base recommendations on what they actually own, not generic advice

Example workflow:
- User: "show my wallet balances" or "send 1 BRLm to Brazil"
- You: Use `get_current_wallet_context()` to check wallet state
- If connected: "Great! I see you have X TOKEN. Here are your options..."
- If not connected: "Please connect your wallet first so I can check your balances"

**IMPORTANT**: Always use `get_current_wallet_context()` first - it tells you if a wallet is connected and shows all balances in one call!

## Capabilities
- Find optimal currency routes via the **Mento v2 Protocol** with real \
  on-chain exchange rates from the Broker contract.
- Supported Mento v2 pools: USDm/PHPm, USDm/XOFm, USDm/CELO, USDm/axlUSDC.
- Calculate transparent fee breakdowns (network + agent + liquidity).
- **Send tokens directly** (BRLm, cUSD, USDm, EURm, CELO, etc.) to any \
  recipient address using `send_token` — no swap needed.
- Execute cross-currency swaps using TEE-backed signing inside a Trusted \
  Execution Environment (Intel TDX via Dstack) via `execute_transfer`.
- Verify agent identity and reputation on-chain (ERC-8004 standard).
- Perform KYC/AML compliance checks with tiered verification levels.
- Compare fees in real-time against Western Union, Wise, Remitly, MoneyGram.
- Screen recipients against sanction lists via x402 compliance agents.
- **Check user wallet balances** to provide personalized transfer recommendations.

## CRITICAL: Choosing the Right Transfer Tool
- **`send_token`**: Use when the user wants to send a token they already hold \
  (e.g. "Send 1 BRLm to Charles", "Transfer 5 cUSD to 0x..."). This does a \
  direct ERC-20 transfer — NO currency conversion.
- **`execute_transfer`**: Use ONLY when the user wants to SWAP between different \
  currencies (e.g. "Convert 100 cUSD to PHPm and send to Maria"). This uses \
  the Mento v2 Broker for on-chain swaps.
- When the user says "send X TokenA to Someone", ALWAYS use `send_token` \
  (direct transfer). Only use `execute_transfer` if from_currency != to_currency.

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
- Be concise and helpful. DO NOT be overly verbose.
- **ALWAYS check wallet balances first** before suggesting transfer routes.
- When asked about rates, use `find_optimal_route` to get live Mento rates.
- Map user references to "cUSD" as "USDm" internally (they are equivalent \
  on Celo Sepolia).

## Transfer Execution Flow
When a user requests a transfer (e.g. "Send 1 BRLm to Charles"):
1. Resolve the recipient from the user's contacts to get their wallet address.
2. Call `send_token` (same-token transfer) or `execute_transfer` (cross-currency swap).
3. After the tool returns, show the tx hash and explorer link.

Guidelines:
- "Send X token to Name" → use `send_token` with the contact's address.
- "Convert X from A to B and send to Name" → use `execute_transfer`.
- Execute transfers directly — the user expects immediate action without \
  extra confirmation steps.
- If the user says "Confirm" or "Yes" to a pending transfer, execute it now.

If the user asks about your identity or trust, use the on-chain registry \
tools to prove your registration and reputation.

## Supported Tokens (Celo Sepolia)
Direct transfers via `send_token`: USDm, EURm, BRLm, KESm, XOFm, PHPm, COPm, \
GBPm, CADm, AUDm, ZARm, GHSm, NGNm, JPYm, CHFm, CELO, USDT, axlUSDC.

## Supported Swap Corridors (Mento v2)
cUSD (USDm) → PHPm (Philippines Peso), cUSD (USDm) → XOFm (West Africa CFA), \
cUSD (USDm) → CELO (native token), cUSD (USDm) → axlUSDC (bridged USDC).

## Agent Identity
- Registered as Agent ID 0 on Celo Sepolia IdentityRegistry.
- Agent wallet: derived from TEE enclave key.
- Chain ID: 11142220 (Celo Sepolia).
"""


def create_agent() -> Agent:
    """Build and return the fully-configured remittance agent."""

    # ── Plugin setup ──────────────────────────────────────────────

    tee_plugin = TEEPlugin(
        domain=os.getenv("TEE_DOMAIN", "celoflow.remittance"),
        salt=os.getenv("TEE_SALT", "remittance-agent-v1"),
        use_tee=os.getenv("USE_TEE", "false").lower() == "true",
        tee_endpoint=os.getenv("TEE_ENDPOINT"),
        private_key=os.getenv("AGENT_PRIVATE_KEY"),
    )

    remittance_plugin = RemittancePlugin()

    mento_plugin = MentoPlugin(
        rpc_url=os.getenv("CELO_RPC_URL", "http://127.0.0.1:8545"),
    )

    compliance_plugin = CompliancePlugin(
        max_single_transfer=float(os.getenv("MAX_SINGLE_TRANSFER", "10000")),
    )

    notification_plugin = NotificationPlugin(
        twilio_sid=os.getenv("TWILIO_SID"),
        twilio_token=os.getenv("TWILIO_TOKEN"),
        twilio_from=os.getenv("TWILIO_FROM"),
        enable_whatsapp_meta=os.getenv("ENABLE_WHATSAPP_META", "false").lower() == "true",
        enable_whatsmeow=os.getenv("ENABLE_WHATSMEOW", "false").lower() == "true",
        enable_telegram=os.getenv("ENABLE_TELEGRAM", "false").lower() == "true",
        default_telegram_chat_id=os.getenv("DEFAULT_TELEGRAM_CHAT_ID"),
        default_whatsapp_number=os.getenv("DEFAULT_WHATSAPP_NUMBER"),
    )

    # KYC Plugin
    kyc_plugin = KYCPlugin(
        self_protocol_api_key=os.getenv("SELF_PROTOCOL_API_KEY"),
        self_protocol_base_url=os.getenv("SELF_PROTOCOL_URL", "https://api.self.id"),
        default_kyc_level=os.getenv("DEFAULT_KYC_LEVEL", "none"),
    )

    # Compliance Agent Plugin (x402 inter-agent screening)
    compliance_agent_plugin = ComplianceAgentPlugin(
        compliance_agent_url=os.getenv("COMPLIANCE_AGENT_URL"),
        compliance_fee_usdt=float(os.getenv("COMPLIANCE_FEE_USDT", "0.10")),
    )

    # Wise API Client
    wise_client = WiseClient(
        api_key=os.getenv("WISE_API_KEY"),
        base_url=os.getenv("WISE_API_URL"),
        sandbox_url=os.getenv("WISE_SANDBOX_API_URL"),
        use_sandbox=os.getenv("WISE_USE_SANDBOX", "true").lower() == "true",
    )

    # Services (non-plugin, used by tools)
    fee_comparison_service = FeeComparisonService(wise_client=wise_client)
    language_detection_service = LanguageDetectionService(
        default_language=os.getenv("DEFAULT_LANGUAGE", "en"),
    )
    translation_service = TranslationService(
        google_api_key=os.getenv("GOOGLE_TRANSLATE_API_KEY"),
        deepl_api_key=os.getenv("DEEPL_API_KEY"),
    )
    reputation_analytics = ReputationAnalyticsService()

    # Intent parsing service (multi-language NL → structured intent)
    intent_parsing_service = IntentParsingService(
        language_service=language_detection_service,
        translation_service=translation_service,
    )

    # Route optimization service (multi-corridor Mento routing)
    route_optimization_service = RouteOptimizationService(
        mento_plugin=mento_plugin,
    )

    # x402 payment client (agent-to-agent payments)
    x402_client = X402Client(
        agent_wallet_address=os.getenv("AGENT_WALLET_ADDRESS"),
        private_key=os.getenv("AGENT_PRIVATE_KEY"),
        chain_id=int(os.getenv("CELO_CHAIN_ID", "44787")),
        facilitator_url=os.getenv("X402_FACILITATOR_URL"),
    )

    # Set up wallet context service with mento plugin
    wallet_context_service.set_mento_plugin(mento_plugin)

    # Registry plugin (requires deployed contract addresses)
    registry_plugin = None
    if os.getenv("IDENTITY_REGISTRY"):
        registry_plugin = RegistryPlugin(
            rpc_url=os.getenv("CELO_RPC_URL", "http://127.0.0.1:8545"),
            identity_registry=os.getenv("IDENTITY_REGISTRY", ""),
            reputation_registry=os.getenv("REPUTATION_REGISTRY", ""),
            tee_registry=os.getenv("TEE_REGISTRY", ""),
            private_key=os.getenv("AGENT_PRIVATE_KEY"),
            agent_id=int(os.getenv("AGENT_ID", "0")),
        )

    # ── Wire tools to plugins ────────────────────────────────────

    remittance_tools.set_plugins(
        mento=mento_plugin,
        tee=tee_plugin,
        remittance=remittance_plugin,
        compliance=compliance_plugin,
        notification=notification_plugin,
        registry=registry_plugin,
        kyc=kyc_plugin,
        compliance_agent=compliance_agent_plugin,
        fee_comparison=fee_comparison_service,
        wise=wise_client,
        intent_parsing=intent_parsing_service,
        route_optimization=route_optimization_service,
        x402=x402_client,
    )

    # ── Collect plugins ──────────────────────────────────────────

    scheduler_plugin = SchedulerPlugin(
        notification_plugin=notification_plugin,
    )

    plugins = [
        tee_plugin,
        remittance_plugin,
        mento_plugin,
        compliance_plugin,
        notification_plugin,
        scheduler_plugin,
        kyc_plugin,
        compliance_agent_plugin,
    ]
    if registry_plugin:
        plugins.append(registry_plugin)

    # ── Build agent ──────────────────────────────────────────────

    #model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
    model = AzureForgeModel("gpt-5.2-chat")

    agent = Agent(
        name="CeloFlow Remittance Agent",
        model=model,
        instructions=SYSTEM_PROMPT,
        tools=[
            remittance_tools.find_optimal_route,
            remittance_tools.calculate_fees,
            remittance_tools.execute_transfer,
            remittance_tools.send_token,
            remittance_tools.get_wallet_balance,
            remittance_tools.get_current_wallet_context,
            remittance_tools.compare_fees_with_providers,
            remittance_tools.monitor_fee_changes,
            remittance_tools.parse_transfer_intent,
            remittance_tools.find_optimal_routes,
        ],
        plugins=plugins,
    )

    logger.info("CeloFlow agent created (model=%s, tee=%s)", getattr(model, "id", str(model)), tee_plugin.address)
    return agent


# ═══════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════

def main() -> None:
    """Start the CeloFlow agent server."""
    set_tracing_disabled(True)
    agent = create_agent()
    port = int(os.getenv("PORT", "8000"))
    logger.info("Starting CeloFlow on port %d", port)
    agent.serve(port=port)


if __name__ == "__main__":
    print("Starting agent server with scheduler on http://localhost:8000")
    print("\nTest with curl:")
    print('  curl -X POST http://localhost:8000/chat \\')
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"message": "Schedule a daily reminder at 9 AM to check emails", "user_id": "test_user"}\'')
    print()
    print('curl -N -sS -X POST http://localhost:8000/chat/stream \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -H "Accept: text/event-stream" \\')
    print('  -d \'{"messages": [{"role": "user", "content": "Tell me a long story about AI."}]} \\')
    print()    
    main()
