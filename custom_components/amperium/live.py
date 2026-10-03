"""Follow a user-chosen power sensor and expose live power + hour forecast."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.util import dt as dt_util

from .hourpower import HourIntegrator, to_kw


def _state_to_kw(state: State | None) -> float | None:
    """Read a power sensor state as kW (None if missing/unavailable/unknown unit)."""
    if state is None:
        return None
    return to_kw(state.state, state.attributes.get("unit_of_measurement"))


class LivePowerTracker:
    """Tracks one power sensor and integrates it over the current clock hour."""

    def __init__(self, hass: HomeAssistant, entity_id: str) -> None:
        """Create the tracker; call async_start to begin listening."""
        self.hass = hass
        self.entity_id = entity_id
        self._integrator = HourIntegrator()
        self._listeners: list[Callable[[], None]] = []

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Start listening; returns a callback that stops it."""
        self._integrator.update(
            dt_util.utcnow(), _state_to_kw(self.hass.states.get(self.entity_id))
        )
        unsub_state = async_track_state_change_event(
            self.hass, [self.entity_id], self._handle_state
        )
        # Roll the hour over exactly at the top of each hour, even if the
        # source sensor is quiet.
        unsub_time = async_track_time_change(
            self.hass, self._handle_tick, minute=0, second=0
        )

        @callback
        def stop() -> None:
            unsub_state()
            unsub_time()

        return stop

    @callback
    def _handle_state(self, event: Event) -> None:
        self._integrator.update(dt_util.utcnow(), _state_to_kw(event.data.get("new_state")))
        self._notify()

    @callback
    def _handle_tick(self, _now: Any) -> None:
        self._integrator.snapshot(dt_util.utcnow())
        self._notify()

    def snapshot(self) -> dict[str, Any]:
        """Return the current live view (power now, hour average and forecast)."""
        return self._integrator.snapshot(dt_util.utcnow())

    @callback
    def add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Call ``listener`` whenever the live values change."""
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            self._listeners.remove(listener)

        return remove

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()
