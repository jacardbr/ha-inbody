"""WebSocket API used by the Lovelace card to browse past weigh-ins."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .api import InBodyError
from .const import DOMAIN
from .metrics import scan_payload
from .sensor import SENSORS


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the commands."""
    websocket_api.async_register_command(hass, ws_scans)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/scans",
        vol.Optional("device_id"): str,
    }
)
@websocket_api.async_response
async def ws_scans(hass: HomeAssistant, connection, msg) -> None:
    """Return every scan of the account (time + numeric values), oldest first."""
    entries = [e for e in hass.config_entries.async_entries(DOMAIN) if getattr(e, "runtime_data", None)]
    device_id = msg.get("device_id")
    if device_id:
        device = dr.async_get(hass).async_get(device_id)
        if device is not None:
            wanted = [e for e in entries if e.entry_id in device.config_entries]
            entries = wanted or entries
    if not entries:
        connection.send_error(msg["id"], "not_found", "HA InBody is not set up")
        return
    try:
        scans = await entries[0].runtime_data.async_get_scans()
    except InBodyError as err:
        connection.send_error(msg["id"], "unknown_error", str(err))
        return
    connection.send_result(
        msg["id"], {"scans": [scan_payload(scan, SENSORS) for scan in scans if scan.taken_at]}
    )
