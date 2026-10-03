"""Binary sensor platform for Amperium (HAN meter online)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AmperiumConfigEntry
from .const import CONF_SITE_ID, CONF_SITE_NAME, DOMAIN
from .coordinator import AmperiumCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmperiumConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HAN-online binary sensor."""
    async_add_entities([AmperiumHanSensor(entry.runtime_data, entry)])


class AmperiumHanSensor(CoordinatorEntity[AmperiumCoordinator], BinarySensorEntity):
    """Reports whether the HAN port meter is online."""

    _attr_has_entity_name = True
    _attr_translation_key = "han_online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self, coordinator: AmperiumCoordinator, entry: AmperiumConfigEntry
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator)
        site_id = entry.data[CONF_SITE_ID]
        site_name = entry.data.get(CONF_SITE_NAME) or f"Site {site_id}"
        self._attr_unique_id = f"{entry.entry_id}_han_online"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(site_id))},
            name=f"Amperium {site_name}",
            manufacturer="Amperium",
            model="HAN / kraftlag",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if the HAN meter is online."""
        if not self.coordinator.data:
            return None
        value: Any = self.coordinator.data.get("han_online")
        if value is None:
            return None
        return bool(value)
