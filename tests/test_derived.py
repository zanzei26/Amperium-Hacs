"""Tests for the pure calculation helpers (no Home Assistant needed)."""
from __future__ import annotations

import asyncio
import datetime as dt

import pytest
from zoneinfo import ZoneInfo

from conftest import amqp_feed, api, derived, hourpower

UTC = dt.timezone.utc
COMP = 154.12478544  # October figures from a live account (3 days)


# --- consumer price ---------------------------------------------------------
def test_consumer_price_uses_vat_from_data():
    assert derived.consumer_price(1.0, 0.0, 0) == pytest.approx(1.0)
    assert derived.consumer_price(1.0, 0.0, 15) == pytest.approx(1.15)
    assert derived.consumer_price(1.5892, 0.0392, 25) == pytest.approx(2.0355)


def test_consumer_price_missing_parts():
    assert derived.consumer_price(1.0, None, 25) == pytest.approx(1.25)  # surcharge None -> 0
    assert derived.consumer_price(None, 0.04, 25) is None
    assert derived.consumer_price(1.0, 0.04, None) is None


def test_price_bucket_has_consumer_field():
    bucket = api._normalise_price(
        {"startTime": "a", "endTime": "b", "spotPreliminary": 1.7, "spotOfficial": None,
         "surcharge": 0.04, "salesTaxPercentage": 25}
    )
    assert bucket["official"] is False
    assert bucket["consumer"] == pytest.approx((1.7 + 0.04) * 1.25)


def test_summarise_prices_includes_consumer():
    buckets = [
        api._normalise_price({"startTime": f"s{i}", "endTime": f"e{i}", "spotOfficial": p,
                              "surcharge": 0.04, "salesTaxPercentage": 25})
        for i, p in enumerate((1.0, 2.0, 3.0))
    ]
    out = api.summarise_prices(buckets)
    assert out["price_min_today"] == 1.0 and out["price_max_today"] == 3.0
    assert out["price_min_consumer"] == pytest.approx(1.04 * 1.25)
    assert out["price_avg_consumer"] == pytest.approx((2.04) * 1.25)


# --- subsidy sign and grid rent ----------------------------------------------
@pytest.mark.parametrize("comp", [COMP, -COMP])
def test_subsidy_is_sign_independent(comp):
    assert derived.subsidy_applied(comp) == pytest.approx(COMP)
    assert derived.gross_grid_rent(328.40, comp) == pytest.approx(328.40 + COMP)
    assert derived.net_with_norgespris(684.32, 25, derived.subsidy_applied(comp), 244.13) == pytest.approx(
        684.32 + 25 + COMP - 244.13
    )


def test_net_models_against_live_october_figures():
    assert derived.net_with_subsidy(684.32, 25) == pytest.approx(709.32)
    assert derived.net_with_norgespris(684.32, 25, COMP, 244.13) == pytest.approx(619.31, abs=0.01)
    assert derived.compensation_difference(244.13, COMP) == pytest.approx(90.01, abs=0.01)
    assert derived.net_for_scheme(None, 684.32, 25, COMP, 244.13) is None
    assert derived.net_with_subsidy(None, 25) is None


def test_charges_summary_has_no_subsidy_key():
    now = dt.datetime(2026, 10, 3, 12, 30, tzinfo=UTC)
    bucket = {"start": dt.datetime(2026, 10, 2, 8, tzinfo=UTC), "end": dt.datetime(2026, 10, 2, 9, tzinfo=UTC),
              "energy": 10.0, "tax": 2.0, "norgespris": 4.0}
    out = derived.summarise_charges([bucket], now, dt.timezone.utc)
    assert "subsidy_month" not in out
    assert out["norgespris_month"] == 4.0 and out["energy_gross_month"] == 10.0


def _charges_response(total, comp, outer):
    raw = {
        "energy": [], "totalAmount": outer,
        "gridRent": {"capacityChargeAveragePower": 6.38,
                     "capacityInterval": {"powerMin": 5, "powerMax": 10, "amount": 400},
                     "importedEnergyDay": 104.361, "importedEnergyNight": 53.725,
                     "compensationAmount": comp, "totalAmount": total},
        "fixedCharges": {"totalAmount": 25},
        "capacityChargeIntervals": [{"powerMin": 5, "powerMax": 10, "amount": 400},
                                    {"powerMin": 10, "powerMax": 15, "amount": 525}],
    }

    class Client(api.AmperiumClient):
        async def _request(self, *args, **kwargs):
            return 200, raw

    start = dt.datetime(2026, 9, 30, 22, tzinfo=UTC)
    return asyncio.run(Client(None, "a", "r").async_get_charges(1, start, start + dt.timedelta(days=3)))


def test_grid_summary_capacity_and_day_night():
    out = derived.summarise_grid(_charges_response(328.40, COMP, 684.32), "")
    assert out["capacity_avg_kw"] == 6.38 and out["capacity_amount"] == 400
    assert out["capacity_headroom_kw"] == pytest.approx(3.62)
    assert out["capacity_details"]["next_tier_amount"] == 525
    assert out["grid_energy_day_kwh"] == 104.361 and out["grid_energy_night_kwh"] == 53.725


