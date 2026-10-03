"""Constants for the Amperium integration."""
from __future__ import annotations

DOMAIN = "amperium"

# Base URL for the Amperium cloud API (used by the Finnås Kraftlag app "Kraftlaget").
BASE_URL = "https://api.amperium.cloud"

# Static application key sent as the `api-key` header on every request.
# This is the public app identifier, the same for all users of the Amperium
# app – it is not a personal secret. It is required in addition to the
# per-user OTP access token.
API_KEY = "pu8egmI9SwiQ7vmnrJ49OyF01s2JAZa4MA640HzsXSs="

# The official Android app (2.3.0, versionCode 34) identifies itself with the
# header `User-Agent: AmperiumApp/<versionName> (+<platform> ...)`. The server
# can reject unsupported app versions ("Upgrade required"), so we send the
# same product/version. Bump APP_VERSION if Amperium starts rejecting it.
APP_NAME = "AmperiumApp"
APP_VERSION = "2.3.0"
USER_AGENT = f"{APP_NAME}/{APP_VERSION} (+Home Assistant integration)"
ACCEPT_LANGUAGE = "nb-NO"

# Config entry data keys
CONF_PHONE = "phone"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_SITE_ID = "site_id"
CONF_SITE_NAME = "site_name"

# How often to poll the API (seconds). The HAN meter data updates hourly.
DEFAULT_SCAN_INTERVAL = 900

# Hours (local time) counted as "day" for the day/night consumption split.
# Configurable in the integration options. Weekends are not treated specially.
CONF_DAY_START = "day_start"
CONF_DAY_END = "day_end"
DEFAULT_DAY_START = 6
DEFAULT_DAY_END = 22

# Extended data (hourly consumption/charges, support comparison) is heavier,
# so it is fetched less often than the main data.
EXTENDED_SCAN_INTERVAL = 3600

# Default request timeout (seconds)
REQUEST_TIMEOUT = 30
