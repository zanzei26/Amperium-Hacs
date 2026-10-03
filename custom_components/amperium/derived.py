"""Pure helpers that turn Amperium hourly buckets into sensor values.

No Home Assistant imports here, so the logic can be tested on its own.
All bucket timestamps are timezone-aware datetimes (UTC from the API); day
and month boundaries are evaluated in the timezone passed in (the user's
local time).
"""
from __future__ import annotations

import datetime as dt
from typing import Any


def local_month_bounds(
    now_local: dt.datetime,
) -> tuple[dt.datetime, dt.datetime, dt.datetime]:
    """Return (start of previous month, start of this month, start of next)."""
    this_start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_start = (this_start - dt.timedelta(days=1)).replace(day=1)
    next_start = (this_start + dt.timedelta(days=32)).replace(day=1)
    return prev_start, this_start, next_start


def complete_hours(buckets: list[dict[str, Any]], now: dt.datetime) -> list[dict[str, Any]]:
    """Sort buckets, drop duplicates, partial/future hours and misaligned ones."""
    seen: dict[dt.datetime, dict[str, Any]] = {}
    for bucket in buckets:
        start, end = bucket.get("start"), bucket.get("end")
        if not isinstance(start, dt.datetime) or not isinstance(end, dt.datetime):
            continue
        if end > now or start.minute or start.second or start.microsecond:
            continue
        seen[start] = bucket
    return [seen[k] for k in sorted(seen)]


def choose_power_now(
    local_kw: float | None,
    amperium_kw: float | None,
    live_kw: float | None = None,
) -> tuple[float | None, str | None]:
    """Pick the "power now" value and say where it came from.

    Order: the user's own Home Assistant power sensor, then Amperium's live feed,
    then Amperium's hourly value (``currentActivePowerImport``). A reading of 0.0
    counts as a reading. Returns (kW, source) with source "local_sensor",
    "amperium_live", "amperium" or None.
    """
    if local_kw is not None:
        return local_kw, "local_sensor"
    if live_kw is not None:
        return live_kw, "amperium_live"
    if amperium_kw is not None:
        return amperium_kw, "amperium"
    return None, None


class ChangeGate:
    """Say whether a value differs from the last one it was asked about.

    Used to skip state writes that would repeat what is already shown.
    """

    _UNSET = object()

    def __init__(self) -> None:
        """Start with nothing remembered, so the first value always counts as changed."""
        self._last: Any = self._UNSET

    def changed(self, value: Any) -> bool:
        """Remember ``value``; True unless it equals the previous one."""
        if self._last is not self._UNSET and value == self._last:
            return False
        self._last = value
        return True


def days_until(timestamp: Any, now: dt.datetime) -> float | None:
    """Days from ``now`` until an ISO-8601 timestamp (None if unknown/invalid)."""
    if not isinstance(timestamp, str):
        return None
    try:
        when = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return (when - now).total_seconds() / 86400


def consumer_price(spot: Any, surcharge: Any, vat_percent: Any) -> float | None:
    """Price per kWh the consumer pays: (spot + surcharge) incl. VAT.

    The VAT percentage comes from the API (never hardcoded). A missing
    surcharge counts as 0; a missing spot price or VAT percentage gives None.
    Derived, not confirmed by Amperium.
    """
    if spot is None or vat_percent is None:
        return None
    try:
        return (float(spot) + float(surcharge or 0)) * (1 + float(vat_percent) / 100)
    except (TypeError, ValueError):
        return None


SIGNAL_STATES = {0: "none", 1: "poor", 2: "fair", 3: "good", 4: "excellent"}


def han_signal_state(signal: Any, online: Any) -> str | None:
    """Map the HAN module's cellular signal (0-4) and online flag to a state.

    Mirrors the official app: offline wins, then "no data" when the signal is
    missing, otherwise 0=none, 1=poor, 2=fair, 3=good, 4=excellent (the app's
    icon picker also treats a higher number as a stronger signal).
    """
    if online is False:
        return "offline"
    if signal is None:
        return "no_data"
    try:
        return SIGNAL_STATES.get(int(signal))
    except (TypeError, ValueError):
        return None


