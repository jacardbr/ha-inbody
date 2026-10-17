"""Import the InBody scan history into Home Assistant long-term statistics."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import MassConverter

from .const import DOMAIN
from .sensor import SENSORS
from .stats_util import hourly_points

if TYPE_CHECKING:
    from . import InBodyConfigEntry

_LOGGER = logging.getLogger(__name__)

try:  # these names live in different modules across HA versions
    from homeassistant.components.recorder.models import (
        StatisticData,
        StatisticMeanType,
        StatisticMetaData,
    )
except ImportError:  # pragma: no cover
    from homeassistant.components.recorder.models.statistics import (  # type: ignore[no-redef]
        StatisticData,
        StatisticMeanType,
        StatisticMetaData,
    )


async def async_import_history(
    hass: HomeAssistant, entry: InBodyConfigEntry
) -> dict[str, Any]:
    """Fetch every scan and write hourly statistics for the measurement sensors.

    Statistics are attached to the existing sensor entities, so the old data
    shows up in the entity's statistics graph. Running it again is safe: the
    same hours are simply overwritten with the same values.
    """
    coordinator = entry.runtime_data
    scans = await coordinator.api.async_get_all_scans(dt_util.get_default_time_zone())

    registry = er.async_get(hass)
    imported: dict[str, int] = {}

    for desc in SENSORS:
        if desc.state_class is None:  # e.g. the "last scan" timestamp
            continue
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{coordinator.uid}_{desc.key}"
        )
        if entity_id is None:
            continue

        points = hourly_points(scans, desc.value_fn)
        if not points:
            continue

        # Statistics must be stored in the unit the entity currently reports.
        state = hass.states.get(entity_id)
        unit = (
            state.attributes.get("unit_of_measurement")
            if state is not None
            else None
        ) or desc.native_unit_of_measurement

        unit_class: str | None = None
        if desc.native_unit_of_measurement == UnitOfMass.KILOGRAMS:
            unit_class = "mass"
            if unit != UnitOfMass.KILOGRAMS:
                points = [
                    (start, MassConverter.convert(v, UnitOfMass.KILOGRAMS, unit))
                    for start, v in points
                ]

        metadata = StatisticMetaData(
            mean_type=StatisticMeanType.ARITHMETIC,
            has_sum=False,
            name=None,
            source="recorder",
            statistic_id=entity_id,
            unit_class=unit_class,
            unit_of_measurement=unit,
        )
        statistics = [
            StatisticData(start=start, mean=v, min=v, max=v) for start, v in points
        ]
        async_import_statistics(hass, metadata, statistics)
        imported[entity_id] = len(statistics)

    _LOGGER.info(
        "Imported InBody history: %d scans, %d hourly points across %d sensors",
        len(scans),
        sum(imported.values()),
        len(imported),
    )
    return {"scans_found": len(scans), "statistics_imported": imported}
