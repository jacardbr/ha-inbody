"""The InBody integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    callback,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import (
    InBodyApi,
    InBodyAuthError,
    InBodyConnectionError,
    InBodyCountryError,
    InBodyError,
)
from .const import (
    CONF_COUNTRY,
    CONF_IMPORT_HISTORY,
    CONF_LOGIN_ID,
    CONF_PASSWORD,
    DOMAIN,
)
from .coordinator import InBodyCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_IMPORT_HISTORY = "import_history"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

# Sensor keys that were renamed. The entity registry entries are migrated in
# place, so entity_ids and recorded history are kept.
_KEY_RENAMES = {
    "percent_body_fat": "body_fat_percentage",
    "total_body_water": "body_water_mass",
    "total_body_water_percentage": "body_water_percentage",
}

type InBodyConfigEntry = ConfigEntry[InBodyCoordinator]


async def _async_migrate_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, uid: str
) -> None:
    """Rename old sensor unique_ids to the current keys (idempotent)."""
    registry = er.async_get(hass)

    @callback
    def _migrate(reg_entry: er.RegistryEntry) -> dict[str, str] | None:
        for old, new in _KEY_RENAMES.items():
            if reg_entry.unique_id == f"{uid}_{old}":
                new_unique_id = f"{uid}_{new}"
                if registry.async_get_entity_id(
                    reg_entry.domain, DOMAIN, new_unique_id
                ):
                    return None  # already exists; leave the old one alone
                return {"new_unique_id": new_unique_id}
        return None

    await er.async_migrate_entries(hass, entry.entry_id, _migrate)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the domain-level actions."""

    async def _import_history(call: ServiceCall) -> ServiceResponse:
        # Imported lazily so the rest of the integration keeps working on
        # Home Assistant versions without the newer statistics API.
        try:
            from .history import async_import_history
        except ImportError as err:
            raise ServiceValidationError(
                f"History import is not supported by this Home Assistant version: {err}"
            ) from err

        entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
        if entry_id:
            entry = hass.config_entries.async_get_entry(entry_id)
            if (
                entry is None
                or entry.domain != DOMAIN
                or entry.state is not ConfigEntryState.LOADED
            ):
                raise ServiceValidationError(
                    f"{entry_id} is not a loaded InBody config entry"
                )
            entries = [entry]
        else:
            entries = hass.config_entries.async_loaded_entries(DOMAIN)
            if not entries:
                raise ServiceValidationError("No loaded InBody config entry")

        results: dict[str, object] = {}
        for entry in entries:
            try:
                results[entry.entry_id] = await async_import_history(hass, entry)
            except HomeAssistantError:
                raise
            except Exception as err:  # InBodyError and anything unexpected
                raise HomeAssistantError(
                    f"InBody history import failed: {err}"
                ) from err
        return {"entries": results} if call.return_response else None

    hass.services.async_register(
        DOMAIN,
        SERVICE_IMPORT_HISTORY,
        _import_history,
        schema=vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


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

    await _async_migrate_unique_ids(hass, entry, uid)

    coordinator = InBodyCoordinator(hass, entry, api, uid)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))

    # One-shot, requested in the setup form. Runs in the background once the
    # sensors exist in the entity registry; the flag is cleared when it succeeds.
    if entry.data.get(CONF_IMPORT_HISTORY):
        entry.async_create_background_task(
            hass,
            _async_import_history_once(hass, entry),
            f"{DOMAIN}_import_history_{entry.entry_id}",
        )
    return True


async def _async_import_history_once(
    hass: HomeAssistant, entry: InBodyConfigEntry
) -> None:
    """Import the history, then clear the flag so it never runs again."""
    try:
        from .history import async_import_history
    except ImportError as err:
        _LOGGER.warning(
            "Skipping InBody history import: not supported by this Home Assistant "
            "version (%s)",
            err,
        )
        _clear_import_flag(hass, entry)
        return

    try:
        await async_import_history(hass, entry)
    except Exception as err:  # noqa: BLE001
        # Keep the flag: the import is retried the next time the entry loads.
        # The ha_inbody.import_history action can also be run manually.
        _LOGGER.warning("InBody history import failed, will retry on next start: %s", err)
        return
    _clear_import_flag(hass, entry)


def _clear_import_flag(hass: HomeAssistant, entry: InBodyConfigEntry) -> None:
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_IMPORT_HISTORY: False}
    )


async def _async_reload_on_options(hass: HomeAssistant, entry: InBodyConfigEntry) -> None:
    """Reload only when the options changed (not for other entry updates)."""
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is not None and dict(entry.options) == coordinator.options:
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: InBodyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