def _iso_z(value: dt.datetime) -> str:
    """Format an aware datetime as ISO-8601 UTC with a trailing Z."""
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def summarise_energy(
    buckets: list[dict[str, Any]],
    now: dt.datetime,
    tz: dt.tzinfo,
    day_start: int,
    day_end: int,
) -> dict[str, Any]:
    """Aggregate hourly consumption into the sensor values we expose.

    "Day" is local hours day_start <= hour < day_end, "night" is the rest.
    Weekends and holidays are not treated specially.
    """
    hours = complete_hours(buckets, now)
    if not hours:
        return {}
    now_local = now.astimezone(tz)
    prev_start, this_start, _ = local_month_bounds(now_local)
    yesterday = (now_local - dt.timedelta(days=1)).date()

    today = now_local.date()
    out: dict[str, Any] = {
        "energy_last_hour": hours[-1]["import"],
        # One entry per complete local hour today, for charts (e.g. ApexCharts).
        "consumption_today": [
            {
                "start": _iso_z(b["start"]),
                "end": _iso_z(b["end"]),
                "kwh": b["import"],
            }
            for b in hours
            if b["start"].astimezone(tz).date() == today
        ],
    }
    yesterday_sum = month_day = month_night = last_month = 0.0
    have_yesterday = have_month = have_last = False
    for bucket in hours:
        local = bucket["start"].astimezone(tz)
        value = bucket["import"]
        if local.date() == yesterday:
            yesterday_sum += value
            have_yesterday = True
        if (local.year, local.month) == (this_start.year, this_start.month):
            have_month = True
            if day_start <= local.hour < day_end:
                month_day += value
            else:
                month_night += value
        elif (local.year, local.month) == (prev_start.year, prev_start.month):
            last_month += value
            have_last = True
    if have_yesterday:
        out["energy_yesterday"] = yesterday_sum
    if have_month:
        out["energy_day_month"] = month_day
        out["energy_night_month"] = month_night
    if have_last:
        out["energy_last_month"] = last_month
    return out


def capacity_peaks(
    buckets: list[dict[str, Any]], now: dt.datetime, tz: dt.tzinfo, count: int = 3
) -> dict[str, Any]:
    """Estimate the capacity basis from hourly consumption.

    Finnas Kraftlag's tariff (2026): the tier is set by the average of the
    three highest hourly consumptions on three different days in the billing
    month. An hour's kWh equals its average kW. For each local day the
    highest hour is found, then the ``count`` highest of those day peaks are
    averaged. Amperium's own value (gridRent.capacityChargeAveragePower) stays
    the authority; this shows which hours are the peaks and what a new day
    must beat to enter the top three.
    """
    now_local = now.astimezone(tz)
    _, this_start, _ = local_month_bounds(now_local)
    best: dict[dt.date, dict[str, Any]] = {}
    for bucket in complete_hours(buckets, now):
        local = bucket["start"].astimezone(tz)
        if (local.year, local.month) != (this_start.year, this_start.month):
            continue
        day = local.date()
        current = best.get(day)
        if current is None or bucket["import"] > current["kw"]:
            best[day] = {
                "date": day.isoformat(),
                "hour_start": _iso_z(bucket["start"]),
                "kw": bucket["import"],
            }
    if not best:
        return {}
    ranked = sorted(best.values(), key=lambda p: p["kw"], reverse=True)[:count]
    return {
        "capacity_calc_kw": sum(p["kw"] for p in ranked) / len(ranked),
        # What a new day's peak must exceed to enter the top three (0 while
        # fewer than three days have data).
        "capacity_threshold_kw": ranked[-1]["kw"] if len(ranked) == count else 0.0,
        "capacity_peaks": ranked,
        "capacity_peak_days": len(best),
    }


