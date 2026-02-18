"""Intent Parsing Service — extract structured transfer data from natural language.

Parses complex multi-language remittance requests into structured intents:
amounts, currencies, recipients, frequency, and preferences.

Integrates with LanguageDetectionService and TranslationService for
multi-language support across 6 languages.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Currency aliases: user-facing names → canonical symbols
CURRENCY_ALIASES: Dict[str, str] = {
    # USD variants
    "usd": "USDm", "dollar": "USDm", "dollars": "USDm", "cusd": "USDm",
    "usdm": "USDm", "us dollar": "USDm", "us dollars": "USDm",
    # EUR variants
    "eur": "EURm", "euro": "EURm", "euros": "EURm", "ceur": "EURm", "eurm": "EURm",
    # BRL variants
    "brl": "BRLm", "real": "BRLm", "reais": "BRLm", "creal": "BRLm", "brlm": "BRLm",
    "brazilian real": "BRLm",
    # PHP variants
    "php": "PHPm", "peso": "PHPm", "pesos": "PHPm", "phpm": "PHPm",
    "philippine peso": "PHPm", "puso": "PHPm",
    # XOF variants
    "xof": "XOFm", "cfa": "XOFm", "xofm": "XOFm", "exof": "XOFm",
    "cfa franc": "XOFm",
    # KES variants
    "kes": "KESm", "shilling": "KESm", "shillingi": "KESm", "kesm": "KESm",
    "kenyan shilling": "KESm",
    # COP variants
    "cop": "COPm", "copm": "COPm", "colombian peso": "COPm",
    # GBP variants
    "gbp": "GBPm", "pound": "GBPm", "pounds": "GBPm", "gbpm": "GBPm",
    "british pound": "GBPm",
    # CAD variants
    "cad": "CADm", "cadm": "CADm", "canadian dollar": "CADm",
    # AUD variants
    "aud": "AUDm", "audm": "AUDm", "australian dollar": "AUDm",
    # ZAR variants
    "zar": "ZARm", "rand": "ZARm", "zarm": "ZARm", "south african rand": "ZARm",
    # GHS variants
    "ghs": "GHSm", "cedi": "GHSm", "ghsm": "GHSm", "ghanaian cedi": "GHSm",
    # NGN variants
    "ngn": "NGNm", "naira": "NGNm", "ngnm": "NGNm", "nigerian naira": "NGNm",
    # JPY variants
    "jpy": "JPYm", "yen": "JPYm", "jpym": "JPYm", "japanese yen": "JPYm",
    # CHF variants
    "chf": "CHFm", "franc": "CHFm", "chfm": "CHFm", "swiss franc": "CHFm",
    # Native
    "celo": "CELO",
    # Other
    "usdc": "USDC", "usdt": "USDT",
}

# Country → default currency mapping
COUNTRY_CURRENCY: Dict[str, str] = {
    "philippines": "PHPm", "brazil": "BRLm", "nigeria": "NGNm",
    "kenya": "KESm", "senegal": "XOFm", "colombia": "COPm",
    "uk": "GBPm", "united kingdom": "GBPm", "england": "GBPm",
    "canada": "CADm", "australia": "AUDm", "south africa": "ZARm",
    "ghana": "GHSm", "japan": "JPYm", "switzerland": "CHFm",
    "france": "EURm", "germany": "EURm", "spain": "EURm",
    "italy": "EURm", "portugal": "EURm", "mexico": "COPm",
    "usa": "USDm", "united states": "USDm",
}

# Frequency keywords (multi-language)
FREQUENCY_PATTERNS: Dict[str, str] = {
    # English
    "daily": "daily", "every day": "daily",
    "weekly": "weekly", "every week": "weekly",
    "monthly": "monthly", "every month": "monthly",
    "biweekly": "biweekly", "every two weeks": "biweekly",
    # Spanish
    "diario": "daily", "cada día": "daily", "diariamente": "daily",
    "semanal": "weekly", "cada semana": "weekly", "semanalmente": "weekly",
    "mensual": "monthly", "cada mes": "monthly", "mensualmente": "monthly",
    # Portuguese
    "diário": "daily", "todo dia": "daily",
    "semanal": "weekly", "toda semana": "weekly",
    "mensal": "monthly", "todo mês": "monthly",
    # French
    "quotidien": "daily", "chaque jour": "daily",
    "hebdomadaire": "weekly", "chaque semaine": "weekly",
    "mensuel": "monthly", "chaque mois": "monthly",
    # Swahili
    "kila siku": "daily", "kila wiki": "weekly", "kila mwezi": "monthly",
    # Filipino
    "araw-araw": "daily", "lingguhan": "weekly", "buwanan": "monthly",
}

# Relationship keywords → recipient hints
RELATIONSHIP_KEYWORDS: Dict[str, str] = {
    "mom": "mother", "mama": "mother", "mamá": "mother", "mãe": "mother",
    "maman": "mother", "mama": "mother", "nanay": "mother",
    "dad": "father", "papá": "father", "pai": "father", "papa": "father",
    "tatay": "father", "baba": "father",
    "brother": "brother", "hermano": "brother", "irmão": "brother",
    "frère": "brother", "kapatid": "brother",
    "sister": "sister", "hermana": "sister", "irmã": "sister",
    "sœur": "sister",
    "wife": "wife", "esposa": "wife",
    "husband": "husband", "esposo": "husband", "marido": "husband",
    "friend": "friend", "amigo": "friend", "ami": "friend",
}


class IntentParsingService:
    """Parse natural language remittance requests into structured intents."""

    def __init__(
        self,
        language_service: Optional[Any] = None,
        translation_service: Optional[Any] = None,
    ) -> None:
        self._language_service = language_service
        self._translation_service = translation_service
        logger.info("IntentParsingService initialised")

    # ------------------------------------------------------------------
    # Public: parse_intent
    # ------------------------------------------------------------------

    def parse_intent(self, text: str, user_id: str = "") -> Dict[str, Any]:
        """Parse a natural language message into a structured transfer intent.

        Args:
            text: User message (any supported language)
            user_id: Optional user identifier for language preference

        Returns:
            Parsed intent with amount, currency, recipient, schedule, etc.
        """
        if not text or not text.strip():
            return self._empty_intent("Empty input")

        cleaned = text.strip()

        # 1. Detect language
        language = "en"
        if self._language_service:
            detection = self._language_service.detect_language(cleaned)
            language = detection.get("language", "en")

        # 2. Extract components
        amount, currency_hint = self._extract_amount_and_currency(cleaned)
        recipient = self._extract_recipient(cleaned)
        destination_country = self._extract_country(cleaned)
        frequency = self._extract_frequency(cleaned)
        relationship = self._extract_relationship(cleaned)

        # 3. Resolve currency
        currency = self._resolve_currency(currency_hint, destination_country)

        # 4. Determine intent type
        intent_type = self._classify_intent(cleaned, amount, frequency)

        # 5. Build confidence score
        confidence = self._calculate_confidence(
            amount=amount,
            currency=currency,
            recipient=recipient,
            intent_type=intent_type,
        )

        # 6. Identify missing fields for clarification
        missing_fields = self._identify_missing_fields(
            amount=amount,
            currency=currency,
            recipient=recipient,
            intent_type=intent_type,
        )

        result: Dict[str, Any] = {
            "intent_type": intent_type,
            "amount": float(amount) if amount else None,
            "currency": currency,
            "recipient": recipient,
            "destination_country": destination_country,
            "frequency": frequency,
            "relationship": relationship,
            "language": language,
            "confidence": confidence,
            "needs_clarification": len(missing_fields) > 0,
            "missing_fields": missing_fields,
            "raw_text": text,
        }

        logger.info(
            "Parsed intent: type=%s amount=%s currency=%s recipient=%s confidence=%.2f",
            intent_type, amount, currency, recipient, confidence,
        )
        return result

    # ------------------------------------------------------------------
    # Public: generate_clarification
    # ------------------------------------------------------------------

    def generate_clarification(self, intent: Dict[str, Any]) -> str:
        """Generate a clarification prompt for missing fields.

        Args:
            intent: Parsed intent with missing_fields

        Returns:
            Human-readable clarification question
        """
        missing = intent.get("missing_fields", [])
        if not missing:
            return ""

        prompts = []
        if "amount" in missing:
            prompts.append("How much would you like to send?")
        if "currency" in missing:
            prompts.append("Which currency? (e.g., USD, BRL, PHP)")
        if "recipient" in missing:
            prompts.append("Who should I send it to? (name or wallet address)")

        return " ".join(prompts)

    # ------------------------------------------------------------------
    # Public: validate_intent
    # ------------------------------------------------------------------

    def validate_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a parsed intent for execution readiness.

        Args:
            intent: Parsed intent dict

        Returns:
            Validation result with is_valid flag and issues list
        """
        issues: List[str] = []

        amount = intent.get("amount")
        if amount is None or amount <= 0:
            issues.append("Invalid or missing transfer amount")
        elif amount > 100_000:
            issues.append("Amount exceeds maximum single transfer limit ($100,000)")

        if not intent.get("currency"):
            issues.append("Currency not specified")

        if not intent.get("recipient"):
            issues.append("Recipient not specified")

        if intent.get("frequency") and not intent.get("recipient"):
            issues.append("Recurring transfers require a recipient")

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "intent": intent,
        }

    # ------------------------------------------------------------------
    # Private: extract amount and currency hint
    # ------------------------------------------------------------------

    def _extract_amount_and_currency(
        self, text: str
    ) -> Tuple[Optional[Decimal], Optional[str]]:
        """Extract numeric amount and currency hint from text."""
        lower = text.lower()

        # Pattern: "$50", "50 USD", "50 dollars", "R$100", "€50"
        # IMPORTANT: R$ must come before bare $ to avoid false match
        patterns = [
            # R$100 (Brazilian Real) — must precede bare $; case-insensitive r/R
            r"[rR]\$\s*([\d,]+(?:\.\d+)?)",
            # $50, $50.00
            r"\$\s*([\d,]+(?:\.\d+)?)",
            # €50
            r"€\s*([\d,]+(?:\.\d+)?)",
            # £50
            r"£\s*([\d,]+(?:\.\d+)?)",
            # ₱100 (Philippine Peso)
            r"₱\s*([\d,]+(?:\.\d+)?)",
            # 50 USD, 50 dollars, 50 BRLm, etc.
            r"([\d,]+(?:\.\d+)?)\s*([a-zA-Z$€£₱]+)",
            # "send 50 to" (amount without explicit currency)
            r"(?:send|transfer|enviar|envoyer|tuma|magpadala)\s+([\d,]+(?:\.\d+)?)",
        ]

        amount: Optional[Decimal] = None
        currency_hint: Optional[str] = None

        for pattern in patterns:
            match = re.search(pattern, lower)
            if match:
                groups = match.groups()
                raw_amount = groups[0].replace(",", "")
                try:
                    amount = Decimal(raw_amount)
                except InvalidOperation:
                    continue

                # Extract currency from symbol or text
                if pattern.startswith(r"[rR]\$"):
                    currency_hint = "BRLm"
                elif pattern.startswith(r"\$"):
                    currency_hint = "USDm"
                elif pattern.startswith("€"):
                    currency_hint = "EURm"
                elif pattern.startswith("£"):
                    currency_hint = "GBPm"
                elif pattern.startswith("₱"):
                    currency_hint = "PHPm"
                elif len(groups) > 1 and groups[1]:
                    currency_hint = groups[1].strip()

                break

        return amount, currency_hint

    def _extract_recipient(self, text: str) -> Optional[str]:
        """Extract recipient name or address from text."""
        lower = text.lower()

        # Pattern: 0x address
        addr_match = re.search(r"(0x[a-fA-F0-9]{40})", text)
        if addr_match:
            return addr_match.group(1)

        # Pattern: "to [Name]", "a [Name]" (Spanish/Portuguese)
        to_patterns = [
            r"(?:to|for)\s+(?:my\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"(?:para|a)\s+(?:mi\s+|meu\s+|minha\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"(?:à|pour)\s+(?:mon\s+|ma\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"(?:kwa)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"(?:kay|para kay)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        ]

        for pattern in to_patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                # Filter out common non-name words
                skip_words = {
                    "Brazil", "Philippines", "Nigeria", "Kenya", "Ghana",
                    "Senegal", "Colombia", "Mexico", "Japan", "France",
                    "The", "My", "Send", "Transfer",
                }
                if name not in skip_words:
                    return name

        # Check for relationship keywords as recipient hints
        for keyword in RELATIONSHIP_KEYWORDS:
            if keyword in lower:
                return keyword

        return None

    def _extract_country(self, text: str) -> Optional[str]:
        """Extract destination country from text."""
        lower = text.lower()
        for country in COUNTRY_CURRENCY:
            if country in lower:
                return country
        # Check "in [Country]" pattern
        match = re.search(r"(?:in|to|en)\s+the\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
        if match:
            country_name = match.group(1).lower()
            if country_name in COUNTRY_CURRENCY:
                return country_name
        return None

    def _extract_frequency(self, text: str) -> Optional[str]:
        """Extract transfer frequency/schedule from text."""
        lower = text.lower()
        for pattern, freq in FREQUENCY_PATTERNS.items():
            if pattern in lower:
                return freq
        return None

    def _extract_relationship(self, text: str) -> Optional[str]:
        """Extract relationship keyword from text."""
        lower = text.lower()
        for keyword, relationship in RELATIONSHIP_KEYWORDS.items():
            if keyword in lower.split():
                return relationship
        return None

    def _resolve_currency(
        self,
        currency_hint: Optional[str],
        destination_country: Optional[str],
    ) -> Optional[str]:
        """Resolve currency from hint or destination country."""
        if currency_hint:
            normalized = currency_hint.lower().strip()
            if normalized in CURRENCY_ALIASES:
                return CURRENCY_ALIASES[normalized]
            # Check if it's already a valid symbol
            upper = currency_hint.upper()
            if upper.endswith("m") or upper in ("CELO", "USDC", "USDT"):
                return currency_hint

        if destination_country:
            return COUNTRY_CURRENCY.get(destination_country.lower())

        return None

    def _classify_intent(
        self,
        text: str,
        amount: Optional[Decimal],
        frequency: Optional[str],
    ) -> str:
        """Classify the type of intent."""
        lower = text.lower()

        if frequency:
            return "recurring_transfer"

        if any(w in lower for w in ["balance", "saldo", "balanse", "salio"]):
            return "balance_check"

        if any(w in lower for w in ["rate", "rates", "tipo de cambio", "taux"]):
            return "rate_check"

        if any(w in lower for w in ["swap", "convert", "exchange", "cambiar", "trocar"]):
            return "currency_swap"

        if any(w in lower for w in ["fee", "fees", "comisión", "taxa", "frais", "ada", "bayad"]):
            return "fee_check"

        if amount is not None:
            return "single_transfer"

        if any(w in lower for w in [
            "send", "transfer", "enviar", "envoyer", "tuma", "magpadala",
            "pay", "pagar",
        ]):
            return "single_transfer"

        return "general_query"

    def _calculate_confidence(
        self,
        amount: Optional[Decimal],
        currency: Optional[str],
        recipient: Optional[str],
        intent_type: str,
    ) -> float:
        """Calculate confidence score for the parsed intent."""
        score = 0.0

        if intent_type in ("balance_check", "rate_check", "fee_check", "general_query"):
            return 0.8

        if amount is not None and amount > 0:
            score += 0.35
        if currency:
            score += 0.25
        if recipient:
            score += 0.25
        if intent_type != "general_query":
            score += 0.15

        return min(round(score, 2), 1.0)

    def _identify_missing_fields(
        self,
        amount: Optional[Decimal],
        currency: Optional[str],
        recipient: Optional[str],
        intent_type: str,
    ) -> List[str]:
        """Identify fields that need clarification."""
        if intent_type in ("balance_check", "rate_check", "fee_check", "general_query"):
            return []

        missing: List[str] = []
        if amount is None or amount <= 0:
            missing.append("amount")
        if not currency:
            missing.append("currency")
        if not recipient:
            missing.append("recipient")
        return missing

    def _empty_intent(self, reason: str) -> Dict[str, Any]:
        """Return an empty intent with a reason."""
        return {
            "intent_type": "unknown",
            "amount": None,
            "currency": None,
            "recipient": None,
            "destination_country": None,
            "frequency": None,
            "relationship": None,
            "language": "en",
            "confidence": 0.0,
            "needs_clarification": True,
            "missing_fields": ["amount", "currency", "recipient"],
            "raw_text": "",
            "error": reason,
        }
