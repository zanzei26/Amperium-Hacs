"""Sensor platform for Amperium."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AmperiumConfigEntry
from .const import CONF_SITE_ID, CONF_SITE_NAME, DOMAIN
from .coordinator import AmperiumCoordinator


@dataclass(frozen=True, kw_only=True)
class AmperiumSensorDescription(SensorEntityDescription):
    """Describes an Amperium sensor."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[AmperiumSensorDescription, ...] = (
    AmperiumSensorDescription(
        key="energy_month",
        translation_key="energy_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        value_fn=lambda d: _round(d.get("energy_month"), 2),
    ),
    AmperiumSensorDescription(
        key="energy_today",
        translation_key="energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("energy_today"), 2),
    ),
    AmperiumSensorDescription(
        key="power_now",
        translation_key="power_now",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("power_now"), 3),
    ),
    AmperiumSensorDescription(
        key="cost_total",
        translation_key="cost_total",
        native_unit_of_measurement="kr",
        icon="mdi:cash-multiple",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("cost_total"), 2),
    ),
    AmperiumSensorDescription(
        key="cost_energy",
        translation_key="cost_energy",
        native_unit_of_measurement="kr",
        icon="mdi:cash",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("cost_energy"), 2),
    ),
    AmperiumSensorDescription(
        key="cost_grid_rent",
        translation_key="cost_grid_rent",
        native_unit_of_measurement="kr",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("cost_grid_rent"), 2),
    ),
    AmperiumSensorDescription(
        key="spot_price",
        translation_key="spot_price",
        native_unit_of_measurement="kr/kWh",
        icon="mdi:chart-line",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda d: _round(d.get("spot_price"), 4),
    ),
    AmperiumSensorDescription(
        key="price_min_today",
        translation_key="price_min_today",
        native_unit_of_measurement="kr/kWh",
        icon="mdi:arrow-down-bold",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda d: _round(d.get("price_min_today"), 4),
    ),
    AmperiumSensorDescription(
        key="price_max_today",
        translation_key="price_max_today",
        native_unit_of_measurement="kr/kWh",
        icon="mdi:arrow-up-bold",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda d: _round(d.get("price_max_today"), 4),
    ),
    AmperiumSensorDescription(
        key="price_avg_today",
        translation_key="price_avg_today",
        native_unit_of_measurement="kr/kWh",
        icon="mdi:chart-line-variant",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda d: _round(d.get("price_avg_today"), 4),
    ),
)


def _round(value: Any, digits: int) -> Any:
    """Round numeric values, pass through None."""
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmperiumConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Amperium sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        AmperiumSensor(coordinator, entry, description) for description in SENSORS
    )


class AmperiumSensor(CoordinatorEntity[AmperiumCoordinator], SensorEntity):
    """A single Amperium sensor."""

    entity_description: AmperiumSensorDescription
    _attr_has_entity_name = True
    # Hourly price lists are large and change daily; keep them out of the DB.
    _unrecorded_attributes = frozenset({"prices_today", "prices_tomorrow"})

    def __init__(
        self,
        coordinator: AmperiumCoordinator,
        entry: AmperiumConfigEntry,
        description: AmperiumSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        site_id = entry.data[CONF_SITE_ID]
        site_name = entry.data.get(CONF_SITE_NAME) or f"Site {site_id}"
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(site_id))},
            name=f"Amperium {site_name}",
            manufacturer="Amperium",
            model="HAN / kraftlag",
        )

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the last-updated timestamp from the meter."""
        data = self.coordinator.data
        if not data:
            return None
        key = self.entity_description.key
        if key == "energy_month":
            return {"updated": data.get("updated")}
        if key == "spot_price":
            # Hourly buckets (start/end/spot/surcharge/vat_percent) for use in
            # e.g. ApexCharts cards or automations.
            return {
                "prices_today": data.get("prices_today", []),
                "prices_tomorrow": data.get("prices_tomorrow", []),
            }
        if key == "price_min_today":
            return {"hour": data.get("price_min_hour")}
        if key == "price_max_today":
            return {"hour": data.get("price_max_hour")}
        return None
