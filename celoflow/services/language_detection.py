"""Language Detection Service — accurate language detection for user messages.

Supports dialect detection, confidence scoring, and fallback mechanisms.
Uses a lightweight heuristic approach with optional API integration.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Language code to name mapping
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "pt": "Portuguese",
    "fr": "French",
    "sw": "Swahili",
    "tl": "Filipino/Tagalog",
    "hi": "Hindi",
    "ar": "Arabic",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
}

# Dialect mapping
DIALECT_MAP: Dict[str, Dict[str, str]] = {
    "es": {
        "mx": "Mexican Spanish",
        "es": "Spain Spanish",
        "ar": "Argentine Spanish",
        "co": "Colombian Spanish",
    },
    "pt": {
        "br": "Brazilian Portuguese",
        "pt": "European Portuguese",
    },
    "fr": {
        "fr": "Metropolitan French",
        "ca": "Canadian French",
        "sn": "Senegalese French",
    },
    "en": {
        "us": "American English",
        "gb": "British English",
        "ng": "Nigerian English",
        "ph": "Philippine English",
    },
}

# High-frequency word lists for language detection
LANGUAGE_MARKERS: Dict[str, List[str]] = {
    "es": [
        "hola", "enviar", "dinero", "quiero", "cuánto", "pesos", "gracias",
        "por favor", "transferir", "cuenta", "banco", "necesito", "ayuda",
        "cómo", "dónde", "cuándo", "también", "pero", "porque", "está",
        "puede", "hacer", "tiene", "este", "esta", "estos", "estas",
    ],
    "pt": [
        "olá", "enviar", "dinheiro", "quero", "quanto", "reais", "obrigado",
        "por favor", "transferir", "conta", "banco", "preciso", "ajuda",
        "como", "onde", "quando", "também", "mas", "porque", "está",
        "pode", "fazer", "tem", "este", "esta", "estes", "estas", "não",
    ],
    "fr": [
        "bonjour", "envoyer", "argent", "veux", "combien", "euros", "merci",
        "s'il vous plaît", "transférer", "compte", "banque", "besoin", "aide",
        "comment", "où", "quand", "aussi", "mais", "parce", "est",
        "peut", "faire", "cette", "ces", "les", "des", "une", "dans",
    ],
    "sw": [
        "habari", "tuma", "pesa", "nataka", "kiasi", "shillingi", "asante",
        "tafadhali", "hamisha", "akaunti", "benki", "nahitaji", "msaada",
        "vipi", "wapi", "lini", "pia", "lakini", "kwa sababu",
    ],
    "tl": [
        "kumusta", "magpadala", "pera", "gusto", "magkano", "peso", "salamat",
        "pakiusap", "ilipat", "account", "bangko", "kailangan", "tulong",
        "paano", "saan", "kailan", "din", "pero", "dahil", "ang", "mga",
    ],
}

# Character set patterns for script-based detection
SCRIPT_PATTERNS: Dict[str, str] = {
    "ar": r"[\u0600-\u06FF\u0750-\u077F]+",
    "zh": r"[\u4E00-\u9FFF]+",
    "ja": r"[\u3040-\u309F\u30A0-\u30FF]+",
    "ko": r"[\uAC00-\uD7AF\u1100-\u11FF]+",
    "hi": r"[\u0900-\u097F]+",
}


class LanguageDetectionService:
    """Detect language and dialect from user messages."""

    def __init__(
        self,
        default_language: str = "en",
        confidence_threshold: float = 0.3,
    ) -> None:
        self.default_language = default_language
        self.confidence_threshold = confidence_threshold
        # User language preferences: user_id -> language_code
        self._user_preferences: Dict[str, str] = {}
        logger.info(
            "LanguageDetectionService initialised (default=%s, threshold=%.2f)",
            default_language,
            confidence_threshold,
        )

    # ------------------------------------------------------------------
    # Public: detect_language
    # ------------------------------------------------------------------

    def detect_language(self, text: str) -> Dict[str, Any]:
        """Detect the language of a text message.

        Args:
            text: Input text to analyze

        Returns:
            Detection result with language code, name, confidence, and dialect
        """
        if not text or not text.strip():
            return {
                "language": self.default_language,
                "name": SUPPORTED_LANGUAGES.get(self.default_language, "Unknown"),
                "confidence": 0.0,
                "dialect": None,
                "method": "default",
            }

        cleaned = text.lower().strip()

        # 1. Script-based detection (highest priority for non-Latin scripts)
        script_result = self._detect_by_script(cleaned)
        if script_result and script_result["confidence"] > 0.7:
            return script_result

        # 2. Word-frequency detection for Latin-script languages
        word_result = self._detect_by_words(cleaned)

        # 3. Combine results
        if word_result["confidence"] >= self.confidence_threshold:
            # Try dialect detection
            dialect = self._detect_dialect(cleaned, word_result["language"])
            word_result["dialect"] = dialect
            return word_result

        # 4. Fallback to default
        return {
            "language": self.default_language,
            "name": SUPPORTED_LANGUAGES.get(self.default_language, "Unknown"),
            "confidence": 0.1,
            "dialect": None,
            "method": "fallback",
        }

    # ------------------------------------------------------------------
    # Public: get/set user preference
    # ------------------------------------------------------------------

    def get_user_language(self, user_id: str) -> Optional[str]:
        """Get stored language preference for a user."""
        return self._user_preferences.get(user_id)

    def set_user_language(self, user_id: str, language: str) -> None:
        """Store language preference for a user."""
        if language in SUPPORTED_LANGUAGES:
            self._user_preferences[user_id] = language
            logger.info("Language preference set: user=%s lang=%s", user_id, language)

    def detect_and_remember(self, user_id: str, text: str) -> Dict[str, Any]:
        """Detect language and update user preference if confident.

        Args:
            user_id: User identifier
            text: Message text

        Returns:
            Detection result
        """
        result = self.detect_language(text)

        # Only update preference if confidence is high enough
        if result["confidence"] >= 0.5 and result["language"] != self.default_language:
            self.set_user_language(user_id, result["language"])

        # If we have a stored preference and detection is uncertain, use preference
        stored = self._user_preferences.get(user_id)
        if stored and result["confidence"] < self.confidence_threshold:
            result["language"] = stored
            result["name"] = SUPPORTED_LANGUAGES.get(stored, "Unknown")
            result["method"] = "user_preference"
            result["confidence"] = 0.6

        return result

    # ------------------------------------------------------------------
    # Public: get_supported_languages
    # ------------------------------------------------------------------

    def get_supported_languages(self) -> Dict[str, str]:
        """Return all supported languages."""
        return dict(SUPPORTED_LANGUAGES)

    # ------------------------------------------------------------------
    # Private: script-based detection
    # ------------------------------------------------------------------

    def _detect_by_script(self, text: str) -> Optional[Dict[str, Any]]:
        """Detect language by character script patterns."""
        for lang, pattern in SCRIPT_PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                total_chars = sum(len(m) for m in matches)
                text_len = len(text.replace(" ", ""))
                confidence = min(total_chars / max(text_len, 1), 1.0)
                if confidence > 0.3:
                    return {
                        "language": lang,
                        "name": SUPPORTED_LANGUAGES.get(lang, "Unknown"),
                        "confidence": round(confidence, 2),
                        "dialect": None,
                        "method": "script",
                    }
        return None

    # ------------------------------------------------------------------
    # Private: word-frequency detection
    # ------------------------------------------------------------------

    def _detect_by_words(self, text: str) -> Dict[str, Any]:
        """Detect language by matching against word frequency lists."""
        words = set(re.findall(r"\b\w+\b", text))
        if not words:
            return {
                "language": self.default_language,
                "name": SUPPORTED_LANGUAGES.get(self.default_language, "Unknown"),
                "confidence": 0.0,
                "dialect": None,
                "method": "word_frequency",
            }

        scores: Dict[str, float] = {}
        for lang, markers in LANGUAGE_MARKERS.items():
            marker_set = set(markers)
            matches = words & marker_set
            if matches:
                scores[lang] = len(matches) / len(words)

        if not scores:
            return {
                "language": self.default_language,
                "name": SUPPORTED_LANGUAGES.get(self.default_language, "Unknown"),
                "confidence": 0.15,
                "dialect": None,
                "method": "word_frequency",
            }

        best_lang = max(scores, key=scores.get)  # type: ignore[arg-type]
        confidence = min(scores[best_lang] * 2, 1.0)  # Scale up

        return {
            "language": best_lang,
            "name": SUPPORTED_LANGUAGES.get(best_lang, "Unknown"),
            "confidence": round(confidence, 2),
            "dialect": None,
            "method": "word_frequency",
        }

    # ------------------------------------------------------------------
    # Private: dialect detection
    # ------------------------------------------------------------------

    def _detect_dialect(self, text: str, language: str) -> Optional[str]:
        """Attempt to detect dialect within a language."""
        dialects = DIALECT_MAP.get(language)
        if not dialects:
            return None

        # Simple heuristics for dialect detection
        if language == "es":
            if any(w in text for w in ["güey", "chido", "neta", "mano", "órale"]):
                return "Mexican Spanish"
            if any(w in text for w in ["tío", "vale", "mola", "guay"]):
                return "Spain Spanish"
            if any(w in text for w in ["che", "boludo", "pibe", "vos"]):
                return "Argentine Spanish"

        if language == "pt":
            if any(w in text for w in ["você", "legal", "beleza", "cara", "gente"]):
                return "Brazilian Portuguese"
            if any(w in text for w in ["fixe", "gajo", "pá"]):
                return "European Portuguese"

        if language == "fr":
            if any(w in text for w in ["icitte", "char", "blonde", "pantoute"]):
                return "Canadian French"

        return None
