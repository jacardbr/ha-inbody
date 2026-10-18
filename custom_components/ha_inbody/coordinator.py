"""Data update coordinator for InBody."""

from __future__ import annotations

from datetime import timedelta
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import InBodyApi, InBodyAuthError, InBodyError, InBodyScan
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

_SCANS_TTL = 6 * 3600  # seconds


class InBodyCoordinator(DataUpdateCoordinator[InBodyScan | None]):
    """Polls the InBody cloud for the latest scan."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: InBodyApi, uid: str
    ) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=minutes),
        )
        self.api = api
        self.uid = uid
        # Snapshot used to tell real option changes apart from other entry
        # updates (e.g. clearing the one-shot import flag) when deciding to reload.
        self.options = dict(entry.options)
        # Every scan of the account, fetched on demand for the card's history.
        self._scans: list[InBodyScan] | None = None
        self._scans_at = 0.0

    async def _async_update_data(self) -> InBodyScan | None:
        try:
            return await self.api.async_get_latest_scan(dt_util.get_default_time_zone())
        except InBodyAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except InBodyError as err:
            raise UpdateFailed(f"Error fetching InBody data: {err}") from err

    async def async_get_scans(self) -> list[InBodyScan]:
        """All scans, oldest first. Cached; refreshed when a new scan arrives."""
        latest = self.data.raw_datetime if self.data else None
        cached = self._scans
        fresh = (
            cached is not None
            and time.monotonic() - self._scans_at < _SCANS_TTL
            and (latest is None or (bool(cached) and cached[-1].raw_datetime == latest))
        )
        if not fresh:
            try:
                self._scans = await self.api.async_get_all_scans(dt_util.get_default_time_zone())
            except InBodyAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            self._scans_at = time.monotonic()
        return self._scans or []
