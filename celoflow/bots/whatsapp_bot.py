"""WhatsApp Bot — WhatsApp Business API integration for CeloFlow.

Handles incoming WhatsApp messages, routes them to the core agent,
and sends formatted responses back via the WhatsApp Business API.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# WhatsApp message types
MSG_TEXT = "text"
MSG_INTERACTIVE = "interactive"
MSG_TEMPLATE = "template"

# Quick reply templates for common actions
QUICK_REPLIES: Dict[str, List[Dict[str, str]]] = {
    "welcome": [
        {"id": "send_money", "title": "Send Money"},
        {"id": "check_balance", "title": "Check Balance"},
        {"id": "check_rates", "title": "Exchange Rates"},
    ],
    "confirm_transfer": [
        {"id": "confirm_yes", "title": "Confirm"},
        {"id": "cancel_no", "title": "Cancel"},
    ],
    "language_select": [
        {"id": "lang_en", "title": "English"},
        {"id": "lang_es", "title": "Español"},
        {"id": "lang_pt", "title": "Português"},
    ],
}


class WhatsAppBot:
    """WhatsApp Business API bot for CeloFlow remittance agent."""

    def __init__(
        self,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None,
        verify_token: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        agent_handler: Optional[Callable[..., Coroutine[Any, Any, str]]] = None,
    ) -> None:
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.verify_token = verify_token or "celoflow_whatsapp_verify"
        self.webhook_secret = webhook_secret
        self.agent_handler = agent_handler
        self._is_configured = bool(phone_number_id and access_token)

        # Session management: phone_number -> {messages, last_active, language}
        self._sessions: Dict[str, Dict[str, Any]] = {}

        # Analytics
        self._stats: Dict[str, int] = {
            "messages_received": 0,
            "messages_sent": 0,
            "errors": 0,
        }

        logger.info(
            "WhatsAppBot initialised (configured=%s, phone_id=%s)",
            self._is_configured,
            phone_number_id or "none",
        )

    # ------------------------------------------------------------------
    # Public: handle_webhook
    # ------------------------------------------------------------------

    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming WhatsApp webhook payload.

        Args:
            payload: Webhook payload from WhatsApp Business API

        Returns:
            Processing result
        """
        try:
            entry = payload.get("entry", [])
            if not entry:
                return {"status": "no_entry"}

            results = []
            for e in entry:
                changes = e.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    for message in messages:
                        result = await self._process_message(message, value)
                        results.append(result)

            self._stats["messages_received"] += len(results)
            return {"status": "processed", "count": len(results)}

        except Exception as e:
            self._stats["errors"] += 1
            logger.error("WhatsApp webhook error: %s", e)
            return {"status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # Public: verify_webhook
    # ------------------------------------------------------------------

    def verify_webhook(
        self, mode: str, token: str, challenge: str
    ) -> Optional[str]:
        """Verify WhatsApp webhook subscription.

        Args:
            mode: Hub mode (should be 'subscribe')
            token: Verification token
            challenge: Challenge string to return

        Returns:
            Challenge string if valid, None otherwise
        """
        if mode == "subscribe" and token == self.verify_token:
            logger.info("WhatsApp webhook verified")
            return challenge
        logger.warning("WhatsApp webhook verification failed")
        return None

    # ------------------------------------------------------------------
    # Public: send_text
    # ------------------------------------------------------------------

    async def send_text(self, to: str, text: str) -> Dict[str, Any]:
        """Send a text message via WhatsApp.

        Args:
            to: Recipient phone number (with country code)
            text: Message text

        Returns:
            Send result
        """
        if not self._is_configured:
            logger.info("WhatsApp (dry-run) to %s: %s", to, text[:100])
            return {"sent": False, "mode": "dry-run", "to": to}

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        return await self._send_api(payload)

    # ------------------------------------------------------------------
    # Public: send_interactive
    # ------------------------------------------------------------------

    async def send_interactive(
        self,
        to: str,
        body_text: str,
        buttons: List[Dict[str, str]],
        header: Optional[str] = None,
        footer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an interactive message with quick reply buttons.

        Args:
            to: Recipient phone number
            body_text: Message body
            buttons: List of {id, title} button definitions
            header: Optional header text
            footer: Optional footer text

        Returns:
            Send result
        """
        if not self._is_configured:
            logger.info("WhatsApp interactive (dry-run) to %s", to)
            return {"sent": False, "mode": "dry-run"}

        action_buttons = [
            {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
            for b in buttons[:3]
        ]

        interactive: Dict[str, Any] = {
            "type": "button",
            "body": {"text": body_text},
            "action": {"buttons": action_buttons},
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        return await self._send_api(payload)

    # ------------------------------------------------------------------
    # Public: send_transaction_update
    # ------------------------------------------------------------------

    async def send_transaction_update(
        self,
        to: str,
        tx_hash: str,
        amount: str,
        currency: str,
        status: str,
    ) -> Dict[str, Any]:
        """Send a transaction status update.

        Args:
            to: Recipient phone number
            tx_hash: Transaction hash
            amount: Transfer amount
            currency: Currency code
            status: Transaction status

        Returns:
            Send result
        """
        status_emoji = {
            "processing": "⏳",
            "completed": "✅",
            "failed": "❌",
            "scheduled": "📅",
        }
        emoji = status_emoji.get(status, "ℹ️")

        text = (
            f"{emoji} *Transfer Update*\n\n"
            f"💰 Amount: {amount} {currency}\n"
            f"📊 Status: {status.upper()}\n"
            f"🔗 TX: {tx_hash[:16]}...\n\n"
            f"_Powered by CeloFlow_"
        )

        return await self.send_text(to, text)

    # ------------------------------------------------------------------
    # Public: get_stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get bot usage statistics."""
        return {
            **self._stats,
            "active_sessions": len(self._sessions),
            "configured": self._is_configured,
        }

    # ------------------------------------------------------------------
    # Private: process message
    # ------------------------------------------------------------------

    async def _process_message(
        self, message: Dict[str, Any], value: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a single incoming message."""
        msg_type = message.get("type", "")
        sender = message.get("from", "")
        msg_id = message.get("id", "")

        # Get or create session
        session = self._get_or_create_session(sender)

        # Extract text content
        text = ""
        if msg_type == "text":
            text = message.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            interactive = message.get("interactive", {})
            button_reply = interactive.get("button_reply", {})
            text = button_reply.get("id", "") or button_reply.get("title", "")
        elif msg_type == "audio":
            text = "[Voice message received — text input required for now]"

        if not text:
            return {"status": "ignored", "reason": "no_text_content"}

        # Route to agent
        response_text = await self._route_to_agent(sender, text, session)

        # Send response
        await self.send_text(sender, response_text)

        # Update session
        session["messages"].append({"role": "user", "content": text, "timestamp": time.time()})
        session["messages"].append({"role": "assistant", "content": response_text, "timestamp": time.time()})
        session["last_active"] = time.time()

        return {"status": "processed", "sender": sender, "msg_id": msg_id}

    async def _route_to_agent(
        self, sender: str, text: str, session: Dict[str, Any]
    ) -> str:
        """Route message to the core agent for processing."""
        if self.agent_handler:
            try:
                return await self.agent_handler(
                    user_id=sender,
                    message=text,
                    history=session.get("messages", []),
                )
            except Exception as e:
                logger.error("Agent handler error: %s", e)
                return "Sorry, I encountered an error processing your request. Please try again."

        # Fallback response when no agent handler is configured
        return (
            "👋 Welcome to CeloFlow!\n\n"
            "I can help you send money globally using the Celo blockchain.\n"
            "Type your request in natural language, e.g.:\n"
            "• 'Send 50 USD to Philippines'\n"
            "• 'Check my balance'\n"
            "• 'What are the rates for MXN?'"
        )

    # ------------------------------------------------------------------
    # Private: session management
    # ------------------------------------------------------------------

    def _get_or_create_session(self, phone: str) -> Dict[str, Any]:
        """Get or create a user session."""
        if phone not in self._sessions:
            self._sessions[phone] = {
                "messages": [],
                "last_active": time.time(),
                "language": "en",
                "created_at": time.time(),
            }
        return self._sessions[phone]

    # ------------------------------------------------------------------
    # Private: API call
    # ------------------------------------------------------------------

    async def _send_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message via WhatsApp Business API."""
        url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                self._stats["messages_sent"] += 1
                if response.status_code == 200:
                    return {"sent": True, "response": response.json()}
                logger.warning(
                    "WhatsApp API error %d: %s",
                    response.status_code,
                    response.text[:200],
                )
                return {"sent": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("WhatsApp API call failed: %s", e)
            return {"sent": False, "error": str(e)}
