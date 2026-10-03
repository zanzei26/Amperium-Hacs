"""Sensor platform for Amperium."""
from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import AmperiumConfigEntry
from .amqp_feed import (
    AmperiumLiveFeed,
    LiveFeedState,
    async_prepare_library,
    consume_with_aio_pika,
)
from .const import (
    CONF_HAS_DOBBE,
    CONF_POWER_ENTITY,
    CONF_SITE_ID,
    CONF_SITE_NAME,
    DOMAIN,
)
from .coordinator import AmperiumCoordinator
from .derived import (
    SIGNAL_STATES,
    choose_power_now,
    compensation_difference,
    compensation_for_scheme,
    consumer_price,
    gross_grid_from_net,
    gross_total_from_net,
    han_signal_state,
    net_for_scheme,
    net_with_norgespris,
    net_with_subsidy,
    subsidy_applied,
)
from .live import LivePowerTracker


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
        key="energy_yesterday",
        translation_key="energy_yesterday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("energy_yesterday"), 3),
    ),
    AmperiumSensorDescription(
        key="energy_last_hour",
        translation_key="energy_last_hour",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=3,
        value_fn=lambda d: _round(d.get("energy_last_hour"), 3),
    ),
    AmperiumSensorDescription(
        key="energy_last_month",
        translation_key="energy_last_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=1,
        value_fn=lambda d: _round(d.get("energy_last_month"), 2),
    ),
    AmperiumSensorDescription(
        key="energy_day_month",
        translation_key="energy_day_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=1,
        value_fn=lambda d: _round(d.get("energy_day_month"), 2),
    ),
    AmperiumSensorDescription(
        key="energy_night_month",
        translation_key="energy_night_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=1,
        value_fn=lambda d: _round(d.get("energy_night_month"), 2),
    ),
    AmperiumSensorDescription(
        key="energy_export_month",
        translation_key="energy_export_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _round(d.get("energy_export_month"), 2),
    ),
    AmperiumSensorDescription(
        key="energy_export_today",
        translation_key="energy_export_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _round(d.get("energy_export_today"), 2),
    ),
    AmperiumSensorDescription(
        key="cost_yesterday",
        translation_key="cost_yesterday",
        native_unit_of_measurement="kr",
        icon="mdi:cash",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("cost_yesterday"), 2),
    ),
    AmperiumSensorDescription(
        key="norgespris_month",
        translation_key="norgespris_month",
        native_unit_of_measurement="kr",
        icon="mdi:cash-plus",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("norgespris_month"), 2),
    ),
    AmperiumSensorDescription(
        key="cost_energy_last_month",
        translation_key="cost_energy_last_month",
        native_unit_of_measurement="kr",
        icon="mdi:cash",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("cost_energy_last_month"), 2),
    ),
    AmperiumSensorDescription(
        key="cost_grid_rent_last_month",
        translation_key="cost_grid_rent_last_month",
        native_unit_of_measurement="kr",
        icon="mdi:transmission-tower",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("cost_grid_rent_last_month"), 2),
    ),
    AmperiumSensorDescription(
        key="cost_last_month",
        translation_key="cost_last_month",
        native_unit_of_measurement="kr",
        icon="mdi:cash-multiple",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("cost_last_month"), 2),
    ),
    AmperiumSensorDescription(
        key="grid_gross_month",
        translation_key="grid_gross_month",
        native_unit_of_measurement="kr",
        icon="mdi:transmission-tower",
        suggested_display_precision=2,
        value_fn=lambda d: _round(
            gross_grid_from_net(
                d.get("cost_grid_rent"), d.get("grid_compensation"), d.get("grid_total")
            ),
            2,
        ),
    ),
    AmperiumSensorDescription(
        key="subsidy_applied_month",
        translation_key="subsidy_applied_month",
        native_unit_of_measurement="kr",
        icon="mdi:cash-plus",
        suggested_display_precision=2,
        value_fn=lambda d: _round(subsidy_applied(d.get("grid_compensation")), 2),
    ),
    AmperiumSensorDescription(
        key="fixed_month",
        translation_key="fixed_month",
        native_unit_of_measurement="kr",
        icon="mdi:calendar-month",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("fixed_total"), 2),
    ),
    AmperiumSensorDescription(
        key="gross_total_month",
        translation_key="gross_total_month",
        native_unit_of_measurement="kr",
        icon="mdi:cash-multiple",
        suggested_display_precision=2,
        value_fn=lambda d: _round(
            gross_total_from_net(
                d.get("cost_total"), d.get("fixed_total"), d.get("grid_compensation")
            ),
            2,
        ),
    ),
    AmperiumSensorDescription(
        key="capacity_avg_kw",
        translation_key="capacity_avg_kw",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:chart-bell-curve-cumulative",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("capacity_avg_kw"), 3),
    ),
    AmperiumSensorDescription(
        key="capacity_calc_kw",
        translation_key="capacity_calc_kw",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:chart-bell-curve-cumulative",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("capacity_calc_kw"), 3),
    ),
    AmperiumSensorDescription(
        key="capacity_threshold_kw",
        translation_key="capacity_threshold_kw",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:target",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("capacity_threshold_kw"), 3),
    ),
    AmperiumSensorDescription(
        key="capacity_amount",
        translation_key="capacity_amount",
        native_unit_of_measurement="kr",
        icon="mdi:transmission-tower",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("capacity_amount"), 2),
    ),
    AmperiumSensorDescription(
        key="capacity_headroom_kw",
        translation_key="capacity_headroom_kw",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:arrow-collapse-up",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("capacity_headroom_kw"), 3),
    ),
    AmperiumSensorDescription(
        key="capacity_avg_kw_last_month",
        translation_key="capacity_avg_kw_last_month",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:chart-bell-curve-cumulative",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("capacity_avg_kw_last_month"), 3),
    ),
    AmperiumSensorDescription(
        key="capacity_amount_last_month",
        translation_key="capacity_amount_last_month",
        native_unit_of_measurement="kr",
        icon="mdi:transmission-tower",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("capacity_amount_last_month"), 2),
    ),
    AmperiumSensorDescription(
        key="energy_gross_month",
        translation_key="energy_gross_month",
        native_unit_of_measurement="kr",
        icon="mdi:cash",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("energy_gross_month"), 2),
    ),
    AmperiumSensorDescription(
        key="vat_month",
        translation_key="vat_month",
        native_unit_of_measurement="kr",
        icon="mdi:percent",
        suggested_display_precision=2,
        value_fn=lambda d: _round(d.get("vat_month"), 2),
    ),
    AmperiumSensorDescription(
        key="compensation_month",
        translation_key="compensation_month",
        native_unit_of_measurement="kr",
        icon="mdi:cash-plus",
        suggested_display_precision=2,
        value_fn=lambda d: _round(
            compensation_for_scheme(
                d.get("scheme"),
                d.get("norgespris_month"),
                subsidy_applied(d.get("grid_compensation")),
            ),
            2,
        ),
    ),
    AmperiumSensorDescription(
        key="net_cost_month",
        translation_key="net_cost_month",
        native_unit_of_measurement="kr",
        icon="mdi:cash-check",
        suggested_display_precision=2,
        value_fn=lambda d: _round(
            net_for_scheme(
                d.get("scheme"),
                d.get("cost_total"),
                d.get("fixed_total"),
                subsidy_applied(d.get("grid_compensation")),
                d.get("norgespris_month"),
            ),
            2,
        ),
    ),
    AmperiumSensorDescription(
        key="net_norgespris_month",
        translation_key="net_norgespris_month",
        native_unit_of_measurement="kr",
        icon="mdi:cash-check",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _round(
            net_with_norgespris(
                d.get("cost_total"),
                d.get("fixed_total"),
                subsidy_applied(d.get("grid_compensation")),
                d.get("norgespris_month"),
            ),
            2,
        ),
    ),
    AmperiumSensorDescription(
        key="net_subsidy_month",
        translation_key="net_subsidy_month",
        native_unit_of_measurement="kr",
        icon="mdi:cash-check",
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _round(
            net_with_subsidy(d.get("cost_total"), d.get("fixed_total")), 2
        ),
    ),
    AmperiumSensorDescription(
        key="norgespris_saves_month",
        translation_key="norgespris_saves_month",
        native_unit_of_measurement="kr",
        icon="mdi:scale-balance",
        suggested_display_precision=2,
        value_fn=lambda d: _round(
            compensation_difference(
                d.get("norgespris_month"), subsidy_applied(d.get("grid_compensation"))
            ),
            2,
        ),
    ),
    AmperiumSensorDescription(
        key="han_signal",
        translation_key="han_signal",
        icon="mdi:signal",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("han_signal"),
    ),
    AmperiumSensorDescription(
        key="login_valid_until",
        translation_key="login_valid_until",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:key-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("login_valid_until"),
    ),
    AmperiumSensorDescription(
        key="han_signal_quality",
        translation_key="han_signal_quality",
        device_class=SensorDeviceClass.ENUM,
        options=[*SIGNAL_STATES.values(), "no_data", "offline"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: han_signal_state(d.get("han_signal"), d.get("han_online")),
    ),
    AmperiumSensorDescription(
        key="spot_price_incl_vat",
        translation_key="spot_price_incl_vat",
        native_unit_of_measurement="kr/kWh",
        icon="mdi:cash",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        # Current hour's bucket from the price list (it has a preliminary
        # fallback); otherwise the main poll's current price.
        value_fn=lambda d: _round(
            d.get("consumer_price_now")
            if d.get("consumer_price_now") is not None
            else consumer_price(
                d.get("spot_price")
                if d.get("spot_price") is not None
                else d.get("spot_price_preliminary"),
                d.get("surcharge"),
                d.get("vat_percent"),
            ),
            4,
        ),
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

    # Optional: the user's own power sensor (for example a local HAN reader).
    # "Power now" follows it, because Amperium only reports power once an hour.
    power_entity = entry.options.get(CONF_POWER_ENTITY)
    tracker: LivePowerTracker | None = None
    if power_entity:
        tracker = LivePowerTracker(hass, power_entity)
        entry.async_on_unload(tracker.async_start())

    # Optional: Amperium's own live feed (the one the app's live power view uses).
    live_state: LiveFeedState | None = None
    if entry.options.get(CONF_HAS_DOBBE):
        live_state = LiveFeedState()
        try:
            from homeassistant.util.ssl import get_default_context

            ssl_context = get_default_context()
        except Exception:  # noqa: BLE001 - older Home Assistant: let the library build one
            ssl_context = None
        feed = AmperiumLiveFeed(
            coordinator.client,
            entry.data[CONF_SITE_ID],
            state=live_state,
            consume=functools.partial(consume_with_aio_pika, ssl_context=ssl_context),
            ensure_library=lambda: async_prepare_library(hass),
        )
        entry.async_create_background_task(hass, feed.run(), "amperium_live_feed")

    entities: list[SensorEntity] = [
        AmperiumSensor(coordinator, entry, description, tracker, live_state)
        for description in SENSORS
    ]
    if tracker is not None:
        entities.append(AmperiumLivePowerSensor(tracker, entry, "live_power"))
        entities.append(AmperiumLivePowerSensor(tracker, entry, "hour_power_forecast"))
    if live_state is not None:
        entities.append(AmperiumLiveFeedSensor(live_state, entry))

    async_add_entities(entities)


class AmperiumSensor(CoordinatorEntity[AmperiumCoordinator], SensorEntity):
    """A single Amperium sensor."""

    entity_description: AmperiumSensorDescription
    _attr_has_entity_name = True
    # Hourly price lists are large and change daily; keep them out of the DB.
    _unrecorded_attributes = frozenset(
        {
            "prices_today",
            "prices_tomorrow",
            "consumption_today",
            "tiers",
            "peaks",
            "source",
            "local_entity",
            "amperium_kw",
            "amperium_live_kw",
            "live_status",
        }
    )

    def __init__(
        self,
        coordinator: AmperiumCoordinator,
        entry: AmperiumConfigEntry,
        description: AmperiumSensorDescription,
        tracker: LivePowerTracker | None = None,
        live_state: LiveFeedState | None = None,
    ) -> None:
        """Initialise the sensor (tracker and live feed are only used by "power now")."""
        super().__init__(coordinator)
        self.entity_description = description
        is_power_now = description.key == "power_now"
        self._tracker = tracker if is_power_now else None
        self._live_state = live_state if is_power_now else None
        site_id = entry.data[CONF_SITE_ID]
        site_name = entry.data.get(CONF_SITE_NAME) or f"Site {site_id}"
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(site_id))},
            name=f"Amperium {site_name}",
            manufacturer="Amperium",
            model="HAN / kraftlag",
        )

    async def async_added_to_hass(self) -> None:
        """Follow the local power sensor too, if one was chosen."""
        await super().async_added_to_hass()
        if self._tracker is not None:
            self.async_on_remove(self._tracker.add_listener(self._handle_local_update))
        if self._live_state is not None:
            self.async_on_remove(self._live_state.add_listener(self._handle_local_update))

    @callback
    def _handle_local_update(self) -> None:
        self.async_write_ha_state()

    def _power_now(self) -> tuple[float | None, str | None]:
        """Power now in kW and its source: local sensor, Amperium live, then Amperium hourly."""
        local = self._tracker.snapshot()["kw"] if self._tracker is not None else None
        live = (
            self._live_state.current_kw(dt_util.utcnow())
            if self._live_state is not None
            else None
        )
        amperium = _round((self.coordinator.data or {}).get("power_now"), 3)
        return choose_power_now(local, amperium, live)

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        if self.entity_description.key == "power_now":
            return _round(self._power_now()[0], 3)
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the last-updated timestamp from the meter."""
        key = self.entity_description.key
        if key == "power_now":
            return {
                "source": self._power_now()[1],
                "local_entity": self._tracker.entity_id if self._tracker else None,
                "amperium_kw": _round((self.coordinator.data or {}).get("power_now"), 3),
                "amperium_live_kw": (
                    self._live_state.current_kw(dt_util.utcnow())
                    if self._live_state is not None
                    else None
                ),
                "live_status": self._live_state.status if self._live_state else "off",
            }
        data = self.coordinator.data
        if not data:
            return None
        if key == "energy_month":
            return {"updated": data.get("updated")}
        if key == "energy_last_hour":
            return {"consumption_today": data.get("consumption_today", [])}
        if key == "spot_price":
            # Hourly buckets (start/end/spot/surcharge/vat_percent) for use in
            # e.g. ApexCharts cards or automations.
            return {
                "prices_today": data.get("prices_today", []),
                "prices_tomorrow": data.get("prices_tomorrow", []),
            }
        if key == "grid_gross_month":
            return data.get("grid_breakdown")
        if key == "capacity_avg_kw":
            return data.get("capacity_details")
        if key == "capacity_calc_kw":
            calc, api_value = data.get("capacity_calc_kw"), data.get("capacity_avg_kw")
            return {
                "peaks": data.get("capacity_peaks", []),
                "days_with_data": data.get("capacity_peak_days"),
                "amperium_value_kw": api_value,
                "difference_kw": (
                    round(calc - api_value, 3)
                    if calc is not None and api_value is not None
                    else None
                ),
            }
        if key == "capacity_avg_kw_last_month":
            return data.get("capacity_details_last_month")
        if key == "price_min_today":
            return {
                "hour": data.get("price_min_hour"),
                "consumer": data.get("price_min_consumer"),
            }
        if key == "price_max_today":
            return {
                "hour": data.get("price_max_hour"),
                "consumer": data.get("price_max_consumer"),
            }
        if key == "price_avg_today":
            return {"consumer": data.get("price_avg_consumer")}
        return None


class AmperiumLivePowerSensor(SensorEntity):
    """Live power, or the forecast average for the current hour.

    Both come from a Home Assistant power sensor the user chose (not from
    Amperium, which only reports power once per hour).
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _unrecorded_attributes = frozenset({"source", "hour_start"})

    def __init__(
        self, tracker: LivePowerTracker, entry: AmperiumConfigEntry, kind: str
    ) -> None:
        """Initialise the sensor ("live_power" or "hour_power_forecast")."""
        self._tracker = tracker
        self._coordinator = entry.runtime_data
        self._kind = kind
        self._attr_translation_key = kind
        site_id = entry.data[CONF_SITE_ID]
        site_name = entry.data.get(CONF_SITE_NAME) or f"Site {site_id}"
        self._attr_unique_id = f"{entry.entry_id}_{kind}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(site_id))},
            name=f"Amperium {site_name}",
            manufacturer="Amperium",
            model="HAN / kraftlag",
        )

    async def async_added_to_hass(self) -> None:
        """Update whenever the source sensor changes."""
        self.async_on_remove(self._tracker.add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        """Return power now, or the forecast hour average, in kW."""
        snap = self._tracker.snapshot()
        value = snap["kw"] if self._kind == "live_power" else snap["forecast_kw"]
        return None if value is None else round(value, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Show the source sensor and, for the forecast, how it is derived."""
        attrs: dict[str, Any] = {"source": self._tracker.entity_id}
        if self._kind == "hour_power_forecast":
            snap = self._tracker.snapshot()
            average = snap["average_so_far_kw"]
            attrs["average_so_far_kw"] = None if average is None else round(average, 3)
            attrs["coverage"] = round(snap["coverage"], 2)
            attrs["hour_start"] = snap["hour_start"].isoformat()
            # Compare with this month's top-three threshold (completed hours).
            data = self._coordinator.data or {}
            threshold = data.get("capacity_threshold_kw")
            forecast = snap["forecast_kw"]
            attrs["capacity_threshold_kw"] = threshold
            attrs["above_threshold"] = (
                forecast > threshold
                if forecast is not None and threshold is not None
                else None
            )
        return attrs


class AmperiumLiveFeedSensor(SensorEntity):
    """Power now straight from Amperium's live feed (only with the option switched on).

    Empty when no reading has arrived in the last two minutes. The attributes say
    how the feed is doing, which makes it easy to see whether the meter delivers.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "amperium_live_power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _unrecorded_attributes = frozenset(
        {"status", "messages", "age_seconds", "observed_at", "last_error"}
    )

    def __init__(self, state: LiveFeedState, entry: AmperiumConfigEntry) -> None:
        """Initialise the sensor."""
        self._state = state
        site_id = entry.data[CONF_SITE_ID]
        site_name = entry.data.get(CONF_SITE_NAME) or f"Site {site_id}"
        self._attr_unique_id = f"{entry.entry_id}_amperium_live_power"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(site_id))},
            name=f"Amperium {site_name}",
            manufacturer="Amperium",
            model="HAN / kraftlag",
        )

    async def async_added_to_hass(self) -> None:
        """Update whenever the feed has news."""
        self.async_on_remove(self._state.add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        """Return the live power in kW, or None without a recent reading."""
        value = self._state.current_kw(dt_util.utcnow())
        return None if value is None else round(value, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Say how the feed is doing."""
        age = self._state.age_seconds(dt_util.utcnow())
        observed = self._state.import_observed
        return {
            "status": self._state.status,
            "messages": self._state.messages,
            "age_seconds": None if age is None else round(age),
            "observed_at": observed.isoformat() if observed else None,
            "last_error": self._state.last_error,
        }
