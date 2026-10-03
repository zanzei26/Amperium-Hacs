"""DataUpdateCoordinator for Amperium."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AmperiumAuthError, AmperiumClient, AmperiumError, summarise_prices
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_SITE_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

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
        session = async_get_clientsession(hass)
        self.client = AmperiumClient(
            session,
            access_token=entry.data.get(CONF_ACCESS_TOKEN),
            refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data, persisting tokens if they were refreshed."""
        before_access = self.client.access_token
        before_refresh = self.client.refresh_token
        try:
            data = await self.client.async_fetch(self._site_id)
        except AmperiumAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AmperiumError as err:
            raise UpdateFailed(str(err)) from err

        data.update(await self._async_fetch_prices())

        # If the access/refresh token changed (lazy refresh), persist it so
        # a restart keeps working.
        if (
            self.client.access_token != before_access
            or self.client.refresh_token != before_refresh
        ):
            new_data = {
                **self.entry.data,
                CONF_ACCESS_TOKEN: self.client.access_token,
                CONF_REFRESH_TOKEN: self.client.refresh_token,
            }
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)

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
