"""Constants for the Amperium integration."""
from __future__ import annotations

DOMAIN = "amperium"

# Base URL for the Amperium cloud API (Finnås Kraftlag m.fl.).
BASE_URL = "https://api.amperium.cloud"

# Static application key sent as the `api-key` header on every request.
# This is the public app identifier, the same for all users of the Amperium
# app – it is not a personal secret. It is required in addition to the
# per-user OTP access token.
API_KEY = "pu8egmI9SwiQ7vmnrJ49OyF01s2JAZa4MA640HzsXSs="

# Config entry data keys
CONF_PHONE = "phone"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_SITE_ID = "site_id"
CONF_SITE_NAME = "site_name"

# How often to poll the API (seconds). The HAN meter data updates hourly.
DEFAULT_SCAN_INTERVAL = 900

# Default request timeout (seconds)
REQUEST_TIMEOUT = 30
