"""Async API client for the Amperium cloud API."""
from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from typing import Any

import aiohttp

from .const import ACCEPT_LANGUAGE, API_KEY, BASE_URL, REQUEST_TIMEOUT, USER_AGENT
from .derived import consumer_price

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
        on_tokens: Callable[[str | None, str | None], None] | None = None,
    ) -> None:
        """Initialise the client with an aiohttp session and optional tokens.

        ``on_tokens`` is called with the new (access, refresh) pair right after
        every successful refresh, so the caller can store them immediately.
        """
        self._session = session
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._on_tokens = on_tokens

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
        headers = {
            "api-key": API_KEY,
            "Accept": "application/json",
            "Accept-Language": ACCEPT_LANGUAGE,
            "User-Agent": USER_AGENT,
        }
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
        """Refresh the access token.

        Returns True on success and False when Amperium says the token pair is
        not valid (HTTP 400/401/403): the user has to log in again. Any other
        failure (HTTP 5xx, 429, network) raises AmperiumError, because it says
        nothing about the tokens and must never look like a logout.

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
            if self._on_tokens is not None:
                self._on_tokens(self.access_token, self.refresh_token)
            return True
        if status in (400, 401, 403):
            return False
        raise AmperiumError(f"Token refresh failed (HTTP {status})")

    # ------------------------------------------------------------------ #
    # Data
    # ------------------------------------------------------------------ #
    async def _auth_get(self, path: str) -> tuple[int, Any]:
        """Authenticated GET, refreshing the token once on 401."""
        status, data = await self._request("GET", path, auth=True)
        if status == 401 and await self.refresh():
            status, data = await self._request("GET", path, auth=True)
        return status, data

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
        return await self._auth_get(path)

    async def async_get_sites(self) -> list[dict[str, Any]]:
        """Return the list of sites for this account."""
        status, data = await self._get_sites_raw()
        if status == 401:
            raise AmperiumAuthError("Access/refresh token no longer valid")
        if status != 200 or not isinstance(data, list):
            raise AmperiumError(f"GET /api/sites failed (HTTP {status})")
        return data

    async def async_get_prices(
        self, site_id: int, start: datetime.datetime, end: datetime.datetime
    ) -> list[dict[str, Any]]:
        """Return hourly prices for [start, end) as normalised buckets.

        GET /api/sites/{id}/prices returns one bucket per hour. Verified
        against the live API: an array of objects with startTime, endTime,
        spotPreliminary, spotOfficial (null until fixed), surcharge,
        salesTaxPercentage and updatedOn.
        """
        path = f"/api/sites/{site_id}/prices?from={_iso_z(start)}&to={_iso_z(end)}"
        status, data = await self._auth_get(path)
        if status == 401:
            raise AmperiumAuthError("Access/refresh token no longer valid")
        if status != 200 or not isinstance(data, list):
            raise AmperiumError(f"GET /api/sites/{{id}}/prices failed (HTTP {status})")
        return [_normalise_price(b) for b in data if isinstance(b, dict)]

    async def async_get_energy(
        self, site_id: int, start: datetime.datetime, end: datetime.datetime
    ) -> list[dict[str, Any]]:
        """Return hourly consumption for [start, end).

        resolution must be a single letter (H, D or M); words and numbers are
        rejected by the API. We always ask for H and aggregate ourselves in
        local time.
        """
        path = (
            f"/api/sites/{site_id}/consumption/energy"
            f"?from={_iso_z(start)}&to={_iso_z(end)}&resolution=H"
        )
        data = await self._get_list(path, "consumption/energy")
        return [
            {
                "start": _parse_dt(b.get("from")),
                "end": _parse_dt(b.get("to")),
                "import": _num(b.get("importedEnergy")),
                "export": _num(b.get("exportedEnergy")),
            }
            for b in data
            if isinstance(b, dict)
        ]

    async def async_get_charges(
        self, site_id: int, start: datetime.datetime, end: datetime.datetime
    ) -> dict[str, Any]:
        """Return charges for [start, end) (resolution=H).

        Response parts:
        - ``energy``: hourly energy buckets (gross energy, subsidy, Norgespris).
        - ``outer_total``: energy + grid rent after subsidy, excl. fixed fee.
        - ``grid``: ONE aggregate for the whole period (grid rent items,
          capacity charge, subsidy applied; ``total`` is after subsidy).
        - ``fixed_total``: the fixed monthly fee, which is outside /api/sites.
        - ``capacity_intervals``: the full capacity-charge tier table.
        """
        path = (
            f"/api/sites/{site_id}/consumption/charges"
            f"?from={_iso_z(start)}&to={_iso_z(end)}&resolution=H"
        )
        status, data = await self._auth_get(path)
        if status == 401:
            raise AmperiumAuthError("Access/refresh token no longer valid")
        if status != 200 or not isinstance(data, dict):
            raise AmperiumError(f"GET consumption/charges failed (HTTP {status})")
        fixed = data.get("fixedCharges")
        return {
            "energy": [
                {
                    "start": _parse_dt(b.get("from")),
                    "end": _parse_dt(b.get("to")),
                    # Gross energy cost incl. VAT, before any subsidy (kr).
                    # totalAmount carries the same number; spotCostPrice and
                    # surchargePrice are prices per kWh, not amounts.
                    "energy": _num(b.get("importedEnergyAmount")),
                    "tax": _num(b.get("salesTaxAmount")),
                    "norgespris": _num(b.get("importedCompensationAmountNorgespris")),
                }
                for b in data.get("energy") or []
                if isinstance(b, dict)
            ],
            "outer_total": _opt(data.get("totalAmount")),
            "grid": _parse_grid(data.get("gridRent")),
            "fixed_total": _opt(fixed.get("totalAmount")) if isinstance(fixed, dict) else None,
            "capacity_intervals": [
                {
                    "min": _opt(i.get("powerMin")),
                    "max": _opt(i.get("powerMax")),
                    "amount": _opt(i.get("amount")),
                }
                for i in data.get("capacityChargeIntervals") or []
                if isinstance(i, dict)
            ],
        }

    async def _get_list(self, path: str, label: str) -> list[Any]:
        """Authenticated GET that must return a JSON array."""
        status, data = await self._auth_get(path)
        if status == 401:
            raise AmperiumAuthError("Access/refresh token no longer valid")
        if status != 200 or not isinstance(data, list):
            raise AmperiumError(f"GET {label} failed (HTTP {status})")
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
            "spot_price_preliminary": price.get("spotPreliminary"),
            "surcharge": price.get("surcharge"),
            "vat_percent": price.get("salesTaxPercentage"),
            "han_online": site.get("hanPortMeterOnline"),
            "han_signal": site.get("hanPortMeterSignal"),
            "is_producing": site.get("isProducingEnergy"),
            "energy_export_month": usage.get("energyExportThisMonth"),
            "energy_export_today": usage.get("energyExportToday"),
            "updated": usage.get("energyUpdatedOn"),
        }


def _iso_z(value: datetime.datetime) -> str:
    """Format an aware datetime as ISO-8601 UTC with a trailing Z."""
    return value.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dt(value: Any) -> datetime.datetime | None:
    """Parse an ISO-8601 timestamp into an aware UTC datetime."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _opt(value: Any) -> float | None:
    """Return value as float, or None when missing/invalid."""
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _parse_grid(grid: Any) -> dict[str, Any] | None:
    """Pick out the grid-rent aggregate for a period (all amounts in kr)."""
    if not isinstance(grid, dict):
        return None
    interval = grid.get("capacityInterval")
    interval = interval if isinstance(interval, dict) else {}
    return {
        # After subsidy; equals amountGridRent in /api/sites.
        "total": _opt(grid.get("totalAmount")),
        # The straumstotte applied against the grid rent. Reported as a
        # positive amount in live data; use abs() when reading, never the sign.
        "compensation": _opt(grid.get("compensationAmount")),
        "sales_tax": _opt(grid.get("salesTaxAmount")),
        "capacity_avg_kw": _opt(grid.get("capacityChargeAveragePower")),
        "capacity_min_kw": _opt(interval.get("powerMin")),
        "capacity_max_kw": _opt(interval.get("powerMax")),
        "capacity_amount": _opt(interval.get("amount")),
        "energy_day_kwh": _opt(grid.get("importedEnergyDay")),
        "energy_night_kwh": _opt(grid.get("importedEnergyNight")),
        "energy_day": _opt(grid.get("energyChargeDayAmount")),
        "energy_night": _opt(grid.get("energyChargeNightAmount")),
        "electricity_fee": _opt(grid.get("electricityFeeAmount")),
        "enova_fee": _opt(grid.get("enovaFeeAmount")),
        "membership_discount": _opt(grid.get("membershipDiscountAmount")),
    }


