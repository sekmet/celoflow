import logging
import os
from dotenv import load_dotenv

from contextwise import Agent
from contextwise.models import AzureForgeModel

# Plugins
from plugins.tee_plugin import TEEPlugin
from plugins.remittance_plugin import RemittancePlugin
from plugins.registry_plugin import RegistryPlugin
from plugins.compliance_plugin import CompliancePlugin
from plugins.mento_plugin import MentoPlugin
from plugins.notification_plugin import NotificationPlugin
from plugins.scheduler_plugin import SchedulerPlugin

# Tools
from tools import remittance_tools

logger = logging.getLogger(__name__)

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

If the user speaks Spanish, reply in Spanish. If Portuguese, reply in Portuguese.
Maintain the same helpful, professional persona in all languages.

## Capabilities
- Find optimal currency routes via the **Mento v2 Protocol** with real \
on-chain exchange rates from the Broker contract.
- Supported Mento v2 pools: USDm/PHPm, USDm/XOFm, USDm/CELO, USDm/axlUSDC.
- Calculate transparent fee breakdowns (network + agent + liquidity).
- Execute secure transfers using TEE-backed signing inside a Trusted \
Execution Environment (Intel TDX via Dstack).
- Verify agent identity and reputation on-chain (ERC-8004 standard).
- Perform basic KYC/AML compliance checks.

## Interaction Style
- Be concise and helpful.
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

def create_agent() -> Agent:
    """Build and return the fully-configured remittance agent."""
    load_dotenv()

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
    )

    # ── Collect plugins ──────────────────────────────────────────

    plugins = [
        tee_plugin,
        remittance_plugin,
        mento_plugin,
        compliance_plugin,
        notification_plugin,
        SchedulerPlugin(),
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
            remittance_tools.get_wallet_balance,
        ],
        plugins=plugins,
    )

    logger.info("CeloFlow agent factory created agent (model=%s, tee=%s)", getattr(model, "id", str(model)), tee_plugin.address)
    return agent
