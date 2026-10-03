"""DataUpdateCoordinator for Amperium."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AmperiumAuthError, AmperiumClient, AmperiumError, summarise_prices
from .const import (
    CONF_ACCESS_EXPIRES,
    CONF_ACCESS_TOKEN,
    CONF_DAY_END,
    CONF_DAY_START,
    CONF_REFRESH_EXPIRES,
    CONF_REFRESH_TOKEN,
    CONF_SCHEME,
    CONF_SITE_ID,
    DEFAULT_DAY_END,
    DEFAULT_DAY_START,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EXTENDED_SCAN_INTERVAL,
    ISSUE_LOGIN_EXPIRING,
    REAUTH_WARN_DAYS,
)
from .derived import (
    capacity_peaks,
    days_until,
    local_month_bounds,
    summarise_charges,
    summarise_energy,
    summarise_grid,
)
from .statistics import async_import_statistics

_LOGGER = logging.getLogger(__name__)


class AmperiumCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the Amperium API and persists refreshed tokens to the entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry = entry
        self._site_id = entry.data[CONF_SITE_ID]
        self._extended: dict[str, Any] = {}
        self._extended_at: datetime | None = None
        # Used to tell a real options change from a token-only entry update.
        self.options_snapshot = dict(entry.options)
        session = async_get_clientsession(hass)
        self.client = AmperiumClient(
            session,
            access_token=entry.data.get(CONF_ACCESS_TOKEN),
            refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
            on_tokens=self._persist_tokens,
            access_expires_at=entry.data.get(CONF_ACCESS_EXPIRES),
            refresh_expires_at=entry.data.get(CONF_REFRESH_EXPIRES),
        )
        self._expiry_warned = False

    def _persist_tokens(self, tokens: dict[str, str | None]) -> None:
        """Store refreshed tokens (and their expiry) in the config entry at once.

        Done right when the refresh succeeds (not at the end of the update), so
        a restart or an error later in the update can never leave us holding an
        old token pair if Amperium rotates the refresh token.
        """
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={
                **self.entry.data,
                CONF_ACCESS_TOKEN: tokens["access_token"],
                CONF_REFRESH_TOKEN: tokens["refresh_token"],
                CONF_ACCESS_EXPIRES: tokens["access_expires_at"],
                CONF_REFRESH_EXPIRES: tokens["refresh_expires_at"],
            },
        )

    def _check_login_expiry(self) -> None:
        """Warn well before the refresh token expires and ask for a new login.

        Starts the re-login flow once the refresh token has less than
        REAUTH_WARN_DAYS left, and removes the warning after a fresh login.
        """
        remaining = days_until(self.client.refresh_expires_at, dt_util.utcnow())
        issue_id = f"{ISSUE_LOGIN_EXPIRING}_{self.entry.entry_id}"
        if remaining is None or remaining >= REAUTH_WARN_DAYS:
            self._expiry_warned = False
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_LOGIN_EXPIRING,
            translation_placeholders={"days": str(max(0, int(remaining)))},
        )
        if not self._expiry_warned:
            self._expiry_warned = True
            self.entry.async_start_reauth(self.hass)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data. Refreshed tokens are stored by ``_persist_tokens``."""
        # The month starts at local midnight (not 00:00 UTC), like the hourly data.
        _, month_start, _ = local_month_bounds(
            dt_util.utcnow().astimezone(dt_util.DEFAULT_TIME_ZONE)
        )
        try:
            data = await self.client.async_fetch(self._site_id, month_start)
        except AmperiumAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AmperiumError as err:
            raise UpdateFailed(str(err)) from err

        data["scheme"] = self.entry.options.get(CONF_SCHEME)
        data["login_valid_until"] = dt_util.parse_datetime(
            self.client.refresh_expires_at or ""
        )
        data.update(await self._async_fetch_prices())
        data.update(await self._async_fetch_extended(bool(data.get("is_producing"))))
        self._check_login_expiry()

        return data

    async def _async_fetch_prices(self) -> dict[str, Any]:
        """Fetch hourly prices for today and tomorrow (local days).

        Prices are an extra: a failure here must not make the main sensors
        unavailable, so errors are logged and the price data is left out.
        """
        today_start = dt_util.start_of_local_day()
        tomorrow_start = today_start + timedelta(days=1)
        day_after_start = tomorrow_start + timedelta(days=1)

        try:
            today = await self.client.async_get_prices(
                self._site_id, today_start, tomorrow_start
            )
        except AmperiumAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AmperiumError as err:
            _LOGGER.debug("Could not fetch today's prices: %s", err)
            return {}

        result: dict[str, Any] = {
            "prices_today": today,
            **summarise_prices(today),
        }
        now_utc = dt_util.utcnow()
        for bucket in today:
            start = dt_util.parse_datetime(bucket["start"] or "")
            end = dt_util.parse_datetime(bucket["end"] or "")
            if start and end and start <= now_utc < end:
                result["consumer_price_now"] = bucket.get("consumer")
                break

        # Tomorrow's prices are published around midday, so this may be empty.
        try:
            tomorrow = await self.client.async_get_prices(
                self._site_id, tomorrow_start, day_after_start
            )
        except AmperiumError as err:
            _LOGGER.debug("Could not fetch tomorrow's prices: %s", err)
            tomorrow = []
        result["prices_tomorrow"] = [b for b in tomorrow if b.get("spot") is not None]
        return result

    async def _async_fetch_extended(self, producing: bool) -> dict[str, Any]:
        """Fetch hourly consumption/charges and the Norgespris comparison.

        Heavier than the main poll, so it runs at most once per
        EXTENDED_SCAN_INTERVAL. Everything here is an extra: errors are logged
        and the last good values are kept, so the main sensors keep working.
        """
        now = dt_util.utcnow()
        if (
            self._extended_at is not None
            and (now - self._extended_at).total_seconds() < EXTENDED_SCAN_INTERVAL
        ):
            return self._extended

        tz = dt_util.DEFAULT_TIME_ZONE
        prev_start, this_start, _ = local_month_bounds(now.astimezone(tz))
        hour_now = now.replace(minute=0, second=0, microsecond=0)
        # Month-sized requests: previous month, then this month up to now.
        windows = [(prev_start, this_start), (this_start, hour_now)]
        client, site = self.client, self._site_id

        energy: list[dict[str, Any]] = []
        charges: list[dict[str, Any]] = []
        grid_responses: dict[str, dict[str, Any] | None] = {"": None, "_last_month": None}
        energy_ok = False
        try:
            for start, end in windows:
                if end <= start:
                    continue
                try:
                    energy += await client.async_get_energy(site, start, end)
                    energy_ok = True
                except AmperiumAuthError:
                    raise
                except AmperiumError as err:
                    _LOGGER.debug("Could not fetch hourly energy: %s", err)
                try:
                    response = await client.async_get_charges(site, start, end)
                    charges += response["energy"]
                    grid_responses["" if start == this_start else "_last_month"] = response
                except AmperiumAuthError:
                    raise
                except AmperiumError as err:
                    _LOGGER.debug("Could not fetch hourly charges: %s", err)
        except AmperiumAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err

        day_start = self.entry.options.get(CONF_DAY_START, DEFAULT_DAY_START)
        day_end = self.entry.options.get(CONF_DAY_END, DEFAULT_DAY_END)
        new: dict[str, Any] = {}
        new.update(summarise_energy(energy, now, tz, day_start, day_end))
        new.update(capacity_peaks(energy, now, tz))
        new.update(summarise_charges(charges, now, tz))
        for suffix, response in grid_responses.items():
            new.update(summarise_grid(response, suffix))
        # The billing split of day/night kWh comes straight from Amperium
        # (gridRent); prefer it over our own hour-of-day classification.
        for api_key, own_key in (
            ("grid_energy_day_kwh", "energy_day_month"),
            ("grid_energy_night_kwh", "energy_night_month"),
        ):
            if new.get(api_key) is not None:
                new[own_key] = new[api_key]

        try:
            await async_import_statistics(
                self.hass, site, energy, charges, producing, now
            )
        except Exception:  # noqa: BLE001 - statistics are optional
            _LOGGER.warning("Could not import statistics", exc_info=True)

        self._extended.update(new)
        if energy_ok:
            self._extended_at = now
        return self._extended
