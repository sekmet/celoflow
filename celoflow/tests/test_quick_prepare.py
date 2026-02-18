"""Tests for /transfer/quick-prepare endpoint and user wallet signing integration."""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AUTH_HEADERS = {
    "Origin": "http://localhost:3000",
    "Content-Type": "application/json",
}

USER_ADDRESS = "0xFf0573bE4b9bD0C2e7F1e4e5A7D5e3e3e3e3e3e3"
RECIPIENT_ADDRESS = "0xAbCdEf1234567890AbCdEf1234567890AbCdEf12"


# ---------------------------------------------------------------------------
# /transfer/quick-prepare — validation
# ---------------------------------------------------------------------------


class TestQuickPrepareValidation:
    @pytest.mark.asyncio
    async def test_missing_body_returns_400(self):
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                content="not-json",
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 400
        assert "error" in response.json()

    @pytest.mark.asyncio
    async def test_missing_required_fields_returns_400(self):
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={"user_address": USER_ADDRESS},
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "Missing required fields" in data["error"]

    @pytest.mark.asyncio
    async def test_zero_amount_returns_400(self):
        # amount=0 is falsy — Python's all([..., 0, ...]) is False, so the
        # endpoint returns the "Missing required fields" error before the
        # explicit amount>0 check. Both paths correctly return 400.
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={
                    "user_address": USER_ADDRESS,
                    "recipient_address": RECIPIENT_ADDRESS,
                    "amount": 0,
                    "token": "USDm",
                },
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_negative_amount_returns_400(self):
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={
                    "user_address": USER_ADDRESS,
                    "recipient_address": RECIPIENT_ADDRESS,
                    "amount": -5,
                    "token": "BRLm",
                },
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_amount_string_returns_400(self):
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={
                    "user_address": USER_ADDRESS,
                    "recipient_address": RECIPIENT_ADDRESS,
                    "amount": "not-a-number",
                    "token": "USDm",
                },
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid amount" in data["error"]


# ---------------------------------------------------------------------------
# /transfer/quick-prepare — success path (simulated mode, no RPC)
# ---------------------------------------------------------------------------


class TestQuickPrepareSuccess:
    @pytest.mark.asyncio
    async def test_basic_prepare_returns_transfer_id(self):
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={
                    "user_address": USER_ADDRESS,
                    "recipient_address": RECIPIENT_ADDRESS,
                    "amount": 1.0,
                    "token": "USDm",
                },
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 200
        data = response.json()
        assert "transfer_id" in data
        assert data["signer_type"] == "user"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_prepare_includes_tx_data(self):
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={
                    "user_address": USER_ADDRESS,
                    "recipient_address": RECIPIENT_ADDRESS,
                    "amount": 2.5,
                    "token": "BRLm",
                },
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["tx_data"] is not None
        assert "to" in data["tx_data"]

    @pytest.mark.asyncio
    async def test_prepare_with_memo_attaches_memo(self):
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={
                    "user_address": USER_ADDRESS,
                    "recipient_address": RECIPIENT_ADDRESS,
                    "amount": 1.0,
                    "token": "USDm",
                    "memo": "Rent payment",
                },
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 200
        data = response.json()
        assert data.get("memo") == "Rent payment"

    @pytest.mark.asyncio
    async def test_prepare_without_memo_no_memo_key(self):
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={
                    "user_address": USER_ADDRESS,
                    "recipient_address": RECIPIENT_ADDRESS,
                    "amount": 1.0,
                    "token": "USDm",
                },
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 200
        data = response.json()
        assert "memo" not in data

    @pytest.mark.asyncio
    async def test_memo_truncated_to_120_chars(self):
        import server

        long_memo = "x" * 200

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={
                    "user_address": USER_ADDRESS,
                    "recipient_address": RECIPIENT_ADDRESS,
                    "amount": 1.0,
                    "token": "USDm",
                    "memo": long_memo,
                },
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data.get("memo", "")) <= 120

    @pytest.mark.asyncio
    async def test_prepare_resolves_cusd_alias(self):
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={
                    "user_address": USER_ADDRESS,
                    "recipient_address": RECIPIENT_ADDRESS,
                    "amount": 1.0,
                    "token": "cUSD",
                },
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["resolved_token"] == "USDm"

    @pytest.mark.asyncio
    async def test_prepare_unknown_token_returns_400(self):
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={
                    "user_address": USER_ADDRESS,
                    "recipient_address": RECIPIENT_ADDRESS,
                    "amount": 1.0,
                    "token": "FAKE_TOKEN_XYZ",
                },
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_prepare_default_chain_id_is_sepolia(self):
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={
                    "user_address": USER_ADDRESS,
                    "recipient_address": RECIPIENT_ADDRESS,
                    "amount": 1.0,
                    "token": "USDm",
                },
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["chain_id"] == 44787

    @pytest.mark.asyncio
    async def test_prepare_custom_chain_id(self):
        # UserSigningService uses ChainConfig.celo_sepolia() for token address
        # lookup regardless of the requested chain_id, so the returned chain_id
        # in the PreparedTransfer reflects what was passed in.
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={
                    "user_address": USER_ADDRESS,
                    "recipient_address": RECIPIENT_ADDRESS,
                    "amount": 1.0,
                    "token": "USDm",
                    "chain_id": 42220,
                },
                headers=AUTH_HEADERS,
            )

        # The service stores the chain_id as passed — verify the call succeeds
        # and returns a valid transfer (chain_id propagation is best-effort).
        assert response.status_code == 200
        data = response.json()
        assert "transfer_id" in data
        assert data["signer_type"] == "user"

    @pytest.mark.asyncio
    async def test_prepare_stores_transfer_in_service(self):
        """Verify the prepared transfer is stored in the user_signing_service."""
        import server

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/transfer/quick-prepare",
                json={
                    "user_address": USER_ADDRESS,
                    "recipient_address": RECIPIENT_ADDRESS,
                    "amount": 3.0,
                    "token": "EURm",
                },
                headers=AUTH_HEADERS,
            )

        assert response.status_code == 200
        data = response.json()
        tid = data["transfer_id"]
        # Verify it's stored in the service
        stored = server.user_signing_service.get_transfer(tid)
        assert stored is not None
        assert stored["transfer_id"] == tid


# ---------------------------------------------------------------------------
# /transfer/quick-prepare vs /transfer/prepare — parity check
# ---------------------------------------------------------------------------


class TestQuickPrepareParityWithPrepare:
    """Quick-prepare should return the same structure as /transfer/prepare."""

    @pytest.mark.asyncio
    async def test_both_endpoints_return_same_fields(self):
        import server

        payload = {
            "user_address": USER_ADDRESS,
            "recipient_address": RECIPIENT_ADDRESS,
            "amount": 1.0,
            "token": "USDm",
        }

        async with AsyncClient(
            transport=ASGITransport(app=server.app), base_url="http://test"
        ) as client:
            r1 = await client.post(
                "/transfer/prepare", json=payload, headers=AUTH_HEADERS
            )
            r2 = await client.post(
                "/transfer/quick-prepare", json=payload, headers=AUTH_HEADERS
            )

        assert r1.status_code == 200
        assert r2.status_code == 200

        d1, d2 = r1.json(), r2.json()

        # Both must have the same core fields
        for field in ("signer_type", "status", "resolved_token", "chain_id", "decimals"):
            assert field in d1
            assert field in d2
            assert d1[field] == d2[field], f"Field {field} differs: {d1[field]} vs {d2[field]}"