def summarise_charges(
    buckets: list[dict[str, Any]], now: dt.datetime, tz: dt.tzinfo
) -> dict[str, Any]:
    """Aggregate hourly charges: yesterday's cost and this month's support."""
    hours = complete_hours(buckets, now)
    if not hours:
        return {}
    now_local = now.astimezone(tz)
    _, this_start, _ = local_month_bounds(now_local)
    yesterday = (now_local - dt.timedelta(days=1)).date()

    out: dict[str, Any] = {}
    cost = gross = tax = norgespris = 0.0
    have_cost = have_month = False
    for bucket in hours:
        local = bucket["start"].astimezone(tz)
        if local.date() == yesterday:
            cost += bucket["energy"]
            have_cost = True
        if (local.year, local.month) == (this_start.year, this_start.month):
            gross += bucket["energy"]
            tax += bucket["tax"]
            norgespris += bucket["norgespris"]
            have_month = True
    if have_cost:
        out["cost_yesterday"] = cost
    if have_month:
        out["energy_gross_month"] = gross
        out["vat_month"] = tax
        out["norgespris_month"] = norgespris
    return out


def summarise_grid(
    resp: dict[str, Any] | None, suffix: str = ""
) -> dict[str, Any]:
    """Turn the charges response's grid/fixed/capacity parts into sensor values.

    ``suffix`` is "" for this month and "_last_month" for the previous one.
    """
    if not resp or not resp.get("grid"):
        return {}
    grid = resp["grid"]
    out: dict[str, Any] = {
        f"grid_total{suffix}": grid["total"],
        f"grid_compensation{suffix}": grid["compensation"],
        f"fixed_total{suffix}": resp.get("fixed_total"),
        f"capacity_avg_kw{suffix}": grid["capacity_avg_kw"],
        f"capacity_amount{suffix}": grid["capacity_amount"],
        f"grid_breakdown{suffix}": {
            "capacity_charge": grid["capacity_amount"],
            "energy_day": grid["energy_day"],
            "energy_night": grid["energy_night"],
            "electricity_fee": grid["electricity_fee"],
            "enova_fee": grid["enova_fee"],
            "membership_discount": grid["membership_discount"],
            "subsidy_applied": subsidy_applied(grid["compensation"]),
            "vat_included": grid["sales_tax"],
        },
    }
    out.update(_capacity_tier(grid, resp.get("capacity_intervals") or [], suffix))
    out[f"grid_energy_day_kwh{suffix}"] = grid.get("energy_day_kwh")
    out[f"grid_energy_night_kwh{suffix}"] = grid.get("energy_night_kwh")
    if suffix == "_last_month":
        # Month-level figures for the previous month come from this response;
        # /api/sites only reports the current month.
        outer, total = resp.get("outer_total"), grid["total"]
        out["cost_last_month"] = outer
        out["cost_grid_rent_last_month"] = total
        out["cost_energy_last_month"] = (
            outer - total if outer is not None and total is not None else None
        )
    return out


def _capacity_tier(
    grid: dict[str, Any], intervals: list[dict[str, Any]], suffix: str
) -> dict[str, Any]:
    """Describe the current capacity tier and the distance to the next one."""
    avg, tier_min, tier_max = (
        grid["capacity_avg_kw"], grid["capacity_min_kw"], grid["capacity_max_kw"]
    )
    ordered = sorted(
        (i for i in intervals if i.get("min") is not None), key=lambda i: i["min"]
    )
    next_tier = None
    for index, tier in enumerate(ordered):
        if tier["min"] == tier_min and index + 1 < len(ordered):
            next_tier = ordered[index + 1]
            break
    headroom = None
    if avg is not None and tier_max is not None:
        headroom = tier_max - avg
    return {
        f"capacity_headroom_kw{suffix}": headroom,
        f"capacity_details{suffix}": {
            "tier_from_kw": tier_min,
            "tier_to_kw": tier_max,
            "tier_amount": grid["capacity_amount"],
            "next_tier_from_kw": next_tier["min"] if next_tier else None,
            "next_tier_amount": next_tier["amount"] if next_tier else None,
            "extra_cost_next_tier": (
                next_tier["amount"] - grid["capacity_amount"]
                if next_tier
                and next_tier["amount"] is not None
                and grid["capacity_amount"] is not None
                else None
            ),
            "tiers": [
                {"from_kw": t["min"], "to_kw": t["max"], "amount": t["amount"]}
                for t in ordered
            ],
        },
    }


def subsidy_applied(compensation: Any) -> float | None:
    """The straumstotte applied in the grid rent, as a positive amount.

    Amperium has been seen to report it as a positive number; an earlier
    reading suggested a negative one. It is always a deduction, so the sign
    is ignored: the magnitude is what counts.
    """
    if compensation is None:
        return None
    return abs(float(compensation))


