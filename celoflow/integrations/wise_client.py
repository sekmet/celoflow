"""Wise Comparison API client for real-time fee data.

Fetches live fee comparisons from the Wise API to compare CeloFlow
fees against traditional remittance providers with accurate, real-time data.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.5
REQUEST_TIMEOUT_SECONDS = 15.0

# Rate limiting
RATE_LIMIT_REQUESTS_PER_MINUTE = 30
RATE_LIMIT_WINDOW_SECONDS = 60

# Cache TTL for real-time data (5 minutes)
REALTIME_CACHE_TTL = 300


class WiseClient:
    """HTTP client for the Wise Comparison API (v4).

    Supports both sandbox and production environments.
    Implements rate limiting, retry logic, caching, and graceful fallback.
    """

    PRODUCTION_URL = "https://api.wise.com/v4"
    SANDBOX_URL = "https://api.wise-sandbox.com/v4"

    # Currency code mapping: country name -> ISO currency code
    COUNTRY_CURRENCY_MAP: Dict[str, str] = {
        "Philippines": "PHP",
        "Mexico": "MXN",
        "Nigeria": "NGN",
        "Kenya": "KES",
        "India": "INR",
        "Colombia": "COP",
        "Brazil": "BRL",
        "United Kingdom": "GBP",
        "Germany": "EUR",
        "France": "EUR",
        "Japan": "JPY",
        "Australia": "AUD",
        "Canada": "CAD",
    }

    # Source currency mapping
    SOURCE_CURRENCY_MAP: Dict[str, str] = {
        "USD": "USD",
        "cUSD": "USD",
        "USDm": "USD",
        "USDC": "USD",
        "EUR": "EUR",
        "cEUR": "EUR",
        "GBP": "GBP",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        sandbox_url: Optional[str] = None,
        use_sandbox: bool = True,
    ) -> None:
        self.api_key = api_key
        self._is_configured = bool(api_key)
        self.use_sandbox = use_sandbox

        if base_url:
            self._production_url = base_url.rstrip("/")
        else:
            self._production_url = self.PRODUCTION_URL

        if sandbox_url:
            self._sandbox_url = sandbox_url.rstrip("/")
        else:
            self._sandbox_url = self.SANDBOX_URL

        self._cache: Dict[str, Dict[str, Any]] = {}
        self._rate_limit_timestamps: List[float] = []

        logger.info(
            "WiseClient initialised (configured=%s, sandbox=%s)",
            self._is_configured,
            self.use_sandbox,
        )

    @property
    def is_configured(self) -> bool:
        return self._is_configured

    @property
    def base_url(self) -> str:
        return self._sandbox_url if self.use_sandbox else self._production_url

    # ------------------------------------------------------------------
    # Public: get_comparison
    # ------------------------------------------------------------------

    async def get_comparison(
        self,
        source_currency: str,
        target_currency: str,
        send_amount: Optional[float] = None,
        recipient_gets_amount: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Fetch real-time fee comparison data from Wise.

        Args:
            source_currency: ISO currency code (e.g. USD, EUR)
            target_currency: ISO currency code (e.g. PHP, MXN)
            send_amount: Amount to send (mutually exclusive with recipient_gets_amount)
            recipient_gets_amount: Amount recipient should receive

        Returns:
            Parsed comparison data with provider quotes, or error dict
        """
        if not self._is_configured:
            return self._simulate_comparison(
                source_currency, target_currency, send_amount or 100.0
            )

        # Validate inputs
        if send_amount is None and recipient_gets_amount is None:
            return {"error": "Either send_amount or recipient_gets_amount is required"}

        # Check cache
        cache_key = self._cache_key(
            source_currency, target_currency, send_amount, recipient_gets_amount
        )
        cached = self._get_cached(cache_key)
        if cached:
            cached["data_source"] = "cache"
            return cached

        # Check rate limit
        if not self._check_rate_limit():
            logger.warning("Wise API rate limit reached, returning cached/fallback data")
            return {
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please try again shortly.",
            }

        # Build query params
        params: Dict[str, Any] = {
            "sourceCurrency": source_currency.upper(),
            "targetCurrency": target_currency.upper(),
        }
        if send_amount is not None:
            params["sendAmount"] = send_amount
        else:
            params["recipientGetsAmount"] = recipient_gets_amount

        # Make API call
        response = await self._request("GET", "/comparisons", params=params)

        if response.get("error"):
            return response

        # Parse and cache
        parsed = self._parse_comparison_response(
            response, source_currency, target_currency, send_amount
        )
        parsed["data_source"] = "realtime"
        parsed["fetched_at"] = time.time()
        self._set_cached(cache_key, parsed)

        return parsed

    # ------------------------------------------------------------------
    # Public: get_comparison_for_country
    # ------------------------------------------------------------------

    async def get_comparison_for_country(
        self,
        amount: float,
        from_currency: str,
        destination_country: str,
    ) -> Dict[str, Any]:
        """Convenience method: get comparison using country name.

        Maps from_currency (which may be a crypto symbol) and
        destination_country to ISO currency codes for the Wise API.

        Args:
            amount: Transfer amount
            from_currency: Source currency (USD, cUSD, EUR, etc.)
            destination_country: Destination country name

        Returns:
            Comparison data or error dict
        """
        source_iso = self.SOURCE_CURRENCY_MAP.get(from_currency, from_currency.upper())
        target_iso = self.COUNTRY_CURRENCY_MAP.get(destination_country)

        if not target_iso:
            return {
                "error": f"Unsupported destination country: {destination_country}",
                "supported_countries": list(self.COUNTRY_CURRENCY_MAP.keys()),
            }

        return await self.get_comparison(
            source_currency=source_iso,
            target_currency=target_iso,
            send_amount=amount,
        )

    # ------------------------------------------------------------------
    # Public: get_supported_corridors
    # ------------------------------------------------------------------

    def get_supported_corridors(self) -> Dict[str, str]:
        """Return the mapping of supported countries to currency codes."""
        return dict(self.COUNTRY_CURRENCY_MAP)

    # ------------------------------------------------------------------
    # Private: parse Wise API response
    # ------------------------------------------------------------------

    def _parse_comparison_response(
        self,
        raw: Any,
        source_currency: str,
        target_currency: str,
        send_amount: Optional[float],
    ) -> Dict[str, Any]:
        """Parse the Wise comparison API response into a normalized format.

        The Wise API returns an array of provider quotes. Each quote contains:
        - providerName, logo, fee, rate, receivedAmount, speed, etc.
        """
        providers: List[Dict[str, Any]] = []

        # Handle both list and dict responses
        quotes = raw if isinstance(raw, list) else raw.get("providers", raw.get("quotes", []))

        if not isinstance(quotes, list):
            quotes = []

        for quote in quotes:
            try:
                provider = self._parse_provider_quote(quote, send_amount)
                if provider:
                    providers.append(provider)
            except Exception as e:
                logger.warning("Failed to parse Wise provider quote: %s", e)
                continue

        # Sort by total cost (fee + fx markup)
        providers.sort(key=lambda p: p.get("total_cost", float("inf")))

        # Assign rankings
        for i, p in enumerate(providers):
            p["rank"] = i + 1

        return {
            "source_currency": source_currency.upper(),
            "target_currency": target_currency.upper(),
            "send_amount": send_amount,
            "providers": providers,
            "provider_count": len(providers),
            "cheapest": providers[0] if providers else None,
            "most_expensive": providers[-1] if providers else None,
        }

    def _parse_provider_quote(
        self,
        quote: Dict[str, Any],
        send_amount: Optional[float],
    ) -> Optional[Dict[str, Any]]:
        """Parse a single provider quote from the Wise response."""
        name = quote.get("providerName") or quote.get("name") or quote.get("provider", "")
        if not name:
            return None

        fee = float(quote.get("fee", 0) or 0)
        rate = float(quote.get("rate", 0) or quote.get("exchangeRate", 0) or 0)
        received = float(quote.get("receivedAmount", 0) or quote.get("targetAmount", 0) or 0)

        # Calculate FX markup if mid-market rate is available
        mid_rate = float(quote.get("midMarketRate", 0) or 0)
        fx_markup = 0.0
        fx_markup_pct = 0.0
        if mid_rate > 0 and rate > 0:
            fx_markup_pct = abs(mid_rate - rate) / mid_rate
            if send_amount:
                fx_markup = send_amount * fx_markup_pct

        total_cost = fee + fx_markup

        # Parse delivery speed
        speed_raw = quote.get("speed") or quote.get("deliveryEstimate") or ""
        speed = self._normalize_speed(speed_raw)

        return {
            "name": name,
            "fee": round(fee, 2),
            "exchange_rate": round(rate, 6) if rate else 0,
            "mid_market_rate": round(mid_rate, 6) if mid_rate else 0,
            "fx_markup": round(fx_markup, 2),
            "fx_markup_pct": round(fx_markup_pct * 100, 3),
            "total_cost": round(total_cost, 2),
            "recipient_receives": round(received, 2),
            "speed": speed,
            "speed_raw": str(speed_raw),
            "logo": quote.get("logo", ""),
            "confidence": "high",
        }

    def _normalize_speed(self, speed_raw: Any) -> str:
        """Normalize delivery speed to a human-readable string."""
        if not speed_raw:
            return "Unknown"

        speed_str = str(speed_raw).lower()

        if "instant" in speed_str or "second" in speed_str:
            return "Instant"
        if "minute" in speed_str:
            return "Minutes"
        if "hour" in speed_str:
            return "Hours"
        if "1" in speed_str and "day" in speed_str:
            return "1 business day"
        if "2" in speed_str and "day" in speed_str:
            return "1-2 business days"
        if "day" in speed_str:
            return "1-3 business days"

        return str(speed_raw)

    # ------------------------------------------------------------------
    # Private: HTTP request with retry and rate limiting
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make an HTTP request to the Wise API with retry logic."""
        url = f"{self.base_url}{path}"
        headers: Dict[str, str] = {
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self._record_rate_limit()

        last_error: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=REQUEST_TIMEOUT_SECONDS
                ) as client:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        params=params,
                        json=json_body,
                    )

                    if response.status_code == 200:
                        return response.json()

                    if response.status_code == 429:
                        wait = RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                        logger.warning(
                            "Wise API rate limited (429), retrying in %.1fs (attempt %d/%d)",
                            wait, attempt, MAX_RETRIES,
                        )
                        await asyncio.sleep(wait)
                        continue

                    if response.status_code in (500, 502, 503, 504):
                        wait = RETRY_DELAY_SECONDS * attempt
                        logger.warning(
                            "Wise API server error %d, retrying in %.1fs (attempt %d/%d)",
                            response.status_code, wait, attempt, MAX_RETRIES,
                        )
                        await asyncio.sleep(wait)
                        continue

                    # Non-retryable error
                    return {
                        "error": f"HTTP {response.status_code}",
                        "message": response.text[:300],
                    }

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "Wise API timeout (attempt %d/%d): %s",
                    attempt, MAX_RETRIES, e,
                )
            except Exception as e:
                last_error = e
                logger.error(
                    "Wise API request error (attempt %d/%d): %s",
                    attempt, MAX_RETRIES, e,
                )

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)

        return {"error": f"All {MAX_RETRIES} attempts failed: {last_error}"}

    # ------------------------------------------------------------------
    # Private: rate limiting
    # ------------------------------------------------------------------

    def _check_rate_limit(self) -> bool:
        """Check if we're within the rate limit window."""
        now = time.time()
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        self._rate_limit_timestamps = [
            ts for ts in self._rate_limit_timestamps if ts > cutoff
        ]
        return len(self._rate_limit_timestamps) < RATE_LIMIT_REQUESTS_PER_MINUTE

    def _record_rate_limit(self) -> None:
        """Record a request timestamp for rate limiting."""
        self._rate_limit_timestamps.append(time.time())

    # ------------------------------------------------------------------
    # Private: caching
    # ------------------------------------------------------------------

    def _cache_key(
        self,
        source: str,
        target: str,
        send_amount: Optional[float],
        recipient_amount: Optional[float],
    ) -> str:
        return f"wise:{source}:{target}:{send_amount}:{recipient_amount}"

    def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        cached = self._cache.get(key)
        if cached and cached["expires_at"] > time.time():
            return cached["data"].copy()
        return None

    def _set_cached(self, key: str, data: Dict[str, Any]) -> None:
        self._cache[key] = {
            "data": data,
            "expires_at": time.time() + REALTIME_CACHE_TTL,
        }

    def clear_cache(self) -> None:
        """Clear all cached comparison data."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Private: simulation for development (no API key)
    # ------------------------------------------------------------------

    def _simulate_comparison(
        self,
        source_currency: str,
        target_currency: str,
        amount: float,
    ) -> Dict[str, Any]:
        """Return simulated comparison data for development without API key."""
        logger.info(
            "WiseClient (simulated) comparison %s->%s amount=%.2f",
            source_currency, target_currency, amount,
        )

        # Simulated mid-market rates
        sim_rates: Dict[str, float] = {
            "PHP": 56.20,
            "MXN": 17.15,
            "NGN": 1550.0,
            "KES": 153.50,
            "INR": 83.40,
            "COP": 3950.0,
            "BRL": 4.95,
            "EUR": 0.92,
            "GBP": 0.79,
        }
        mid_rate = sim_rates.get(target_currency.upper(), 1.0)

        providers = [
            {
                "name": "Wise",
                "fee": round(amount * 0.0065, 2),
                "exchange_rate": round(mid_rate * 0.996, 4),
                "mid_market_rate": mid_rate,
                "fx_markup": round(amount * 0.004, 2),
                "fx_markup_pct": 0.4,
                "total_cost": round(amount * 0.0065 + amount * 0.004, 2),
                "recipient_receives": round((amount - amount * 0.0065) * mid_rate * 0.996, 2),
                "speed": "1-2 business days",
                "speed_raw": "1-2 business days",
                "logo": "",
                "confidence": "simulated",
                "rank": 1,
            },
            {
                "name": "Western Union",
                "fee": round(max(amount * 0.05, 4.99), 2),
                "exchange_rate": round(mid_rate * 0.975, 4),
                "mid_market_rate": mid_rate,
                "fx_markup": round(amount * 0.025, 2),
                "fx_markup_pct": 2.5,
                "total_cost": round(max(amount * 0.05, 4.99) + amount * 0.025, 2),
                "recipient_receives": round((amount - max(amount * 0.05, 4.99)) * mid_rate * 0.975, 2),
                "speed": "1-3 business days",
                "speed_raw": "1-3 business days",
                "logo": "",
                "confidence": "simulated",
                "rank": 2,
            },
            {
                "name": "Remitly",
                "fee": round(max(amount * 0.03, 2.99), 2),
                "exchange_rate": round(mid_rate * 0.985, 4),
                "mid_market_rate": mid_rate,
                "fx_markup": round(amount * 0.015, 2),
                "fx_markup_pct": 1.5,
                "total_cost": round(max(amount * 0.03, 2.99) + amount * 0.015, 2),
                "recipient_receives": round((amount - max(amount * 0.03, 2.99)) * mid_rate * 0.985, 2),
                "speed": "Minutes to 3 days",
                "speed_raw": "Minutes to 3 days",
                "logo": "",
                "confidence": "simulated",
                "rank": 3,
            },
            {
                "name": "MoneyGram",
                "fee": round(max(amount * 0.045, 3.99), 2),
                "exchange_rate": round(mid_rate * 0.98, 4),
                "mid_market_rate": mid_rate,
                "fx_markup": round(amount * 0.02, 2),
                "fx_markup_pct": 2.0,
                "total_cost": round(max(amount * 0.045, 3.99) + amount * 0.02, 2),
                "recipient_receives": round((amount - max(amount * 0.045, 3.99)) * mid_rate * 0.98, 2),
                "speed": "1-3 business days",
                "speed_raw": "1-3 business days",
                "logo": "",
                "confidence": "simulated",
                "rank": 4,
            },
        ]

        # Sort by total cost
        providers.sort(key=lambda p: p["total_cost"])
        for i, p in enumerate(providers):
            p["rank"] = i + 1

        return {
            "source_currency": source_currency.upper(),
            "target_currency": target_currency.upper(),
            "send_amount": amount,
            "providers": providers,
            "provider_count": len(providers),
            "cheapest": providers[0],
            "most_expensive": providers[-1],
            "data_source": "simulated",
            "fetched_at": time.time(),
        }
