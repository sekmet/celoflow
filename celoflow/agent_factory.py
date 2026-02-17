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
from plugins.kyc_plugin import KYCPlugin
from plugins.compliance_agent_plugin import ComplianceAgentPlugin
# WalletContextPlugin and ContactsContextPlugin removed — they baked stale
# context at startup.  Live context is now injected per-request via
# WalletContextMiddleware in server.py.
from services.wallet_context_service import wallet_context_service

# Services
from services.fee_comparison_service import FeeComparisonService
from services.language_detection import LanguageDetectionService
from services.translation_service import TranslationService
from services.reputation_analytics import ReputationAnalyticsService

# Integrations
from integrations.wise_client import WiseClient

# Tools
from tools import remittance_tools

logger = logging.getLogger(__name__)

# Import the system prompt from main.py
from main import SYSTEM_PROMPT

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
    )

    # Wire mento plugin into wallet context service for balance fetching
    wallet_context_service.set_mento_plugin(mento_plugin)

    # ── Collect plugins ──────────────────────────────────────────

    plugins = [
        tee_plugin,
        remittance_plugin,
        mento_plugin,
        compliance_plugin,
        notification_plugin,
        kyc_plugin,
        compliance_agent_plugin,
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
            remittance_tools.get_current_wallet_context,
            remittance_tools.compare_fees_with_providers,
            remittance_tools.monitor_fee_changes,
        ],
        plugins=plugins,
    )

    logger.info("CeloFlow agent factory created agent (model=%s, tee=%s)", getattr(model, "id", str(model)), tee_plugin.address)
    return agent