def add_amounts(*values: Any) -> float | None:
    """Sum amounts; None if any of them is missing."""
    if any(v is None for v in values):
        return None
    return sum(float(v) for v in values)


def gross_grid_rent(grid_total: Any, compensation: Any) -> float | None:
    """Grid rent (incl. capacity charge) BEFORE straumstotte.

    gridRent.totalAmount is after the subsidy, so the subsidy is added back:
    gross = total + |compensation| (sign-independent, see subsidy_applied).
    """
    if grid_total is None or compensation is None:
        return None
    return float(grid_total) + abs(float(compensation))


def gross_grid_from_net(
    grid_after: Any, compensation: Any, fallback_total: Any = None
) -> float | None:
    """This month's grid rent BEFORE subsidy, built on the figure shown as "after".

    "After" comes from /api/sites (every poll) and the subsidy from the charges
    response (hourly). Adding the subsidy to the very figure that is shown as
    "after" makes "before - subsidy = after" hold exactly, whatever the age of
    the two sources. ``fallback_total`` (the charges response's own total) is
    used only while /api/sites has no figure. Last month has no /api/sites
    figure and keeps using ``gross_grid_rent``.
    """
    if grid_after is None:
        grid_after = fallback_total
    if grid_after is None or compensation is None:
        return None
    return float(grid_after) + subsidy_applied(compensation)


def gross_total_from_net(total_after: Any, fixed_total: Any, compensation: Any) -> float | None:
    """This month's total BEFORE subsidy, including the fixed fee.

    = total after subsidy (/api/sites) + fixed fee + subsidy, so that
    "total before - subsidy - fixed fee = total after" holds exactly.
    """
    if compensation is None:
        return None
    return add_amounts(total_after, fixed_total, subsidy_applied(compensation))


def net_with_subsidy(site_total: Any, fixed_total: Any) -> float | None:
    """Total cost for a customer on the regular subsidy.

    /api/sites totalAmount (energy + grid rent) is already after straumstotte
    but excludes the fixed monthly fee, so only the fixed fee is added.
    """
    return add_amounts(site_total, fixed_total)


def net_with_norgespris(
    site_total: Any, fixed_total: Any, subsidy: Any, norgespris: Any
) -> float | None:
    """Total cost for a Norgespris customer.

    Start from the after-subsidy total, add the straumstotte back (it does
    not apply on Norgespris) and subtract the Norgespris compensation.
    """
    if None in (site_total, fixed_total, subsidy, norgespris):
        return None
    return float(site_total) + float(fixed_total) + float(subsidy) - float(norgespris)


def compensation_for_scheme(scheme: Any, norgespris: Any, subsidy: Any) -> float | None:
    """Return the compensation amount for the chosen scheme (None if unset)."""
    if scheme == "norgespris":
        value = norgespris
    elif scheme == "subsidy":
        value = subsidy
    else:
        return None
    return None if value is None else float(value)


def net_for_scheme(
    scheme: Any, site_total: Any, fixed_total: Any, subsidy: Any, norgespris: Any
) -> float | None:
    """Total cost for the scheme the customer has chosen."""
    if scheme == "norgespris":
        return net_with_norgespris(site_total, fixed_total, subsidy, norgespris)
    if scheme == "subsidy":
        return net_with_subsidy(site_total, fixed_total)
    return None


def compensation_difference(norgespris: Any, subsidy: Any) -> float | None:
    """How much more Norgespris compensates than the regular subsidy."""
    if norgespris is None or subsidy is None:
        return None
    return float(norgespris) - float(subsidy)


def build_hourly_statistics(
    buckets: list[dict[str, Any]], key: str, base_sum: float, now: dt.datetime
) -> list[dict[str, Any]]:
    """Turn hourly buckets into cumulative statistics rows.

    Each row's sum continues from base_sum (the sum of the last row that was
    stored before the first bucket), so re-importing an overlapping window
    keeps the chain consistent.
    """
    rows = []
    running = base_sum
    for bucket in complete_hours(buckets, now):
        running += bucket[key]
        rows.append({"start": bucket["start"], "state": running, "sum": running})
    return rows