def test_last_month_figures_come_from_charges_response():
    out = derived.summarise_grid(_charges_response(-139.43, 1794.23, 3912.24), "_last_month")
    assert out["cost_last_month"] == 3912.24
    assert out["cost_grid_rent_last_month"] == -139.43
    assert out["cost_energy_last_month"] == pytest.approx(4051.67)


def test_api_has_no_norgespris_endpoint_any_more():
    assert not hasattr(api.AmperiumClient, "async_get_norgespris_vs_subsidy")


# --- HAN signal -----------------------------------------------------------------
@pytest.mark.parametrize(
    ("signal", "online", "state"),
    [(0, True, "none"), (1, True, "poor"), (2, True, "fair"), (3, True, "good"),
     (4, True, "excellent"), (1, False, "offline"), (None, True, "no_data"), (9, True, None)],
)
def test_han_signal_state(signal, online, state):
    assert derived.han_signal_state(signal, online) == state


# --- hourly power --------------------------------------------------------------
def test_hour_integrator_forecast_and_rollover():
    t0 = dt.datetime(2026, 10, 3, 10, tzinfo=UTC)
    minute = lambda m: t0 + dt.timedelta(minutes=m)  # noqa: E731
    h = hourpower.HourIntegrator()
    h.update(t0, 2.0)
    h.update(minute(30), 6.0)
    snap = h.snapshot(minute(45))
    assert snap["average_so_far_kw"] == pytest.approx((2 * 0.5 + 6 * 0.25) / 0.75)
    assert snap["forecast_kw"] == pytest.approx(4.0)
    h.snapshot(minute(75))
    assert h.last_complete["average_kw"] == pytest.approx(4.0)


def test_power_unit_conversion():
    assert hourpower.to_kw("2500", "W") == 2.5
    assert hourpower.to_kw("2.5", "kW") == 2.5
    assert hourpower.to_kw("unavailable", "W") is None
    assert hourpower.to_kw("5", None) is None


# --- capacity peaks (Finnas tariff 2026: three highest hours on three different days) ---
def _hours(values):
    """values: {(day, hour_local_oslo): kwh} in October 2026 (CEST, UTC+2)."""
    out = []
    for (day, hour), kwh in values.items():
        start = dt.datetime(2026, 10, day, hour, tzinfo=dt.timezone(dt.timedelta(hours=2))).astimezone(UTC)
        out.append({"start": start, "end": start + dt.timedelta(hours=1), "import": kwh, "export": 0.0})
    return out


def test_capacity_peaks_use_three_different_days():
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Europe/Oslo")
    now = dt.datetime(2026, 10, 10, 12, tzinfo=UTC)
    buckets = _hours({
        (1, 8): 9.0, (1, 9): 8.9, (1, 10): 8.8,   # three high hours, same day: only 9.0 counts
        (2, 18): 6.0, (3, 7): 5.0, (4, 12): 3.0, (5, 12): 1.0,
    })
    out = derived.capacity_peaks(buckets, now, tz)
    assert [p["kw"] for p in out["capacity_peaks"]] == [9.0, 6.0, 5.0]
    assert out["capacity_calc_kw"] == pytest.approx((9.0 + 6.0 + 5.0) / 3)
    assert out["capacity_threshold_kw"] == 5.0  # a new day must beat the third highest
    assert out["capacity_peak_days"] == 5
    assert out["capacity_peaks"][0]["date"] == "2026-10-01"


def test_capacity_peaks_with_fewer_than_three_days():
    from zoneinfo import ZoneInfo

    now = dt.datetime(2026, 10, 3, 12, tzinfo=UTC)
    out = derived.capacity_peaks(_hours({(1, 8): 4.0, (2, 8): 2.0}), now, ZoneInfo("Europe/Oslo"))
    assert out["capacity_calc_kw"] == pytest.approx(3.0)
    assert out["capacity_threshold_kw"] == 0.0


def test_capacity_peaks_ignore_previous_month_and_empty():
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Europe/Oslo")
    now = dt.datetime(2026, 10, 3, 12, tzinfo=UTC)
    september = [{"start": dt.datetime(2026, 9, 30, 10, tzinfo=UTC), "end": dt.datetime(2026, 9, 30, 11, tzinfo=UTC),
                  "import": 50.0, "export": 0.0}]
    assert derived.capacity_peaks(september, now, tz) == {}
    assert derived.capacity_peaks([], now, tz) == {}


