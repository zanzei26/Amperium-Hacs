"""Tests for the pure calculation helpers (no Home Assistant needed)."""
from __future__ import annotations

import asyncio
import datetime as dt

import pytest

from conftest import api, derived, hourpower

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

    async def _request(self, method, path, **kwargs):
        self.calls.append((method, path.split("?")[0]))
        key = path.split("?")[0]
        return self._script[key].pop(0)


REFRESH = "/api/accounts/login/refresh-token"


def test_refresh_success_stores_tokens_immediately():
    stored = []
    client = _ScriptedClient(
        {REFRESH: [(200, {"accessToken": "new-a", "refreshToken": "new-r"})]},
        access_token="old-a", refresh_token="old-r",
        on_tokens=lambda a, r: stored.append((a, r)),
    )
    assert asyncio.run(client.refresh()) is True
    assert stored == [("new-a", "new-r")]  # stored right away, once
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
                             on_tokens=lambda a, r: stored.append((a, r)))
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
