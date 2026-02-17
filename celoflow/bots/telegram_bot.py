"""Telegram Bot — Telegram Bot API integration for CeloFlow.

Handles incoming Telegram messages, provides inline keyboards for
transaction confirmations, and sends formatted notifications.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram Bot API integration for CeloFlow remittance agent."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        agent_handler: Optional[Callable[..., Coroutine[Any, Any, str]]] = None,
    ) -> None:
        self.bot_token = bot_token
        self.agent_handler = agent_handler
        self._is_configured = bool(bot_token)
        self._base_url = f"https://api.telegram.org/bot{bot_token}" if bot_token else ""

        # Session management: chat_id -> {messages, last_active, language}
        self._sessions: Dict[str, Dict[str, Any]] = {}

        # Analytics
        self._stats: Dict[str, int] = {
            "messages_received": 0,
            "messages_sent": 0,
            "callbacks_handled": 0,
            "errors": 0,
        }

        logger.info("TelegramBot initialised (configured=%s)", self._is_configured)

    # ------------------------------------------------------------------
    # Public: handle_update
    # ------------------------------------------------------------------

    async def handle_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming Telegram update.

        Args:
            update: Telegram update object

        Returns:
            Processing result
        """
        try:
            # Handle message
            message = update.get("message")
            if message:
                return await self._process_message(message)

            # Handle callback query (inline keyboard button press)
            callback = update.get("callback_query")
            if callback:
                return await self._process_callback(callback)

            return {"status": "ignored", "reason": "unsupported_update_type"}

        except Exception as e:
            self._stats["errors"] += 1
            logger.error("Telegram update error: %s", e)
            return {"status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # Public: send_message
    # ------------------------------------------------------------------

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a text message to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            text: Message text (supports Markdown)
            parse_mode: Parse mode (Markdown or HTML)
            reply_markup: Optional inline keyboard markup

        Returns:
            Send result
        """
        if not self._is_configured:
            logger.info("Telegram (dry-run) to %s: %s", chat_id, text[:100])
            return {"sent": False, "mode": "dry-run", "chat_id": chat_id}

        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        return await self._api_call("sendMessage", payload)

    # ------------------------------------------------------------------
    # Public: send_transfer_confirmation
    # ------------------------------------------------------------------

    async def send_transfer_confirmation(
        self,
        chat_id: str,
        amount: str,
        currency: str,
        recipient: str,
        fee: str,
        transfer_id: str,
    ) -> Dict[str, Any]:
        """Send a transfer confirmation with inline keyboard buttons.

        Args:
            chat_id: Telegram chat ID
            amount: Transfer amount
            currency: Currency code
            recipient: Recipient identifier
            fee: Fee amount
            transfer_id: Unique transfer ID for callback

        Returns:
            Send result
        """
        text = (
            f"💸 *Transfer Confirmation*\n\n"
            f"📤 Amount: {amount} {currency}\n"
            f"👤 To: {recipient}\n"
            f"💰 Fee: {fee} {currency}\n\n"
            f"_Please confirm this transfer:_"
        )

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Confirm", "callback_data": f"confirm_{transfer_id}"},
                    {"text": "❌ Cancel", "callback_data": f"cancel_{transfer_id}"},
                ],
                [
                    {"text": "📊 Fee Details", "callback_data": f"fees_{transfer_id}"},
                ],
            ]
        }

        return await self.send_message(chat_id, text, reply_markup=keyboard)

    # ------------------------------------------------------------------
    # Public: send_transaction_notification
    # ------------------------------------------------------------------

    async def send_transaction_notification(
        self,
        chat_id: str,
        tx_hash: str,
        amount: str,
        currency: str,
        status: str,
    ) -> Dict[str, Any]:
        """Send a transaction status notification.

        Args:
            chat_id: Telegram chat ID
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
            f"{emoji} *Transfer {status.title()}*\n\n"
            f"💰 Amount: {amount} {currency}\n"
            f"🔗 TX: `{tx_hash[:20]}...`\n\n"
        )

        if status == "completed":
            text += "Your transfer has been confirmed on the Celo blockchain! 🎉"
        elif status == "failed":
            text += "Transfer failed. Please try again or contact support."

        keyboard = None
        if status == "completed" and tx_hash.startswith("0x"):
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "🔍 View on CeloScan",
                            "url": f"https://celoscan.io/tx/{tx_hash}",
                        }
                    ]
                ]
            }

        return await self.send_message(chat_id, text, reply_markup=keyboard)

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

    async def _process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single incoming message."""
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")
        user = message.get("from", {})
        username = user.get("username", user.get("first_name", "unknown"))

        if not text or not chat_id:
            return {"status": "ignored", "reason": "no_text_or_chat"}

        self._stats["messages_received"] += 1

        # Handle commands
        if text.startswith("/"):
            return await self._handle_command(chat_id, text, username)

        # Get or create session
        session = self._get_or_create_session(chat_id)

        # Route to agent
        response_text = await self._route_to_agent(chat_id, text, session)

        # Send response
        await self.send_message(chat_id, response_text)

        # Update session
        session["messages"].append({"role": "user", "content": text, "timestamp": time.time()})
        session["messages"].append({"role": "assistant", "content": response_text, "timestamp": time.time()})
        session["last_active"] = time.time()

        return {"status": "processed", "chat_id": chat_id}

    async def _handle_command(
        self, chat_id: str, command: str, username: str
    ) -> Dict[str, Any]:
        """Handle Telegram bot commands."""
        cmd = command.split()[0].lower()

        if cmd == "/start":
            welcome = (
                f"👋 Welcome to *CeloFlow*, {username}!\n\n"
                f"I'm your AI-powered remittance assistant on the Celo blockchain.\n\n"
                f"*What I can do:*\n"
                f"• Send money globally in seconds\n"
                f"• Compare fees with traditional services\n"
                f"• Check exchange rates\n"
                f"• Track your transfers\n\n"
                f"Just type your request in natural language!"
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "💸 Send Money", "callback_data": "action_send"},
                        {"text": "💰 Check Balance", "callback_data": "action_balance"},
                    ],
                    [
                        {"text": "📊 Exchange Rates", "callback_data": "action_rates"},
                        {"text": "🌐 Language", "callback_data": "action_language"},
                    ],
                ]
            }
            await self.send_message(chat_id, welcome, reply_markup=keyboard)
            return {"status": "command", "command": "start"}

        elif cmd == "/help":
            help_text = (
                "*CeloFlow Commands:*\n\n"
                "/start — Start the bot\n"
                "/help — Show this help\n"
                "/balance — Check wallet balance\n"
                "/rates — View exchange rates\n"
                "/history — Transaction history\n\n"
                "Or just type naturally:\n"
                "_'Send 100 USD to Philippines'_"
            )
            await self.send_message(chat_id, help_text)
            return {"status": "command", "command": "help"}

        elif cmd in ("/balance", "/rates", "/history"):
            # Route to agent as natural language
            text_map = {
                "/balance": "What is my wallet balance?",
                "/rates": "Show me current exchange rates",
                "/history": "Show my transaction history",
            }
            session = self._get_or_create_session(chat_id)
            response = await self._route_to_agent(chat_id, text_map[cmd], session)
            await self.send_message(chat_id, response)
            return {"status": "command", "command": cmd}

        else:
            await self.send_message(chat_id, "Unknown command. Type /help for available commands.")
            return {"status": "command", "command": "unknown"}

    # ------------------------------------------------------------------
    # Private: process callback
    # ------------------------------------------------------------------

    async def _process_callback(self, callback: Dict[str, Any]) -> Dict[str, Any]:
        """Process an inline keyboard callback."""
        callback_id = callback.get("id", "")
        data = callback.get("data", "")
        chat_id = str(callback.get("message", {}).get("chat", {}).get("id", ""))

        self._stats["callbacks_handled"] += 1

        # Acknowledge the callback
        if self._is_configured:
            await self._api_call("answerCallbackQuery", {"callback_query_id": callback_id})

        # Handle action callbacks
        if data.startswith("action_"):
            action = data.replace("action_", "")
            action_map = {
                "send": "I want to send money",
                "balance": "Check my balance",
                "rates": "Show exchange rates",
                "language": "Change language settings",
            }
            text = action_map.get(action, action)
            session = self._get_or_create_session(chat_id)
            response = await self._route_to_agent(chat_id, text, session)
            await self.send_message(chat_id, response)

        elif data.startswith("confirm_"):
            await self.send_message(chat_id, "✅ Transfer confirmed! Processing...")

        elif data.startswith("cancel_"):
            await self.send_message(chat_id, "❌ Transfer cancelled.")

        elif data.startswith("fees_"):
            await self.send_message(
                chat_id,
                "📊 *Fee Breakdown:*\n"
                "• Network fee: 0.1%\n"
                "• Agent fee: 0.5%\n"
                "• Liquidity fee: 0.25%\n"
                "• Total: ~0.85%",
            )

        return {"status": "callback", "data": data, "chat_id": chat_id}

    # ------------------------------------------------------------------
    # Private: route to agent
    # ------------------------------------------------------------------

    async def _route_to_agent(
        self, chat_id: str, text: str, session: Dict[str, Any]
    ) -> str:
        """Route message to the core agent."""
        if self.agent_handler:
            try:
                return await self.agent_handler(
                    user_id=chat_id,
                    message=text,
                    history=session.get("messages", []),
                )
            except Exception as e:
                logger.error("Agent handler error: %s", e)
                return "Sorry, I encountered an error. Please try again."

        return (
            "👋 CeloFlow is ready!\n\n"
            "Type your request, e.g.:\n"
            "• 'Send 50 USD to Philippines'\n"
            "• 'Check rates for EUR to PHP'"
        )

    # ------------------------------------------------------------------
    # Private: session management
    # ------------------------------------------------------------------

    def _get_or_create_session(self, chat_id: str) -> Dict[str, Any]:
        """Get or create a user session."""
        if chat_id not in self._sessions:
            self._sessions[chat_id] = {
                "messages": [],
                "last_active": time.time(),
                "language": "en",
            }
        return self._sessions[chat_id]

    # ------------------------------------------------------------------
    # Private: API call
    # ------------------------------------------------------------------

    async def _api_call(
        self, method: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make a Telegram Bot API call."""
        url = f"{self._base_url}/{method}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload)
                self._stats["messages_sent"] += 1
                if response.status_code == 200:
                    return {"sent": True, "response": response.json()}
                logger.warning(
                    "Telegram API error %d: %s",
                    response.status_code,
                    response.text[:200],
                )
                return {"sent": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("Telegram API call failed: %s", e)
            return {"sent": False, "error": str(e)}