def test_capacity_peak_day_follows_local_midnight():
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Europe/Oslo")
    now = dt.datetime(2026, 10, 4, 12, tzinfo=UTC)
    # 22:30 UTC on 1 Oct is 00:30 local on 2 Oct, so it belongs to 2 Oct, not 1 Oct.
    late = {"start": dt.datetime(2026, 10, 1, 22, tzinfo=UTC), "end": dt.datetime(2026, 10, 1, 23, tzinfo=UTC),
            "import": 7.0, "export": 0.0}
    early = {"start": dt.datetime(2026, 10, 1, 8, tzinfo=UTC), "end": dt.datetime(2026, 10, 1, 9, tzinfo=UTC),
             "import": 6.0, "export": 0.0}
    out = derived.capacity_peaks([late, early], now, tz)
    assert sorted(p["date"] for p in out["capacity_peaks"]) == ["2026-10-01", "2026-10-02"]


# --- token refresh: never look like a logout unless Amperium says so ----------------
class _ScriptedClient(api.AmperiumClient):
    """Client whose HTTP answers are scripted: path -> list of (status, body)."""

    def __init__(self, script, **kwargs):
        super().__init__(None, **kwargs)
        self._script = {k: list(v) for k, v in script.items()}
        self.calls = []
        self.paths = []  # full paths, with the query string
        self.bodies = []  # JSON bodies sent

    async def _request(self, method, path, **kwargs):
        self.paths.append(path)
        self.bodies.append(kwargs.get("json"))
        self.calls.append((method, path.split("?")[0]))
        key = path.split("?")[0]
        return self._script[key].pop(0)


REFRESH = "/api/accounts/login/refresh-token"


def test_refresh_success_stores_tokens_immediately():
    stored = []
    client = _ScriptedClient(
        {REFRESH: [(200, {"accessToken": "new-a", "refreshToken": "new-r"})]},
        access_token="old-a", refresh_token="old-r",
        on_tokens=stored.append,
    )
    assert asyncio.run(client.refresh()) is True
    assert len(stored) == 1  # stored right away, once
    assert stored[0]["access_token"] == "new-a"
    assert stored[0]["refresh_token"] == "new-r"
    assert (client.access_token, client.refresh_token) == ("new-a", "new-r")


def test_refresh_keeps_old_refresh_token_if_not_rotated():
    client = _ScriptedClient({REFRESH: [(200, {"accessToken": "new-a"})]},
                             access_token="old-a", refresh_token="old-r")
    assert asyncio.run(client.refresh()) is True
    assert client.refresh_token == "old-r"


@pytest.mark.parametrize("status", [400, 401, 403])
def test_refresh_rejected_means_log_in_again(status):
    stored = []
    client = _ScriptedClient({REFRESH: [(status, {"errorCode": 1})]},
                             access_token="a", refresh_token="r",
                             on_tokens=stored.append)
    assert asyncio.run(client.refresh()) is False
    assert stored == []


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_refresh_server_trouble_is_not_a_logout(status):
    client = _ScriptedClient({REFRESH: [(status, None)]}, access_token="a", refresh_token="r")
    with pytest.raises(api.AmperiumError) as err:
        asyncio.run(client.refresh())
    assert not isinstance(err.value, api.AmperiumAuthError)
    assert (client.access_token, client.refresh_token) == ("a", "r")  # untouched


def test_request_retried_after_successful_refresh():
    client = _ScriptedClient(
        {"/api/sites": [(401, None), (200, [{"siteId": 1}])],
         REFRESH: [(200, {"accessToken": "n", "refreshToken": "m"})]},
        access_token="o", refresh_token="p",
    )
    status, data = asyncio.run(client._auth_get("/api/sites"))
    assert (status, data) == (200, [{"siteId": 1}])
    assert [c[1] for c in client.calls] == ["/api/sites", REFRESH, "/api/sites"]


def test_expired_refresh_token_ends_as_auth_error():
    client = _ScriptedClient({"/api/sites": [(401, None)], REFRESH: [(400, {"errorCode": 7})]},
                             access_token="o", refresh_token="p")
    with pytest.raises(api.AmperiumAuthError):
        asyncio.run(client.async_get_sites())


def test_server_trouble_during_refresh_is_not_auth_error():
    client = _ScriptedClient({"/api/sites": [(401, None)], REFRESH: [(503, None)]},
                             access_token="o", refresh_token="p")
    with pytest.raises(api.AmperiumError) as err:
        asyncio.run(client.async_get_sites())
    assert not isinstance(err.value, api.AmperiumAuthError)


# --- v0.9.1: expiry times, one refresh at a time -----------------------------------
def test_refresh_stores_expiry_times_from_the_response():
    stored = []
    client = _ScriptedClient(
        {REFRESH: [(200, {
            "accessToken": "new-a", "refreshToken": "new-r",
            "accessTokenExpiresAt": "2026-10-08T12:00:00Z",
            "refreshTokenExpiresAt": "2027-10-03T12:00:00Z",
        })]},
        access_token="old-a", refresh_token="old-r",
        access_expires_at="2026-10-03T12:00:00Z", refresh_expires_at="2027-10-01T12:00:00Z",
        on_tokens=stored.append,
    )
    assert asyncio.run(client.refresh()) is True
    assert stored[0] == {
        "access_token": "new-a", "refresh_token": "new-r",
        "access_expires_at": "2026-10-08T12:00:00Z",
        "refresh_expires_at": "2027-10-03T12:00:00Z",
    }
    assert client.tokens() == stored[0]


