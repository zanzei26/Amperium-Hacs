"""Config flow for the Amperium integration (passwordless OTP)."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    AmperiumAuthError,
    AmperiumClient,
    AmperiumError,
    AmperiumRateLimitError,
)
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_DAY_END,
    CONF_DAY_START,
    CONF_PHONE,
    CONF_REFRESH_TOKEN,
    CONF_SCHEME,
    CONF_SITE_ID,
    CONF_SITE_NAME,
    DEFAULT_DAY_END,
    DEFAULT_DAY_START,
    DOMAIN,
    SCHEMES,
)

_LOGGER = logging.getLogger(__name__)


class AmperiumConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Amperium OTP config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise flow state."""
        self._phone: str | None = None
        self._client: AmperiumClient | None = None
        self._sites: list[dict[str, Any]] = []
        self._site: dict[str, Any] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow (day/night hours)."""
        return AmperiumOptionsFlow(config_entry)

    # ------------------------------------------------------------------ #
    # Step 1: phone number -> request OTP
    # ------------------------------------------------------------------ #
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the phone number and request an OTP code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            phone = _normalise_phone(user_input[CONF_PHONE])
            session = async_get_clientsession(self.hass)
            client = AmperiumClient(session)
            try:
                await client.request_otp(phone)
            except AmperiumRateLimitError:
                errors["base"] = "too_many_otp"
            except AmperiumError:
                errors["base"] = "request_otp_failed"
            else:
                self._phone = phone
                self._client = client
                return await self.async_step_otp()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_PHONE, default="+47"): str}
            ),
            errors=errors,
            description_placeholders={"example": "+4790000000"},
        )

    # ------------------------------------------------------------------ #
    # Step 2: OTP code -> tokens -> discover sites
    # ------------------------------------------------------------------ #
    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the SMS code and log in."""
        errors: dict[str, str] = {}
        assert self._client is not None and self._phone is not None

        if user_input is not None:
            code = str(user_input["otp"]).strip()
            try:
                await self._client.login_otp(self._phone, code)
                self._sites = await self._client.async_get_sites()
            except AmperiumAuthError:
                errors["base"] = "invalid_otp"
            except AmperiumError:
                errors["base"] = "cannot_connect"
            else:
                if not self._sites:
                    errors["base"] = "no_sites"
                elif len(self._sites) == 1:
                    self._site = self._sites[0]
                    return await self.async_step_scheme()
                else:
                    return await self.async_step_site()

        return self.async_show_form(
            step_id="otp",
            data_schema=vol.Schema({vol.Required("otp"): str}),
            errors=errors,
            description_placeholders={"phone": self._phone},
        )

    # ------------------------------------------------------------------ #
    # Step 3 (optional): choose site when the account has several
    # ------------------------------------------------------------------ #
    async def async_step_site(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose which site to track."""
        if user_input is not None:
            site = next(
                s for s in self._sites if str(s.get("siteId")) == user_input[CONF_SITE_ID]
            )
            self._site = site
            return await self.async_step_scheme()

        options = {
            str(s.get("siteId")): (s.get("siteName") or f"Site {s.get('siteId')}")
            for s in self._sites
        }
        return self.async_show_form(
            step_id="site",
            data_schema=vol.Schema({vol.Required(CONF_SITE_ID): vol.In(options)}),
        )

    # ------------------------------------------------------------------ #
    # Step 4: Norgespris or electricity subsidy (decides the net cost)
    # ------------------------------------------------------------------ #
    async def async_step_scheme(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask which compensation scheme the customer is on."""
        assert self._site is not None
        if user_input is not None:
            return await self._create_entry(self._site, user_input[CONF_SCHEME])

        return self.async_show_form(
            step_id="scheme",
            data_schema=vol.Schema({vol.Required(CONF_SCHEME): _scheme_selector()}),
        )

    # ------------------------------------------------------------------ #
    # Finish
    # ------------------------------------------------------------------ #
    async def _create_entry(self, site: dict[str, Any], scheme: str) -> ConfigFlowResult:
        """Create (or update) the config entry for the chosen site."""
        assert self._client is not None
        site_id = site.get("siteId")
        site_name = site.get("siteName") or f"Site {site_id}"

        await self.async_set_unique_id(f"{self._phone}-{site_id}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Amperium – {site_name}",
            data={
                CONF_PHONE: self._phone,
                CONF_ACCESS_TOKEN: self._client.access_token,
                CONF_REFRESH_TOKEN: self._client.refresh_token,
                CONF_SITE_ID: site_id,
                CONF_SITE_NAME: site_name,
            },
            options={CONF_SCHEME: scheme},
        )


class AmperiumOptionsFlow(OptionsFlow):
    """Options: which local hours count as "day" in the day/night split."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Keep the entry we are editing."""
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the day/night hours."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_DAY_START] >= user_input[CONF_DAY_END]:
                errors["base"] = "invalid_day_hours"
            else:
                return self.async_create_entry(data=user_input)

        current = self._entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCHEME, default=current.get(CONF_SCHEME, vol.UNDEFINED)
                    ): _scheme_selector(),
                    vol.Required(
                        CONF_DAY_START,
                        default=current.get(CONF_DAY_START, DEFAULT_DAY_START),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                    vol.Required(
                        CONF_DAY_END,
                        default=current.get(CONF_DAY_END, DEFAULT_DAY_END),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
                }
            ),
            errors=errors,
        )


def _scheme_selector() -> SelectSelector:
    """Dropdown with the two compensation schemes (labels come from translations)."""
    return SelectSelector(
        SelectSelectorConfig(
            options=SCHEMES,
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="scheme",
        )
    )


def _normalise_phone(raw: str) -> str:
    """Normalise a Norwegian phone number to +47XXXXXXXX form."""
    phone = raw.strip().replace(" ", "")
    if not phone.startswith("+"):
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) == 8:  # bare Norwegian number
            phone = "+47" + digits
        else:
            phone = "+" + digits
    return phone
