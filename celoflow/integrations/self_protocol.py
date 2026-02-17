"""Self Protocol API client for identity verification.

Provides privacy-preserving KYC verification through the Self Protocol,
handling document upload, verification flows, and attestation retrieval.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 30.0


class SelfProtocolClient:
    """HTTP client for the Self Protocol identity verification API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.self.id",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._is_configured = bool(api_key)
        logger.info(
            "SelfProtocolClient initialised (configured=%s, base_url=%s)",
            self._is_configured,
            self.base_url,
        )

    @property
    def is_configured(self) -> bool:
        return self._is_configured

    # ------------------------------------------------------------------
    # Public: verify_identity
    # ------------------------------------------------------------------

    async def verify_identity(
        self,
        user_id: str,
        level: str,
        documents: List[str],
    ) -> Dict[str, Any]:
        """Submit an identity verification request.

        Args:
            user_id: Unique user identifier
            level: KYC level (basic, standard, enhanced)
            documents: List of document types submitted

        Returns:
            Verification result with status and attestation hash
        """
        if not self._is_configured:
            return self._simulate_verification(user_id, level)

        payload = {
            "user_id": user_id,
            "verification_level": level,
            "documents": documents,
            "privacy_mode": "attestation_only",
        }

        response = await self._request("POST", "/v1/verify", json=payload)
        if response.get("error"):
            return {
                "verified": False,
                "status": "error",
                "message": response["error"],
            }

        return {
            "verified": response.get("verified", False),
            "status": response.get("status", "pending"),
            "attestation_hash": response.get("attestation_hash", ""),
            "verification_id": response.get("verification_id", ""),
            "message": response.get("message", ""),
        }

    # ------------------------------------------------------------------
    # Public: check_verification_status
    # ------------------------------------------------------------------

    async def check_verification_status(
        self, verification_id: str
    ) -> Dict[str, Any]:
        """Check the status of a pending verification.

        Args:
            verification_id: ID returned from verify_identity

        Returns:
            Current verification status
        """
        if not self._is_configured:
            return {
                "status": "verified",
                "message": "Simulated — verification complete",
            }

        response = await self._request(
            "GET", f"/v1/verify/{verification_id}"
        )
        return {
            "status": response.get("status", "unknown"),
            "verified": response.get("verified", False),
            "attestation_hash": response.get("attestation_hash", ""),
            "message": response.get("message", ""),
        }

    # ------------------------------------------------------------------
    # Public: upload_document
    # ------------------------------------------------------------------

    async def upload_document(
        self,
        user_id: str,
        document_type: str,
        document_data: bytes,
        content_type: str = "image/jpeg",
    ) -> Dict[str, Any]:
        """Upload a verification document.

        Args:
            user_id: User identifier
            document_type: Type of document (selfie, government_id, etc.)
            document_data: Raw document bytes
            content_type: MIME type of the document

        Returns:
            Upload result with document reference ID
        """
        if not self._is_configured:
            doc_hash = hashlib.sha256(document_data).hexdigest()[:16]
            return {
                "uploaded": True,
                "document_id": f"sim_doc_{doc_hash}",
                "message": "Simulated upload successful",
            }

        # In production, this would use multipart upload
        response = await self._request(
            "POST",
            "/v1/documents",
            json={
                "user_id": user_id,
                "document_type": document_type,
                "content_type": content_type,
                "size": len(document_data),
            },
        )
        return {
            "uploaded": response.get("success", False),
            "document_id": response.get("document_id", ""),
            "message": response.get("message", ""),
        }

    # ------------------------------------------------------------------
    # Public: get_attestation
    # ------------------------------------------------------------------

    async def get_attestation(
        self, user_id: str
    ) -> Dict[str, Any]:
        """Retrieve the privacy-preserving attestation for a user.

        Returns only verification status — no raw PII is exposed.

        Args:
            user_id: User identifier

        Returns:
            Attestation data (hash, level, expiry) without PII
        """
        if not self._is_configured:
            return {
                "has_attestation": True,
                "attestation_hash": hashlib.sha256(
                    f"attestation:{user_id}".encode()
                ).hexdigest(),
                "level": "basic",
                "expires_at": int(time.time()) + 86_400,
                "message": "Simulated attestation",
            }

        response = await self._request(
            "GET", f"/v1/attestations/{user_id}"
        )
        return {
            "has_attestation": response.get("has_attestation", False),
            "attestation_hash": response.get("attestation_hash", ""),
            "level": response.get("level", "none"),
            "expires_at": response.get("expires_at", 0),
        }

    # ------------------------------------------------------------------
    # Public: get_fee_estimate
    # ------------------------------------------------------------------

    def get_fee_estimate(self, level: str) -> Dict[str, Any]:
        """Get the fee for a KYC verification level.

        Args:
            level: KYC level

        Returns:
            Fee information in USDT
        """
        fees = {
            "basic": 0.0,
            "standard": 2.50,
            "enhanced": 10.00,
        }
        fee = fees.get(level)
        if fee is None:
            return {"error": f"Unknown level: {level}"}
        return {
            "level": level,
            "fee_usdt": fee,
            "currency": "USDT",
        }

    # ------------------------------------------------------------------
    # Private: HTTP request with retry
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request with retry logic."""
        url = f"{self.base_url}{path}"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=REQUEST_TIMEOUT_SECONDS
                ) as client:
                    response = await client.request(
                        method, url, headers=headers, json=json
                    )
                    if response.status_code == 200:
                        return response.json()
                    if response.status_code == 429:
                        # Rate limited — wait and retry
                        wait = RETRY_DELAY_SECONDS * attempt
                        logger.warning(
                            "Self Protocol rate limited, retrying in %.1fs (attempt %d/%d)",
                            wait, attempt, MAX_RETRIES,
                        )
                        import asyncio
                        await asyncio.sleep(wait)
                        continue
                    # Non-retryable error
                    return {
                        "error": f"HTTP {response.status_code}: {response.text[:200]}"
                    }
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "Self Protocol request timeout (attempt %d/%d): %s",
                    attempt, MAX_RETRIES, e,
                )
            except Exception as e:
                last_error = e
                logger.error(
                    "Self Protocol request error (attempt %d/%d): %s",
                    attempt, MAX_RETRIES, e,
                )
            if attempt < MAX_RETRIES:
                import asyncio
                await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)

        return {"error": f"All {MAX_RETRIES} attempts failed: {last_error}"}

    # ------------------------------------------------------------------
    # Private: simulation for development
    # ------------------------------------------------------------------

    def _simulate_verification(
        self, user_id: str, level: str
    ) -> Dict[str, Any]:
        """Return a simulated verification result for development."""
        logger.info(
            "SelfProtocol (simulated) verify user=%s level=%s", user_id, level
        )
        attestation = hashlib.sha256(
            f"{user_id}:{level}:{int(time.time())}".encode()
        ).hexdigest()
        return {
            "verified": True,
            "status": "verified",
            "attestation_hash": attestation,
            "verification_id": f"sim_{user_id}_{level}",
            "message": "Simulated verification successful (no API key configured)",
        }