def test_refresh_keeps_known_expiry_if_response_has_none():
    client = _ScriptedClient(
        {REFRESH: [(200, {"accessToken": "new-a"})]},
        access_token="o", refresh_token="r",
        access_expires_at="2026-10-03T12:00:00Z", refresh_expires_at="2027-10-01T12:00:00Z",
    )
    assert asyncio.run(client.refresh()) is True
    assert client.refresh_expires_at == "2027-10-01T12:00:00Z"
    assert client.access_expires_at == "2026-10-03T12:00:00Z"


def test_login_response_sets_tokens_and_expiry():
    client = _ScriptedClient({"/api/accounts/login/otp": [(200, {
        "accessToken": "a", "refreshToken": "r",
        "accessTokenExpiresAt": "2026-10-08T12:00:00Z",
        "refreshTokenExpiresAt": "2027-10-03T12:00:00Z",
    })]})
    asyncio.run(client.login_otp("12345678", "1234"))
    assert client.tokens() == {
        "access_token": "a", "refresh_token": "r",
        "access_expires_at": "2026-10-08T12:00:00Z",
        "refresh_expires_at": "2027-10-03T12:00:00Z",
    }


class _YieldingClient(_ScriptedClient):
    """Like _ScriptedClient, but lets other tasks run during every request."""

    async def _request(self, method, path, **kwargs):
        await asyncio.sleep(0)
        return await super()._request(method, path, **kwargs)


def test_simultaneous_401s_cause_exactly_one_refresh():
    client = _YieldingClient(
        {"/api/sites": [(401, None), (401, None), (200, [{"siteId": 1}]), (200, [{"siteId": 1}])],
         REFRESH: [(200, {"accessToken": "n", "refreshToken": "m"})]},
        access_token="o", refresh_token="p",
    )

    async def both():
        return await asyncio.gather(client._auth_get("/api/sites"), client._auth_get("/api/sites"))

    results = asyncio.run(both())
    assert results == [(200, [{"siteId": 1}]), (200, [{"siteId": 1}])]
    refreshes = [c for c in client.calls if c[1] == REFRESH]
    assert len(refreshes) == 1  # the second request reused the new token
    assert client.access_token == "n"


def test_simultaneous_401s_with_rejected_refresh_both_end_as_auth_error():
    client = _YieldingClient(
        {"/api/sites": [(401, None), (401, None)],
         REFRESH: [(400, {"errorCode": 7}), (400, {"errorCode": 7})]},
        access_token="o", refresh_token="p",
    )

    async def both():
        return await asyncio.gather(client.async_get_sites(), client.async_get_sites(),
                                    return_exceptions=True)

    results = asyncio.run(both())
    assert all(isinstance(r, api.AmperiumAuthError) for r in results)


# --- days_until (login expiry warning) --------------------------------------------
NOW = dt.datetime(2026, 10, 3, 12, tzinfo=UTC)


def test_days_until_counts_whole_and_part_days():
    assert derived.days_until("2026-10-13T12:00:00Z", NOW) == pytest.approx(10.0)
    assert derived.days_until("2026-10-03T18:00:00Z", NOW) == pytest.approx(0.25)
    assert derived.days_until("2026-10-01T12:00:00Z", NOW) == pytest.approx(-2.0)  # already past


def test_days_until_handles_offsets_and_naive_stamps():
    assert derived.days_until("2026-10-13T14:00:00+02:00", NOW) == pytest.approx(10.0)
    assert derived.days_until("2026-10-13T12:00:00", NOW) == pytest.approx(10.0)  # taken as UTC


@pytest.mark.parametrize("bad", [None, "", "not a date", 12345])
def test_days_until_unknown_is_none(bad):
    assert derived.days_until(bad, NOW) is None


# --- month starts at local midnight, not 00:00 UTC ---------------------------------
OSLO = ZoneInfo("Europe/Oslo")


def _sites_query(month_start):
    client = _ScriptedClient({"/api/sites": [(200, [])]}, access_token="a", refresh_token="r")
    asyncio.run(client.async_get_sites(month_start))
    return client.paths[0]


def test_sites_month_starts_at_local_midnight_in_summer_time():
    start = derived.local_month_bounds(dt.datetime(2026, 10, 3, 19, 45, tzinfo=OSLO))[1]
    # 1 October 00:00 in Oslo (UTC+2) is 22:00 UTC on 30 September, not 00:00 UTC.
    assert "charges_from=2026-09-30T22:00:00Z" in _sites_query(start)


def test_sites_month_starts_at_local_midnight_in_winter_time():
    start = derived.local_month_bounds(dt.datetime(2026, 12, 5, 12, tzinfo=OSLO))[1]
    assert "charges_from=2026-11-30T23:00:00Z" in _sites_query(start)  # UTC+1


