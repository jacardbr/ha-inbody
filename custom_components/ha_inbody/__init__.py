"""The InBody integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    InBodyApi,
    InBodyAuthError,
    InBodyConnectionError,
    InBodyCountryError,
    InBodyError,
)
from .const import CONF_COUNTRY, CONF_LOGIN_ID, CONF_PASSWORD
from .coordinator import InBodyCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type InBodyConfigEntry = ConfigEntry[InBodyCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: InBodyConfigEntry) -> bool:
    """Set up InBody from a config entry."""
    api = InBodyApi(
        async_get_clientsession(hass),
        entry.data[CONF_LOGIN_ID],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_COUNTRY],
    )
    try:
        uid = await api.async_login()
    except InBodyAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except InBodyCountryError as err:
        raise ConfigEntryNotReady(f"No InBody API host for {err}") from err
    except (InBodyConnectionError, InBodyError) as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = InBodyCoordinator(hass, entry, api, uid)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    return True


async def _async_reload_on_options(hass: HomeAssistant, entry: InBodyConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: InBodyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
