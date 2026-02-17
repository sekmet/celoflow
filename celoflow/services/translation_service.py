"""Translation Service — multi-language translation with financial terminology.

Integrates with translation APIs (Google Translate, DeepL) with caching
for common phrases and financial terminology accuracy.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Cache TTL for translations (1 hour)
TRANSLATION_CACHE_TTL = 3_600

# Financial terminology that needs precise translation
FINANCIAL_TERMS: Dict[str, Dict[str, str]] = {
    "es": {
        "transfer": "transferencia",
        "fee": "comisión",
        "exchange rate": "tipo de cambio",
        "wallet": "billetera",
        "balance": "saldo",
        "recipient": "destinatario",
        "sender": "remitente",
        "transaction": "transacción",
        "stablecoin": "moneda estable",
        "blockchain": "cadena de bloques",
        "remittance": "remesa",
        "compliance": "cumplimiento",
        "verification": "verificación",
        "savings": "ahorros",
        "deposit": "depósito",
        "withdrawal": "retiro",
    },
    "pt": {
        "transfer": "transferência",
        "fee": "taxa",
        "exchange rate": "taxa de câmbio",
        "wallet": "carteira",
        "balance": "saldo",
        "recipient": "destinatário",
        "sender": "remetente",
        "transaction": "transação",
        "stablecoin": "moeda estável",
        "blockchain": "cadeia de blocos",
        "remittance": "remessa",
        "compliance": "conformidade",
        "verification": "verificação",
        "savings": "economia",
        "deposit": "depósito",
        "withdrawal": "saque",
    },
    "fr": {
        "transfer": "transfert",
        "fee": "frais",
        "exchange rate": "taux de change",
        "wallet": "portefeuille",
        "balance": "solde",
        "recipient": "destinataire",
        "sender": "expéditeur",
        "transaction": "transaction",
        "stablecoin": "monnaie stable",
        "blockchain": "chaîne de blocs",
        "remittance": "envoi de fonds",
        "compliance": "conformité",
        "verification": "vérification",
        "savings": "économies",
        "deposit": "dépôt",
        "withdrawal": "retrait",
    },
    "sw": {
        "transfer": "uhamisho",
        "fee": "ada",
        "exchange rate": "kiwango cha ubadilishaji",
        "wallet": "pochi",
        "balance": "salio",
        "recipient": "mpokeaji",
        "sender": "mtumaji",
        "transaction": "muamala",
        "remittance": "uhamisho wa fedha",
        "savings": "akiba",
    },
    "tl": {
        "transfer": "paglipat",
        "fee": "bayad",
        "exchange rate": "palitan ng pera",
        "wallet": "pitaka",
        "balance": "balanse",
        "recipient": "tatanggap",
        "sender": "nagpadala",
        "transaction": "transaksyon",
        "remittance": "padala",
        "savings": "ipon",
    },
}

# Common phrases pre-translated for speed
COMMON_PHRASES: Dict[str, Dict[str, str]] = {
    "es": {
        "How can I help you today?": "¿Cómo puedo ayudarte hoy?",
        "Transaction successful!": "¡Transacción exitosa!",
        "Transfer complete": "Transferencia completada",
        "Please confirm the transfer": "Por favor confirma la transferencia",
        "Checking exchange rates...": "Verificando tipos de cambio...",
        "Your balance is": "Tu saldo es",
        "Fee breakdown": "Desglose de comisiones",
        "You save": "Ahorras",
        "compared to traditional banks": "comparado con bancos tradicionales",
    },
    "pt": {
        "How can I help you today?": "Como posso ajudá-lo hoje?",
        "Transaction successful!": "Transação bem-sucedida!",
        "Transfer complete": "Transferência concluída",
        "Please confirm the transfer": "Por favor confirme a transferência",
        "Checking exchange rates...": "Verificando taxas de câmbio...",
        "Your balance is": "Seu saldo é",
        "Fee breakdown": "Detalhamento de taxas",
        "You save": "Você economiza",
        "compared to traditional banks": "comparado com bancos tradicionais",
    },
    "fr": {
        "How can I help you today?": "Comment puis-je vous aider aujourd'hui ?",
        "Transaction successful!": "Transaction réussie !",
        "Transfer complete": "Transfert terminé",
        "Please confirm the transfer": "Veuillez confirmer le transfert",
        "Checking exchange rates...": "Vérification des taux de change...",
        "Your balance is": "Votre solde est",
        "Fee breakdown": "Détail des frais",
        "You save": "Vous économisez",
        "compared to traditional banks": "par rapport aux banques traditionnelles",
    },
}


class TranslationService:
    """Multi-language translation with financial terminology support."""

    def __init__(
        self,
        google_api_key: Optional[str] = None,
        deepl_api_key: Optional[str] = None,
        default_source_lang: str = "en",
    ) -> None:
        self.google_api_key = google_api_key
        self.deepl_api_key = deepl_api_key
        self.default_source_lang = default_source_lang
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._has_api = bool(google_api_key or deepl_api_key)
        logger.info(
            "TranslationService initialised (google=%s, deepl=%s)",
            bool(google_api_key),
            bool(deepl_api_key),
        )

    # ------------------------------------------------------------------
    # Public: translate
    # ------------------------------------------------------------------

    async def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Translate text to the target language.

        Args:
            text: Text to translate
            target_lang: Target language code (e.g., 'es', 'pt', 'fr')
            source_lang: Source language code (defaults to 'en')

        Returns:
            Translation result with text, source, target, and confidence
        """
        src = source_lang or self.default_source_lang

        if src == target_lang:
            return {
                "text": text,
                "source_lang": src,
                "target_lang": target_lang,
                "method": "passthrough",
            }

        # 1. Check common phrases cache
        common = COMMON_PHRASES.get(target_lang, {}).get(text)
        if common:
            return {
                "text": common,
                "source_lang": src,
                "target_lang": target_lang,
                "method": "common_phrase",
            }

        # 2. Check translation cache
        cache_key = self._cache_key(text, src, target_lang)
        cached = self._get_cached(cache_key)
        if cached:
            cached["method"] = "cache"
            return cached

        # 3. Try API translation
        if self._has_api:
            result = await self._api_translate(text, target_lang, src)
            if result and not result.get("error"):
                self._set_cached(cache_key, result)
                return result

        # 4. Fallback: apply financial term substitution
        translated = self._apply_financial_terms(text, target_lang)
        result = {
            "text": translated,
            "source_lang": src,
            "target_lang": target_lang,
            "method": "term_substitution",
            "note": "Partial translation using financial terminology dictionary",
        }
        self._set_cached(cache_key, result)
        return result

    # ------------------------------------------------------------------
    # Public: translate_financial_term
    # ------------------------------------------------------------------

    def translate_financial_term(
        self, term: str, target_lang: str
    ) -> Optional[str]:
        """Translate a specific financial term accurately.

        Args:
            term: Financial term in English
            target_lang: Target language code

        Returns:
            Translated term or None if not found
        """
        terms = FINANCIAL_TERMS.get(target_lang, {})
        return terms.get(term.lower())

    # ------------------------------------------------------------------
    # Public: get_supported_languages
    # ------------------------------------------------------------------

    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Return list of supported translation languages."""
        return [
            {"code": "en", "name": "English"},
            {"code": "es", "name": "Spanish"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "fr", "name": "French"},
            {"code": "sw", "name": "Swahili"},
            {"code": "tl", "name": "Filipino/Tagalog"},
        ]

    # ------------------------------------------------------------------
    # Public: validate_translation
    # ------------------------------------------------------------------

    def validate_translation(
        self, original: str, translated: str, target_lang: str
    ) -> Dict[str, Any]:
        """Validate a translation for financial accuracy.

        Checks that key financial terms are correctly translated.

        Args:
            original: Original English text
            translated: Translated text
            target_lang: Target language code

        Returns:
            Validation result with issues if any
        """
        issues: List[str] = []
        terms = FINANCIAL_TERMS.get(target_lang, {})

        for en_term, local_term in terms.items():
            if en_term.lower() in original.lower():
                if local_term.lower() not in translated.lower():
                    issues.append(
                        f"Term '{en_term}' should be translated as '{local_term}'"
                    )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "terms_checked": len(terms),
        }

    # ------------------------------------------------------------------
    # Private: API translation
    # ------------------------------------------------------------------

    async def _api_translate(
        self, text: str, target_lang: str, source_lang: str
    ) -> Optional[Dict[str, Any]]:
        """Translate via external API (DeepL preferred, Google fallback)."""
        # Try DeepL first (better quality for European languages)
        if self.deepl_api_key:
            result = await self._deepl_translate(text, target_lang, source_lang)
            if result:
                return result

        # Fallback to Google Translate
        if self.google_api_key:
            result = await self._google_translate(text, target_lang, source_lang)
            if result:
                return result

        return None

    async def _deepl_translate(
        self, text: str, target_lang: str, source_lang: str
    ) -> Optional[Dict[str, Any]]:
        """Translate via DeepL API."""
        # DeepL uses uppercase language codes
        deepl_target = target_lang.upper()
        if deepl_target == "EN":
            deepl_target = "EN-US"
        if deepl_target == "PT":
            deepl_target = "PT-BR"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api-free.deepl.com/v2/translate",
                    data={
                        "auth_key": self.deepl_api_key,
                        "text": text,
                        "target_lang": deepl_target,
                        "source_lang": source_lang.upper(),
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    translated = data["translations"][0]["text"]
                    return {
                        "text": translated,
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                        "method": "deepl",
                    }
        except Exception as e:
            logger.warning("DeepL translation failed: %s", e)
        return None

    async def _google_translate(
        self, text: str, target_lang: str, source_lang: str
    ) -> Optional[Dict[str, Any]]:
        """Translate via Google Translate API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://translation.googleapis.com/language/translate/v2",
                    params={"key": self.google_api_key},
                    json={
                        "q": text,
                        "target": target_lang,
                        "source": source_lang,
                        "format": "text",
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    translated = data["data"]["translations"][0]["translatedText"]
                    return {
                        "text": translated,
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                        "method": "google",
                    }
        except Exception as e:
            logger.warning("Google Translate failed: %s", e)
        return None

    # ------------------------------------------------------------------
    # Private: financial term substitution
    # ------------------------------------------------------------------

    def _apply_financial_terms(self, text: str, target_lang: str) -> str:
        """Apply financial terminology substitution as a fallback."""
        terms = FINANCIAL_TERMS.get(target_lang, {})
        result = text
        for en_term, local_term in sorted(
            terms.items(), key=lambda x: len(x[0]), reverse=True
        ):
            # Case-insensitive replacement
            import re
            result = re.sub(
                re.escape(en_term), local_term, result, flags=re.IGNORECASE
            )
        return result

    # ------------------------------------------------------------------
    # Private: caching
    # ------------------------------------------------------------------

    def _cache_key(self, text: str, source: str, target: str) -> str:
        """Generate a cache key for a translation."""
        content = f"{source}:{target}:{text}"
        return hashlib.md5(content.encode()).hexdigest()

    def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached translation."""
        cached = self._cache.get(key)
        if cached and cached["expires_at"] > time.time():
            return dict(cached["data"])
        return None

    def _set_cached(self, key: str, data: Dict[str, Any]) -> None:
        """Cache a translation result."""
        self._cache[key] = {
            "data": data,
            "expires_at": time.time() + TRANSLATION_CACHE_TTL,
        }
        # Limit cache size
        if len(self._cache) > 5000:
            # Remove oldest entries
            sorted_keys = sorted(
                self._cache.keys(),
                key=lambda k: self._cache[k]["expires_at"],
            )
            for k in sorted_keys[:1000]:
                del self._cache[k]