def test_sites_month_start_is_independent_of_the_tz_it_is_given_in():
    in_utc = dt.datetime(2026, 9, 30, 22, tzinfo=UTC)
    in_oslo = dt.datetime(2026, 10, 1, 0, tzinfo=OSLO)
    assert _sites_query(in_utc).split("&")[0] == _sites_query(in_oslo).split("&")[0]


def test_sites_without_month_start_keeps_the_old_utc_month():
    query = _sites_query(None)
    assert "charges_from=" in query and "T00:00:00Z&" in query


def test_local_month_bounds_across_the_clock_change():
    # The clocks go back on 25 October 2026: October starts at UTC+2, November at UTC+1.
    prev, this, nxt = derived.local_month_bounds(dt.datetime(2026, 11, 10, 12, tzinfo=OSLO))
    assert prev.astimezone(UTC) == dt.datetime(2026, 9, 30, 22, tzinfo=UTC)
    assert this.astimezone(UTC) == dt.datetime(2026, 10, 31, 23, tzinfo=UTC)
    assert nxt.astimezone(UTC) == dt.datetime(2026, 11, 30, 23, tzinfo=UTC)


# --- "power now": local sensor first, Amperium as fallback ----------------------------
def test_power_now_prefers_the_local_sensor():
    assert derived.choose_power_now(2.5, 0.0) == (2.5, "local_sensor")


def test_power_now_local_zero_is_a_real_reading():
    # 0.0 kW from the local sensor must not be mistaken for "no value".
    assert derived.choose_power_now(0.0, 1.2) == (0.0, "local_sensor")


def test_power_now_falls_back_to_amperium_when_local_is_missing():
    assert derived.choose_power_now(None, 1.2) == (1.2, "amperium")


def test_power_now_without_any_value():
    assert derived.choose_power_now(None, None) == (None, None)


def test_power_now_local_value_from_the_live_tracker_units():
    # The tracker hands over kW already converted by to_kw (W, kW and MW supported).
    assert derived.choose_power_now(hourpower.to_kw("2500", "W"), None) == (2.5, "local_sensor")
    assert derived.choose_power_now(hourpower.to_kw("unavailable", "W"), 0.4) == (0.4, "amperium")


# --- before/after subsidy must add up (live figures from 3 October) -------------------
def test_grid_before_minus_subsidy_equals_after():
    before = derived.gross_grid_from_net(326.87, 154.12 + 5.07, 326.12)  # comp = 159.19
    assert before == pytest.approx(326.87 + 159.19)
    assert before == pytest.approx(486.06)
    assert before - derived.subsidy_applied(159.19) == pytest.approx(326.87)  # = "after", exactly


def test_grid_gross_does_not_depend_on_the_age_of_the_charges_total():
    # charges said 326.12 an hour ago; /api/sites says 326.87 now. "After" wins.
    assert derived.gross_grid_from_net(326.87, 159.19, 326.12) == pytest.approx(486.06)


def test_grid_gross_falls_back_to_charges_total_without_site_figure():
    assert derived.gross_grid_from_net(None, 159.19, 326.12) == pytest.approx(485.31)


@pytest.mark.parametrize("compensation", [159.19, -159.19])
def test_grid_gross_is_sign_independent(compensation):
    assert derived.gross_grid_from_net(326.87, compensation) == pytest.approx(486.06)


def test_grid_gross_unknown_without_subsidy_or_figures():
    assert derived.gross_grid_from_net(326.87, None) is None
    assert derived.gross_grid_from_net(None, 159.19) is None


def test_total_before_minus_subsidy_minus_fixed_equals_total_after():
    total_after, fixed, comp = 689.56, 25.0, 159.19
    gross = derived.gross_total_from_net(total_after, fixed, comp)
    assert gross == pytest.approx(873.75)
    assert gross - derived.subsidy_applied(comp) - fixed == pytest.approx(total_after)


def test_total_gross_equals_energy_plus_gross_grid_plus_fixed():
    energy, grid_after, fixed, comp = 362.69, 326.87, 25.0, 159.19
    via_parts = energy + derived.gross_grid_from_net(grid_after, comp) + fixed
    assert derived.gross_total_from_net(energy + grid_after, fixed, comp) == pytest.approx(via_parts)


def test_total_gross_unknown_when_a_part_is_missing():
    assert derived.gross_total_from_net(689.56, None, 159.19) is None
    assert derived.gross_total_from_net(None, 25.0, 159.19) is None
    assert derived.gross_total_from_net(689.56, 25.0, None) is None


def test_last_month_still_uses_charges_figures():
    assert derived.gross_grid_rent(-139.97, 100.0) == pytest.approx(-39.97)


# --- "power now" with the Amperium live feed in between --------------------------------
def test_power_now_order_local_then_live_then_hourly():
    assert derived.choose_power_now(2.5, 0.0, 1.9) == (2.5, "local_sensor")
    assert derived.choose_power_now(None, 0.0, 1.9) == (1.9, "amperium_live")
    assert derived.choose_power_now(None, 0.4, None) == (0.4, "amperium")
    assert derived.choose_power_now(None, None, None) == (None, None)