def _num(value: Any) -> float:
    """Return value as float, treating missing/invalid as 0."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalise_price(bucket: dict[str, Any]) -> dict[str, Any]:
    """Reduce one hourly price bucket to the fields we expose.

    The official spot price is preferred; the preliminary price is used until
    the official one has been fixed.
    """
    official = bucket.get("spotOfficial")
    spot = official if official is not None else bucket.get("spotPreliminary")
    surcharge = bucket.get("surcharge")
    vat_percent = bucket.get("salesTaxPercentage")
    return {
        "start": bucket.get("startTime"),
        "end": bucket.get("endTime"),
        "spot": spot,
        "official": official is not None,
        "surcharge": surcharge,
        "vat_percent": vat_percent,
        # What the consumer pays per kWh: (spot + surcharge) incl. VAT.
        "consumer": consumer_price(spot, surcharge, vat_percent),
    }


def summarise_prices(buckets: list[dict[str, Any]]) -> dict[str, Any]:
    """Return min/max/average spot price for a list of normalised buckets."""
    priced = [b for b in buckets if isinstance(b.get("spot"), (int, float))]
    if not priced:
        return {}
    low = min(priced, key=lambda b: b["spot"])
    high = max(priced, key=lambda b: b["spot"])
    consumer = [b["consumer"] for b in priced if isinstance(b.get("consumer"), (int, float))]
    return {
        "price_min_today": low["spot"],
        "price_min_hour": low["start"],
        "price_min_consumer": low.get("consumer"),
        "price_max_today": high["spot"],
        "price_max_hour": high["start"],
        "price_max_consumer": high.get("consumer"),
        "price_avg_today": sum(b["spot"] for b in priced) / len(priced),
        "price_avg_consumer": sum(consumer) / len(consumer) if consumer else None,
    }
