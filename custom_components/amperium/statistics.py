"""Import Amperium hourly data as long-term statistics.

The Energy dashboard needs a cumulative meter. The sensors from the API reset
daily/monthly, so the hourly data is imported as external statistics instead
(statistic ids ``amperium:<site>_energy_import`` etc.), which the Energy
dashboard can use directly.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    statistics_during_period,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .derived import build_hourly_statistics, complete_hours

try:  # Newer Home Assistant replaced has_mean with mean_type
    from homeassistant.components.recorder.models import StatisticMeanType
except ImportError:  # pragma: no cover - older Home Assistant
    StatisticMeanType = None

_LOGGER = logging.getLogger(__name__)

CURRENCY_UNIT = "NOK"


def _metadata(
    statistic_id: str, name: str, unit: str, unit_class: str | None
) -> StatisticMetaData:
    """Build metadata that works across Home Assistant versions."""
    meta: dict[str, Any] = {
        "has_sum": True,
        "name": name,
        "source": DOMAIN,
        "statistic_id": statistic_id,
        "unit_of_measurement": unit,
    }
    if StatisticMeanType is not None:
        meta["mean_type"] = StatisticMeanType.NONE
    else:
        meta["has_mean"] = False
    if "unit_class" in getattr(StatisticMetaData, "__annotations__", {}):
        meta["unit_class"] = unit_class
    return meta  # type: ignore[return-value]


async def _base_sum(hass: HomeAssistant, statistic_id: str, first: dt.datetime) -> float:
    """Return the sum of the last stored row before ``first`` (0 if none)."""
    rows = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        first - dt.timedelta(days=7),
        first,
        {statistic_id},
        "hour",
        None,
        {"sum"},
    )
    stored = rows.get(statistic_id) or []
    if not stored:
        return 0.0
    return float(stored[-1].get("sum") or 0.0)


async def _import_series(
    hass: HomeAssistant,
    statistic_id: str,
    name: str,
    unit: str,
    unit_class: str | None,
    buckets: list[dict[str, Any]],
    key: str,
    now: dt.datetime,
) -> None:
    """Import one cumulative hourly series."""
    hours = complete_hours(buckets, now)
    if not hours:
        return
    base = await _base_sum(hass, statistic_id, hours[0]["start"])
    rows = build_hourly_statistics(hours, key, base, now)
    async_add_external_statistics(
        hass, _metadata(statistic_id, name, unit, unit_class), rows
    )
    _LOGGER.debug("Imported %d hourly rows into %s", len(rows), statistic_id)


async def async_import_statistics(
    hass: HomeAssistant,
    site_id: int,
    energy: list[dict[str, Any]],
    charges: list[dict[str, Any]],
    producing: bool,
    now: dt.datetime,
) -> None:
    """Import consumption (and cost / export) as long-term statistics."""
    prefix = f"{DOMAIN}:{site_id}"
    kwh = UnitOfEnergy.KILO_WATT_HOUR
    await _import_series(
        hass, f"{prefix}_energy_import", "Amperium forbruk", kwh, "energy",
        energy, "import", now,
    )
    if producing:
        await _import_series(
            hass, f"{prefix}_energy_export", "Amperium eksport", kwh, "energy",
            energy, "export", now,
        )
    await _import_series(
        hass, f"{prefix}_energy_cost", "Amperium energikostnad", CURRENCY_UNIT, None,
        charges, "total", now,
    )
