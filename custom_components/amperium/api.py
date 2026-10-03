"""Async API client for the Amperium cloud API."""
from __future__ import annotations

import datetime
import logging
from typing import Any

import aiohttp

from .const import API_KEY, BASE_URL, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class AmperiumError(Exception):
    """Generic Amperium API error."""


class AmperiumAuthError(AmperiumError):
    """Authentication failed / token no longer valid."""


class AmperiumRateLimitError(AmperiumError):
    """Too many OTP codes requested today (Amperium daily limit)."""


class AmperiumClient:
    """Minimal async client for api.amperium.cloud.

    Auth is passwordless OTP. After the one-time OTP login we keep an
    access token (short-lived) and a refresh token. The refresh endpoint
    only accepts an *expired* access token, so we refresh lazily: on a 401
    we refresh once and retry the request.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        """Initialise the client with an aiohttp session and optional tokens."""
        self._session = session
        self.access_token = access_token
        self.refresh_token = refresh_token

    # ------------------------------------------------------------------ #
    # Low-level request helper
    # ------------------------------------------------------------------ #
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        auth: bool = False,
    ) -> tuple[int, Any]:
        """Perform a single HTTP request. Returns (status, parsed_json|None)."""
        headers = {"api-key": API_KEY, "Accept": "application/json"}
        if auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        try:
            async with self._session.request(
                method, f"{BASE_URL}{path}", json=json, headers=headers, timeout=timeout
            ) as resp:
                text = await resp.text()
                data: Any = None
                if text.strip():
                    try:
                        data = await resp.json(content_type=None)
                    except (aiohttp.ContentTypeError, ValueError):
                        data = None
                return resp.status, data
        except aiohttp.ClientError as err:
            raise AmperiumError(f"Network error: {err}") from err

    # ------------------------------------------------------------------ #
    # Authentication
    # ------------------------------------------------------------------ #
    async def request_otp(self, phone: str) -> None:
        """Ask Amperium to send a one-time code by SMS to this phone number."""
        status, data = await self._request(
            "POST", "/api/accounts/login/request-otp", json={"phoneNumber": phone}
        )
        if status in (200, 202, 204):
            return
        # Surface the server's own message where we can.
        detail = ""
        error_code = None
        if isinstance(data, dict):
            detail = data.get("title") or data.get("detail") or ""
            error_code = data.get("errorCode")
        if error_code == 100104 or (
            "too many" in detail.lower() and "one time password" in detail.lower()
        ):
            raise AmperiumRateLimitError(detail or "Too many OTP codes requested today")
        raise AmperiumError(detail or f"request-otp failed (HTTP {status})")

    async def login_otp(self, phone: str, code: str) -> dict[str, Any]:
        """Exchange the OTP code for access + refresh tokens."""
        status, data = await self._request(
            "POST",
            "/api/accounts/login/otp",
            json={"phoneNumber": phone, "otp": code},
        )
        if status != 200 or not data or not data.get("accessToken"):
            raise AmperiumAuthError(f"OTP login failed (HTTP {status})")
        self.access_token = data["accessToken"]
        self.refresh_token = data.get("refreshToken")
        return data

    async def refresh(self) -> bool:
        """Refresh the access token. Returns True on success.

        Only works once the current access token has expired, which is
        exactly the 401 case we call it from.
        """
        if not self.refresh_token:
            return False
        status, data = await self._request(
            "POST",
            "/api/accounts/login/refresh-token",
            json={
                "accessToken": self.access_token,
                "refreshToken": self.refresh_token,
            },
        )
        if status == 200 and data and data.get("accessToken"):
            self.access_token = data["accessToken"]
            self.refresh_token = data.get("refreshToken", self.refresh_token)
            return True
        return False

    # ------------------------------------------------------------------ #
    # Data
    # ------------------------------------------------------------------ #
    async def _get_sites_raw(self) -> tuple[int, Any]:
        """GET /api/sites for the current month, refreshing the token on 401."""
        now = datetime.datetime.now(datetime.timezone.utc)
        frm = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        path = (
            "/api/sites?charges_from=%s&charges_to=%s"
            % (
                frm.strftime("%Y-%m-%dT%H:%M:%SZ"),
                now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        )
        status, data = await self._request("GET", path, auth=True)
        if status == 401:
            if await self.refresh():
                status, data = await self._request("GET", path, auth=True)
        return status, data

    async def async_get_sites(self) -> list[dict[str, Any]]:
        """Return the list of sites for this account."""
        status, data = await self._get_sites_raw()
        if status == 401:
            raise AmperiumAuthError("Access/refresh token no longer valid")
        if status != 200 or not isinstance(data, list):
            raise AmperiumError(f"GET /api/sites failed (HTTP {status})")
        return data

    async def async_fetch(self, site_id: int) -> dict[str, Any]:
        """Fetch and normalise the current-month data for one site."""
        sites = await self.async_get_sites()
        site = next((s for s in sites if s.get("siteId") == site_id), None)
        if site is None:
            if not sites:
                raise AmperiumError("No sites returned for this account")
            site = sites[0]

        usage = site.get("usageForCurrentMonth") or {}
        charges = site.get("chargesForCurrentMonth") or {}
        price = site.get("currentEnergyPrice") or {}

        return {
            "site_id": site.get("siteId"),
            "site_name": site.get("siteName"),
            "energy_month": usage.get("energyImportThisMonth"),
            "energy_today": usage.get("energyImportToday"),
            "power_now": usage.get("currentActivePowerImport"),
            "cost_total": charges.get("totalAmount"),
            "cost_energy": charges.get("amountEnergy"),
            "cost_grid_rent": charges.get("amountGridRent"),
            "spot_price": price.get("spotOfficial"),
            "surcharge": price.get("surcharge"),
            "vat_percent": price.get("salesTaxPercentage"),
            "han_online": site.get("hanPortMeterOnline"),
            "updated": usage.get("energyUpdatedOn"),
        }
