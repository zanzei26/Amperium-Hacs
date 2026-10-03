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
# When the tokens expire, as reported by Amperium (ISO-8601 strings). The access
# token lasts 5 days, the refresh token 1 year (seen in a real token response).
CONF_ACCESS_EXPIRES = "access_expires_at"
CONF_REFRESH_EXPIRES = "refresh_expires_at"
# Ask for a new login this many days before the refresh token expires.
REAUTH_WARN_DAYS = 30
ISSUE_LOGIN_EXPIRING = "login_expiring"
CONF_SITE_ID = "site_id"
CONF_SITE_NAME = "site_name"

# How often to poll the API (seconds). The HAN meter data updates hourly.
DEFAULT_SCAN_INTERVAL = 900

# Which compensation scheme the customer is on: Norgespris or the regular
# electricity subsidy (straumstotte). Decides which amount the net cost uses.
# No default: it is asked for at setup and can be changed in the options.
CONF_SCHEME = "scheme"
SCHEME_NORGESPRIS = "norgespris"
SCHEME_SUBSIDY = "subsidy"
SCHEMES = [SCHEME_NORGESPRIS, SCHEME_SUBSIDY]

# Optional existing Home Assistant power sensor (e.g. Tibber Pulse/Watty) for
# live power and the running hourly average. Must measure the whole house for
# the capacity charge to make sense; a charger like Easee does not.
CONF_POWER_ENTITY = "power_entity"

# Whether the customer has a Dobbe module (the HAN sensor that sends the meter
# readings to Amperium). If so, live power can be read from Amperium's own AMQP
# feed, the same one the app's live power view uses. Asked at setup and in the
# options; off by default. Needs the "aio-pika" library, which is installed the
# first time it is switched on.
CONF_HAS_DOBBE = "has_dobbe"
LIVE_REQUIREMENTS = ["aio-pika>=9.0.0"]
# Observation ids on the feed (from the app): active power import / export.
LIVE_OBS_IMPORT = 101
LIVE_OBS_EXPORT = 102
# Lifetime asked for on the subscription (the app asks for 300 s).
LIVE_FEED_TTL_SECONDS = 300
# A live reading older than this is not shown as "now".
LIVE_MAX_AGE_SECONDS = 120

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