def test_power_now_live_zero_is_a_real_reading():
    assert derived.choose_power_now(None, 1.2, 0.0) == (0.0, "amperium_live")


# --- live feed: routing keys and messages (as read from the app's code) -----------------
@pytest.mark.parametrize("key,expected", [
    ("AMPMETER-ABC123.O.101", ("AMPMETER-ABC123", 101)),
    ("MID.O.102", ("MID", 102)),
    ("MID.O.101.extra", ("MID", 101)),
    ("MID.P", None),           # pulse
    ("MID.C.5", None),         # command
    ("MID.O.x", None),         # id is not a number
    ("MID", None),
    ("", None),
    (None, None),
    (101, None),
])
def test_routing_key(key, expected):
    assert amqp_feed.parse_routing_key(key) == expected


def test_observation_json_variants():
    when = dt.datetime(2026, 10, 3, 19, 0, 5, tzinfo=UTC)
    assert amqp_feed.parse_observation(b'{"Timestamp":"2026-10-03T19:00:05Z","Value":1351.0}') == (when, 1351.0)
    assert amqp_feed.parse_observation(b'{"timestamp":"2026-10-03T19:00:05Z","value":1351}') == (when, 1351.0)
    assert amqp_feed.parse_observation(b'{"t":"2026-10-03T19:00:05Z","v":"1351.5"}') == (when, 1351.5)
    assert amqp_feed.parse_observation(b'[{"v":1},{"v":2}]')[1] == 2.0  # last item of a list
    assert amqp_feed.parse_observation('{"Value": 0}'.encode())[1] == 0.0  # zero is a value


@pytest.mark.parametrize("body", [b"", b"not json", b"{}", b"[]", b'{"Value": null}',
                                  b'{"Value": "abc"}', b'{"Value": true}', b"\xff\xfe", b"42"])
def test_observation_garbage_gives_no_value(body):
    assert amqp_feed.parse_observation(body)[1] is None


# --- live feed: state ---------------------------------------------------------------------
def test_state_reading_goes_stale():
    state = amqp_feed.LiveFeedState()
    t0 = dt.datetime(2026, 10, 3, 19, 0, tzinfo=UTC)
    assert state.current_kw(t0) is None
    state.set_import(1.35, None, t0)
    assert state.current_kw(t0 + dt.timedelta(seconds=119)) == 1.35
    assert state.current_kw(t0 + dt.timedelta(seconds=121)) is None  # older than 120 s
    assert state.age_seconds(t0 + dt.timedelta(seconds=10)) == 10


def test_state_zero_is_kept_not_treated_as_missing():
    state = amqp_feed.LiveFeedState()
    t0 = dt.datetime(2026, 10, 3, 19, 0, tzinfo=UTC)
    state.set_import(0.0, None, t0)
    assert state.current_kw(t0) == 0.0


def test_state_listeners_hear_changes_and_can_leave():
    state, heard = amqp_feed.LiveFeedState(), []
    remove = state.add_listener(lambda: heard.append(state.status))
    state.set_status("connecting")
    state.set_status("connecting")      # no change -> no call
    state.set_status("connected")
    remove()
    state.set_status("error")
    assert heard == ["connecting", "connected"]


