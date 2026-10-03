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

    out: dict[str, Any] = {"energy_last_hour": hours[-1]["import"]}
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
    cost = subsidy = norgespris = 0.0
    have_cost = have_month = False
    for bucket in hours:
        local = bucket["start"].astimezone(tz)
        if local.date() == yesterday:
            cost += bucket["total"]
            have_cost = True
        if (local.year, local.month) == (this_start.year, this_start.month):
            subsidy += bucket["subsidy"]
            norgespris += bucket["norgespris"]
            have_month = True
    if have_cost:
        out["cost_yesterday"] = cost
    if have_month:
        out["subsidy_month"] = subsidy
        out["norgespris_month"] = norgespris
    return out


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
