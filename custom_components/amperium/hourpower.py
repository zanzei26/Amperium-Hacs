"""Pure helpers for turning a live power sensor into an hourly average.

The grid operator's capacity charge is based on the *average power over each
clock hour*. A live sensor (e.g. Tibber Pulse) reports momentary power, so we
integrate it over the current hour (holding the last value between updates)
to see where the hour is heading. No Home Assistant imports, so this can be
tested on its own.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

HOUR = dt.timedelta(hours=1)

_UNIT_TO_KW = {"W": 0.001, "kW": 1.0, "MW": 1000.0}


def to_kw(state: Any, unit: Any) -> float | None:
    """Convert a sensor state + unit to kW; None if unknown/invalid."""
    factor = _UNIT_TO_KW.get(unit)
    if factor is None:
        return None
    try:
        value = float(state)
    except (TypeError, ValueError):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return value * factor


def _floor_hour(value: dt.datetime) -> dt.datetime:
    return value.replace(minute=0, second=0, microsecond=0)


class HourIntegrator:
    """Time-weighted average of a power reading within the current UTC hour."""

    def __init__(self) -> None:
        """Start empty; the first update opens the current hour."""
        self.hour_start: dt.datetime | None = None
        self.energy_kwh = 0.0  # integrated so far this hour
        self.covered_h = 0.0  # hours of this hour with a valid reading
        self._cursor: dt.datetime | None = None
        self._kw: float | None = None
        self.last_complete: dict[str, Any] | None = None

    def update(self, now: dt.datetime, kw: float | None) -> None:
        """Record a new reading (None = unavailable) at ``now``."""
        self._advance(now)
        self._kw = kw

    def _advance(self, now: dt.datetime) -> None:
        """Account for the time since the last call, rolling over hours."""
        if self._cursor is None:
            self._cursor = now
            self.hour_start = _floor_hour(now)
            return
        assert self.hour_start is not None
        while True:
            hour_end = self.hour_start + HOUR
            seg_end = min(now, hour_end)
            if self._kw is not None and seg_end > self._cursor:
                span_h = (seg_end - self._cursor).total_seconds() / 3600
                self.energy_kwh += self._kw * span_h
                self.covered_h += span_h
            if seg_end > self._cursor:
                self._cursor = seg_end
            if now < hour_end:
                break
            average = self.energy_kwh / self.covered_h if self.covered_h else None
            self.last_complete = {
                "start": self.hour_start,
                "average_kw": average,
                "coverage": self.covered_h,
            }
            self.hour_start = hour_end
            self.energy_kwh = 0.0
            self.covered_h = 0.0
            self._cursor = max(self._cursor, hour_end)

    def snapshot(self, now: dt.datetime) -> dict[str, Any]:
        """Return the live view for this hour.

        ``forecast_kw`` assumes the current power holds for the rest of the
        hour and that any part of the hour without readings looked like the
        average of the part that had readings.
        """
        self._advance(now)
        assert self.hour_start is not None
        elapsed_h = (now - self.hour_start).total_seconds() / 3600
        remaining_h = max(0.0, 1.0 - elapsed_h)
        average = self.energy_kwh / self.covered_h if self.covered_h else None
        forecast = None
        if self._kw is not None:
            past = average if average is not None else self._kw
            forecast = past * elapsed_h + self._kw * remaining_h
        return {
            "kw": self._kw,
            "average_so_far_kw": average,
            "coverage": min(1.0, self.covered_h / elapsed_h) if elapsed_h > 0 else 1.0,
            "forecast_kw": forecast,
            "hour_start": self.hour_start,
        }