# --- live feed: the loop, with a fake client and a fake queue -----------------------------
class _FakeClient:
    """Hands out scripted subscriptions (or errors) like async_create_live_subscription."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    async def async_create_live_subscription(self, site_id, **kwargs):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _sub(history=None):
    return api.LiveSubscription(
        details={"server": "mq.example.test", "port": 5671, "useSsl": True, "virtualHost": "vh",
                 "username": "user-secret", "password": "pw-secret", "queueName": "queue-secret",
                 "exchangeName": "exchange-secret"},
        import_observations=history or [],
    )


def _run_feed(client, consume, *, library=True, stop_after_sleeps=1):
    """Run the feed until it has slept ``stop_after_sleeps`` times; return (feed, sleeps)."""
    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) >= stop_after_sleeps:
            raise asyncio.CancelledError

    async def ensure():
        return library

    feed = amqp_feed.AmperiumLiveFeed(client, 215, consume=consume, ensure_library=ensure, sleep=sleep)

    async def go():
        try:
            await feed.run()
        except asyncio.CancelledError:
            pass

    asyncio.run(go())
    return feed, sleeps


def test_feed_stores_power_in_kw_from_messages():
    async def consume(details, on_message):
        on_message("AMPMETER-X.O.101", b'{"Timestamp":"2026-10-03T19:00:05Z","Value":1351}')
        on_message("AMPMETER-X.O.102", b'{"Value":999}')       # export: ignored
        on_message("AMPMETER-X.O.101", b'{"Value":1349.5}')

    feed, _ = _run_feed(_FakeClient([_sub()]), consume)
    assert feed.state.import_kw == pytest.approx(1.3495)
    assert feed.state.messages == 2


def test_feed_uses_newest_buffered_reading_from_the_subscription():
    old = (dt.datetime.now(UTC) - dt.timedelta(seconds=30), 1000.0)
    new = (dt.datetime.now(UTC) - dt.timedelta(seconds=5), 2500.0)

    async def consume(details, on_message):
        return None

    feed, _ = _run_feed(_FakeClient([_sub([old, new])]), consume)
    assert feed.state.import_kw == pytest.approx(2.5)


def test_feed_without_the_library_stays_off_and_never_subscribes():
    client = _FakeClient([])
    feed, sleeps = _run_feed(client, lambda *a: None, library=False)
    assert feed.state.status == "unavailable"
    assert client.calls == 0 and sleeps == []


def test_feed_backs_off_after_errors_and_gives_the_error_without_secrets(caplog):
    client = _FakeClient([api.AmperiumError("HTTP 503"), api.AmperiumError("HTTP 503")])

    async def consume(details, on_message):
        raise AssertionError("never reached")

    state, seen = amqp_feed.LiveFeedState(), []
    state.add_listener(lambda: seen.append(state.status))
    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) >= 2:
            raise asyncio.CancelledError

    async def ensure():
        return True

    feed = amqp_feed.AmperiumLiveFeed(client, 215, state=state, consume=consume,
                                      ensure_library=ensure, sleep=sleep)

    async def go():
        try:
            await feed.run()
        except asyncio.CancelledError:
            pass

    with caplog.at_level("WARNING"):
        asyncio.run(go())
    assert sleeps == [5, 15]
    assert seen[:3] == ["starting", "connecting", "error"]  # went to "error" while failing
    assert seen[-1] == "off"                                 # and "off" once stopped
    assert "HTTP 503" in state.last_error


def test_feed_errors_from_the_connection_never_show_credentials(caplog):
    client = _FakeClient([_sub()])

    async def consume(details, on_message):
        raise ConnectionError(
            "failed amqps://user-secret:pw-secret@mq.example.test:5671/vh queue-secret exchange-secret"
        )

    with caplog.at_level("DEBUG"):
        feed, _ = _run_feed(client, consume)
    shown = feed.state.last_error + caplog.text
    for secret in ("user-secret", "pw-secret", "mq.example.test", "queue-secret", "exchange-secret"):
        assert secret not in shown
    assert "ConnectionError" in feed.state.last_error


def test_subscription_repr_hides_the_connection_details():
    assert "pw-secret" not in repr(_sub()) and "user-secret" not in repr(_sub())


def test_feed_subscribes_again_when_the_connection_ends():
    client = _FakeClient([_sub(), _sub()])
    calls = []

    async def consume(details, on_message):
        calls.append(1)

    feed, sleeps = _run_feed(client, consume, stop_after_sleeps=2)
    assert client.calls == 2 and len(calls) == 2
    assert sleeps == [5, 15]  # no message arrived, so it counts as a failed session


def test_feed_resubscribes_when_nothing_arrives_for_too_long(monkeypatch):
    monkeypatch.setattr(amqp_feed, "TICK_SECONDS", 0.01)
    monkeypatch.setattr(amqp_feed, "IDLE_RESUBSCRIBE_SECONDS", 0.03)
    client = _FakeClient([_sub()])
    cancelled = []

    async def consume(details, on_message):
        try:
            await asyncio.sleep(30)  # a quiet queue
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    feed, sleeps = _run_feed(client, consume)
    assert cancelled == [True]  # the idle listener was dropped
    assert sleeps == [5]
    assert feed.state.messages == 0


# --- live subscription call (POST /api/sites/{id}/stream/amqp) -------------------------------
STREAM = "/api/sites/215/stream/amqp"
DETAILS = {"server": "mq.example.test", "port": 5671, "useSsl": True, "virtualHost": "vh",
           "username": "u", "password": "p", "queueName": "q", "exchangeName": "x"}


def test_live_subscription_sends_what_the_app_sends_and_parses_the_answer():
    client = _ScriptedClient({STREAM: [(200, {
        "activePowerPositive": [{"timestamp": "2026-10-03T19:00:10Z", "value": 1400.0},
                                {"timestamp": "2026-10-03T19:00:00Z", "value": 1300.0}],
        "activePowerNegative": [],
        "liveConnectionDetails": DETAILS,
    })]}, access_token="a", refresh_token="r")
    sub = asyncio.run(client.async_create_live_subscription(215))
    body = client.bodies[0]
    assert body["includeActivePowerPositive"] is True
    assert body["includeActivePowerNegative"] is False
    assert body["liveFeedTtlInSeconds"] == 300
    initial = dt.datetime.fromisoformat(body["initializeFrom"].replace("Z", "+00:00"))
    assert 170 <= (dt.datetime.now(UTC) - initial).total_seconds() <= 190  # 180 s back
    assert sub.details == DETAILS
    assert [v for _, v in sub.import_observations] == [1300.0, 1400.0]  # oldest first
    assert sub.export_observations == []


def test_live_subscription_with_empty_history_is_fine():
    client = _ScriptedClient({STREAM: [(200, {"activePowerPositive": [], "activePowerNegative": [],
                                              "liveConnectionDetails": DETAILS})]})
    assert asyncio.run(client.async_create_live_subscription(215)).import_observations == []


def test_live_subscription_401_is_an_auth_error_and_never_refreshes():
    client = _ScriptedClient({STREAM: [(401, None)]}, access_token="a", refresh_token="r")
    with pytest.raises(api.AmperiumAuthError):
        asyncio.run(client.async_create_live_subscription(215))
    assert [c[1] for c in client.calls] == [STREAM]  # no refresh-token call


@pytest.mark.parametrize("status,body", [(500, None), (404, {"title": "x"}), (200, None),
                                          (200, {}), (200, {"liveConnectionDetails": {"server": "s"}})])
def test_live_subscription_bad_answers_are_errors(status, body):
    client = _ScriptedClient({STREAM: [(status, body)]})
    with pytest.raises(api.AmperiumError) as err:
        asyncio.run(client.async_create_live_subscription(215))
    assert not isinstance(err.value, api.AmperiumAuthError)


# --- the aio-pika glue, with a fake library (checks how we call it, not RabbitMQ itself) -----
class _FakeCallbacks:
    def __init__(self):
        self.callbacks = []

    def add(self, callback, weak=False):
        self.callbacks.append(callback)

    def fire(self):
        for callback in self.callbacks:
            callback(None, None)


class _FakeMessage:
    def __init__(self, routing_key, body):
        self.routing_key, self.body = routing_key, body


class _FakeQueue:
    def __init__(self, channel):
        self.channel = channel

    async def consume(self, handler, no_ack=False, **kwargs):
        self.channel.consumed = {"handler": handler, "no_ack": no_ack}


class _FakeChannel:
    def __init__(self):
        self.close_callbacks = _FakeCallbacks()
        self.qos = None
        self.queue_asked = None
        self.consumed = None

    async def set_qos(self, prefetch_count=0, **kwargs):
        self.qos = prefetch_count

    async def get_queue(self, name, *, ensure=True):
        self.queue_asked = (name, ensure)
        return _FakeQueue(self)


class _FakeConnection:
    def __init__(self):
        self.close_callbacks = _FakeCallbacks()
        self.channel_obj = _FakeChannel()
        self.closed = False

    async def channel(self):
        return self.channel_obj

    async def close(self):
        self.closed = True


def test_aio_pika_glue_connects_like_the_app_and_passes_messages_on(monkeypatch):
    import sys
    import types

    connection = _FakeConnection()
    seen = {}

    async def fake_connect(**kwargs):
        seen.update(kwargs)
        return connection

    monkeypatch.setitem(sys.modules, "aio_pika", types.SimpleNamespace(connect=fake_connect))
    got = []
    ssl_context = object()

    async def go():
        task = asyncio.ensure_future(amqp_feed.consume_with_aio_pika(
            dict(DETAILS), lambda key, body: got.append((key, body)), ssl_context=ssl_context))
        for _ in range(5):          # let it connect and start consuming
            await asyncio.sleep(0)
        consumed = connection.channel_obj.consumed
        await consumed["handler"](_FakeMessage("AMPMETER-X.O.101", b'{"Value": 5}'))
        assert not task.done()      # keeps listening until the connection closes
        connection.close_callbacks.fire()
        await asyncio.wait_for(task, 1)

    asyncio.run(go())
    assert (seen["host"], seen["port"], seen["virtualhost"]) == ("mq.example.test", 5671, "vh")
    assert (seen["login"], seen["password"], seen["ssl"]) == ("u", "p", True)
    assert seen["ssl_context"] is ssl_context
    assert connection.channel_obj.queue_asked == ("q", False)   # not declared, like the app
    assert connection.channel_obj.consumed["no_ack"] is True
    assert got == [("AMPMETER-X.O.101", b'{"Value": 5}')]
    assert connection.closed is True


def test_aio_pika_glue_without_tls_uses_the_plain_port_and_no_context(monkeypatch):
    import sys
    import types

    connection, seen = _FakeConnection(), {}

    async def fake_connect(**kwargs):
        seen.update(kwargs)
        return connection

    monkeypatch.setitem(sys.modules, "aio_pika", types.SimpleNamespace(connect=fake_connect))
    details = {"server": "s", "useSsl": False, "queueName": "q", "username": "u", "password": "p"}

    async def go():
        task = asyncio.ensure_future(amqp_feed.consume_with_aio_pika(details, lambda *a: None,
                                                                      ssl_context=object()))
        for _ in range(5):
            await asyncio.sleep(0)
        connection.channel_obj.close_callbacks.fire()   # the channel closing also ends it
        await asyncio.wait_for(task, 1)

    asyncio.run(go())
    assert seen["port"] == 5672 and seen["ssl"] is False and seen["ssl_context"] is None
    assert seen["virtualhost"] == "/"
