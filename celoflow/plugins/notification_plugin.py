"""Notification Plugin — Multi-channel notifications (SMS, WhatsApp, Telegram)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from contextwise import AgentPlugin, AgentContext

# Import contextwise lib integrations (if available)
try:
    from contextwise.lib.whatsapp.utils import send_text_message as send_whatsapp_meta
    HAS_WHATSAPP_META = True
except ImportError:
    HAS_WHATSAPP_META = False

try:
    from contextwise.lib.whatsmeow.utils import send_text_message as send_whatsmeow
    HAS_WHATSMEOW = True
except ImportError:
    HAS_WHATSMEOW = False

try:
    from contextwise.lib.telegram.utils import send_telegram_message
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

logger = logging.getLogger(__name__)


class NotificationPlugin(AgentPlugin[AgentContext]):
    """Send notifications via SMS (Twilio), WhatsApp (Meta/WhatsMeow), and Telegram."""

    name = "notification"

    def __init__(
        self,
        twilio_sid: Optional[str] = None,
        twilio_token: Optional[str] = None,
        twilio_from: Optional[str] = None,
        # Channels configuration
        enable_whatsapp_meta: bool = False,
        enable_whatsmeow: bool = False,
        enable_telegram: bool = False,
        # Default recipients (optional)
        default_telegram_chat_id: Optional[str] = None,
        default_whatsapp_number: Optional[str] = None,
    ) -> None:
        super().__init__()
        
        # Twilio Setup
        self.twilio_client: Any = None
        self.twilio_from = twilio_from
        if twilio_sid and twilio_token:
            try:
                from twilio.rest import Client  # type: ignore[import-untyped]
                self.twilio_client = Client(twilio_sid, twilio_token)
                logger.info("NotificationPlugin: Twilio client initialised")
            except ImportError:
                logger.warning("NotificationPlugin: twilio package not installed")

        # Channel Flags
        self.enable_whatsapp_meta = enable_whatsapp_meta and HAS_WHATSAPP_META
        self.enable_whatsmeow = enable_whatsmeow and HAS_WHATSMEOW
        self.enable_telegram = enable_telegram and HAS_TELEGRAM
        
        # Defaults
        self.default_telegram_chat_id = default_telegram_chat_id
        self.default_whatsapp_number = default_whatsapp_number

        if self.enable_whatsapp_meta:
            logger.info("NotificationPlugin: WhatsApp Meta API enabled")
        if self.enable_whatsmeow:
            logger.info("NotificationPlugin: WhatsMeow enabled")
        if self.enable_telegram:
            logger.info("NotificationPlugin: Telegram enabled")

    def configure_agent(self, agent: Any) -> Any:
        return agent

    # ── Channel Senders ───────────────────────────────────────────────

    async def send_sms(self, to: str, message: str) -> Dict[str, Any]:
        """Send an SMS via Twilio."""
        if not self.twilio_client or not self.twilio_from:
            logger.info("SMS (dry-run) to %s: %s", to, message)
            return {"sent": False, "mode": "dry-run", "to": to}

        try:
            msg = self.twilio_client.messages.create(
                body=message,
                from_=self.twilio_from,
                to=to,
            )
            return {"sent": True, "sid": msg.sid, "provider": "twilio"}
        except Exception as e:
            logger.error(f"Twilio send failed: {e}")
            return {"sent": False, "error": str(e)}

    async def send_whatsapp(self, to: str, message: str) -> Dict[str, Any]:
        """Send WhatsApp via configured provider (Meta > WhatsMeow)."""
        # 1. Try Meta API
        if self.enable_whatsapp_meta:
            try:
                # Meta API requires environment variables: WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID
                # We assume these are set in the environment if this channel is enabled.
                result = send_whatsapp_meta(recipient=to, text=message)
                if result is None: # None means success in contextwise lib
                    return {"sent": True, "provider": "meta"}
                return {"sent": False, "error": str(result), "provider": "meta"}
            except Exception as e:
                logger.error(f"WhatsApp Meta send failed: {e}")
        
        # 2. Try WhatsMeow
        if self.enable_whatsmeow:
            try:
                # WhatsMeow requires: WHATSMEOW_BASE_URL, WHATSMEOW_API_KEY
                result = send_whatsmeow(recipient=to, text=message)
                if result is None:
                    return {"sent": True, "provider": "whatsmeow"}
                return {"sent": False, "error": str(result), "provider": "whatsmeow"}
            except Exception as e:
                logger.error(f"WhatsMeow send failed: {e}")
                return {"sent": False, "error": str(e), "provider": "whatsmeow"}

        # Fallback logging
        logger.info("WhatsApp (dry-run) to %s: %s", to, message)
        return {"sent": False, "mode": "dry-run", "to": to}

    async def send_telegram(self, chat_id: str, message: str) -> Dict[str, Any]:
        """Send Telegram message."""
        if self.enable_telegram:
            try:
                # Telegram requires: TELEGRAM_BOT_TOKEN
                result = send_telegram_message(chat_id=chat_id, text=message)
                return {"sent": True, "result": result, "provider": "telegram"}
            except Exception as e:
                logger.error(f"Telegram send failed: {e}")
                return {"sent": False, "error": str(e), "provider": "telegram"}
        
        logger.info("Telegram (dry-run) to %s: %s", chat_id, message)
        return {"sent": False, "mode": "dry-run", "chat_id": chat_id}

    # ── Notification Logic ─────────────────────────────────────────────

    async def notify_transfer_complete(
        self,
        to: str, # Usually phone number or wallet
        amount: str,
        currency: str,
        tx_hash: str,
    ) -> Dict[str, Any]:
        """Send transfer completion notification to all active channels."""
        message = (
            f"✅ *Transfer Complete!*\n"
            f"💸 Amount: {amount} {currency}\n"
            f"🔗 TX: {tx_hash[:10]}..."
        )
        
        results = {}
        
        # 1. SMS / WhatsApp (uses 'to' which should be phone number)
        # We assume 'to' is a phone number if it starts with +
        if to.startswith("+"):
            # Try WhatsApp first (richer), then SMS
            wa_res = await self.send_whatsapp(to, message)
            results["whatsapp"] = wa_res
            
            # If WhatsApp failed or not enabled, try SMS
            if not wa_res.get("sent"):
               sms_res = await self.send_sms(to, message)
               results["sms"] = sms_res
        
        # 2. Telegram (if default chat_id is configured or if 'to' looks like a chat_id)
        # For simplicity, we use the default_telegram_chat_id if set
        chat_id = self.default_telegram_chat_id
        if chat_id:
             tg_res = await self.send_telegram(chat_id, message)
             results["telegram"] = tg_res
             
        return results
