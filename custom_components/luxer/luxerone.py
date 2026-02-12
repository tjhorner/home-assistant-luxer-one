"""Luxer One API client for the v2 API."""

from __future__ import annotations

import uuid
from typing import Any

import aiohttp


class LuxerOneAuthorizationError(Exception):
    """Raised when the API rejects the current token."""


class LuxerOneClient:
    """Client for the Luxer One v2 API."""

    BASE_URL = "https://resident-api.luxerone.com/resident_api/v2"

    def __init__(
        self,
        email: str,
        token: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the Luxer One API client."""
        self.email = email
        self.token = token

        if session is None:
            self.session = aiohttp.ClientSession()
        else:
            self.session = session

    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"LuxerOneApi {self.token}"
        return headers

    async def request(self, method: str, endpoint: str, **kwargs: Any) -> dict:
        """Perform an HTTP request and return the parsed JSON response."""
        url = f"{self.BASE_URL}{endpoint}"
        headers = self._auth_headers()

        async with self.session.request(
            method, url, headers=headers, **kwargs
        ) as response:
            json_data: dict = await response.json()

            if json_data.get("error") == "ApiAuthorizationRequired":
                msg = "Token rejected by Luxer One API - reauthentication required."
                raise LuxerOneAuthorizationError(msg)

            return json_data

    async def get(self, endpoint: str, params: dict | None = None) -> dict:
        """Perform a GET request."""
        return await self.request("GET", endpoint, params=params)

    async def post(self, endpoint: str, body: dict | None = None) -> dict:
        """Perform a POST request with a JSON body."""
        return await self.request("POST", endpoint, json=body)

    @staticmethod
    def generate_uuid() -> str:
        """Return a device UUID in the format expected by the API."""
        return str(uuid.uuid4()).upper()

    async def request_otp(self) -> bool:
        """Request an OTP code to be sent to the configured email."""
        resp = await self.post("/auth/loginUsingEmail", {"email": self.email})
        return resp.get("status") == "OK"

    async def verify_otp(self, otp: str, device_uuid: str) -> str:
        """Verify the OTP and return the long-lived API token."""
        resp = await self.post(
            "/auth/verifyOtpUsingEmail",
            {
                "email": self.email,
                "uuid": device_uuid,
                "otp": otp,
                "as": "token",
            },
        )
        token: str = resp["token"]
        self.token = token
        return token

    async def logout(self) -> None:
        """Revoke the current token."""
        if self.token:
            await self.post("/auth/logout", {"revoke": self.token})
            self.token = None

    async def user_info(self) -> dict:
        """Return user profile information (flat dict, no 'data' wrapper)."""
        return await self.get("/user/info")

    async def pending_packages(self) -> list[dict]:
        """Return the list of pending deliveries."""
        resp = await self.get("/deliveries/pendings")
        return resp.get("deliveries", [])

    async def locations(self) -> list[dict]:
        """Return the list of locker locations for this account."""
        resp = await self.get("/locations/list")
        return resp.get("locations", [])
