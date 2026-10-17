"""Config flow for InBody."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    InBodyApi,
    InBodyAuthError,
    InBodyConnectionError,
    InBodyCountryError,
    InBodyError,
)
from .const import (
    CONF_COUNTRY,
    CONF_LOGIN_ID,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_COUNTRY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def _validate(
    hass, login_id: str, password: str, country: str
) -> tuple[str | None, str | None]:
    """Try to log in. Returns (uid, error_key)."""
    api = InBodyApi(async_get_clientsession(hass), login_id, password, country)
    try:
        return await api.async_login(), None
    except InBodyAuthError:
        return None, "invalid_auth"
    except InBodyCountryError:
        return None, "unsupported_country"
    except InBodyConnectionError:
        return None, "cannot_connect"
    except InBodyError:
        _LOGGER.exception("InBody login failed")
        return None, "cannot_connect"
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error during InBody login")
        return None, "unknown"


class InBodyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for InBody."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            login_id = user_input[CONF_LOGIN_ID].strip()
            country = user_input[CONF_COUNTRY].strip().upper()
            uid, error = await _validate(
                self.hass, login_id, user_input[CONF_PASSWORD], country
            )
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"InBody ({login_id[-4:]})",
                    data={
                        CONF_LOGIN_ID: login_id,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_COUNTRY: country,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_LOGIN_ID): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_COUNTRY, default=DEFAULT_COUNTRY): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            uid, error = await _validate(
                self.hass,
                entry.data[CONF_LOGIN_ID],
                user_input[CONF_PASSWORD],
                entry.data[CONF_COUNTRY],
            )
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return InBodyOptionsFlow()


class InBodyOptionsFlow(OptionsFlow):
    """Options: polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
