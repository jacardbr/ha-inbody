"""Diagnostics for InBody."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import InBodyConfigEntry
from .const import CONF_LOGIN_ID, CONF_PASSWORD

TO_REDACT = {CONF_LOGIN_ID, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: InBodyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics (credentials redacted, all raw metric keys included)."""
    scan = entry.runtime_data.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "latest_scan": None
        if scan is None
        else {
            "raw_datetime": scan.raw_datetime,
            "taken_at": scan.taken_at.isoformat() if scan.taken_at else None,
            "bca": scan.bca,
            "mfa": scan.mfa,
            "other_blocks": scan.other,
        },
    }
