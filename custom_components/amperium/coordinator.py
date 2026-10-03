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

from .api import AmperiumAuthError, AmperiumClient, AmperiumError
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
