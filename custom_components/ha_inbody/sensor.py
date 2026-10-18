"""Sensors for InBody."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import InBodyConfigEntry
from .api import InBodyScan
from .const import DOMAIN
from .coordinator import InBodyCoordinator
from .metrics import ExtraMetric, extra_metrics, read_metric
from .stats_util import percent_of


def _num(block: dict[str, Any], key: str) -> float | None:
    """Read a numeric field that the API may deliver as a string."""
    value = block.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _model(coordinator: InBodyCoordinator) -> str:
    """Scale model reported by the API (for example "H30"), else a generic name."""
    scan = coordinator.data
    equip = str((scan.bca or {}).get("EQUIP") or "").strip() if scan else ""
    return f"InBody {equip}" if equip else "InBody scale"


@dataclass(frozen=True, kw_only=True)
class InBodySensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor."""

    value_fn: Callable[[InBodyScan], float | datetime | None]


SENSORS: tuple[InBodySensorDescription, ...] = (
    InBodySensorDescription(
        key="weight",
        translation_key="weight",
        icon="mdi:weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: _num(s.bca, "WT"),
    ),
    InBodySensorDescription(
        key="bmi",
        translation_key="bmi",
        icon="mdi:weight",
        native_unit_of_measurement="kg/m²",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: _num(s.mfa, "BMI"),
    ),
    InBodySensorDescription(
        key="body_fat_percentage",
        translation_key="body_fat_percentage",
        icon="mdi:water-opacity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: _num(s.mfa, "PBF"),
    ),
    InBodySensorDescription(
        key="skeletal_muscle_mass",
        translation_key="skeletal_muscle_mass",
        icon="mdi:arm-flex",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: _num(s.mfa, "SMM"),
    ),
    InBodySensorDescription(
        key="skeletal_muscle_percentage",
        translation_key="skeletal_muscle_percentage",
        icon="mdi:arm-flex",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        # Derived: skeletal muscle mass as a share of body weight.
        value_fn=lambda s: percent_of(_num(s.mfa, "SMM"), _num(s.bca, "WT")),
    ),
    InBodySensorDescription(
        key="body_fat_mass",
        translation_key="body_fat_mass",
        icon="mdi:water-opacity",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: _num(s.bca, "BFM"),
    ),
    InBodySensorDescription(
        key="body_water_mass",
        translation_key="body_water_mass",
        icon="mdi:water",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: _num(s.bca, "TBW"),
    ),
    InBodySensorDescription(
        key="body_water_percentage",
        translation_key="body_water_percentage",
        icon="mdi:water",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        # Derived: total body water as a share of body weight.
        value_fn=lambda s: percent_of(_num(s.bca, "TBW"), _num(s.bca, "WT")),
    ),
    InBodySensorDescription(
        key="last_scan",
        translation_key="last_scan",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda s: s.taken_at,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InBodyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up InBody sensors."""
    coordinator = entry.runtime_data
    async_add_entities(InBodySensor(coordinator, desc) for desc in SENSORS)

    # Every other numeric field the API returns becomes an extra sensor, disabled
    # by default. New fields that show up in later scans are added as they appear.
    known: set[str] = set()

    @callback
    def _add_extra_sensors() -> None:
        scan = coordinator.data
        if scan is None:
            return
        new = [m for m in extra_metrics(scan.bca, scan.mfa) if m.slug not in known]
        if new:
            known.update(m.slug for m in new)
            async_add_entities(InBodyExtraSensor(coordinator, m) for m in new)

    _add_extra_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_extra_sensors))


class InBodySensor(CoordinatorEntity[InBodyCoordinator], SensorEntity):
    """A sensor reading one value from the latest scan."""

    _attr_has_entity_name = True
    entity_description: InBodySensorDescription
    # The raw blocks are large and change every scan; keep them out of the DB.
    _unrecorded_attributes = frozenset({"bca", "mfa"})

    def __init__(
        self, coordinator: InBodyCoordinator, description: InBodySensorDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.uid}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.uid)},
            name="InBody",
            manufacturer="InBody",
            model=_model(coordinator),
        )

    @property
    def native_value(self) -> float | datetime | None:
        scan = self.coordinator.data
        if scan is None:
            return None
        return self.entity_description.value_fn(scan)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        # Expose every field the API returned on the "last scan" sensor, so
        # metrics without a dedicated sensor are still visible/usable.
        if self.entity_description.key != "last_scan" or self.coordinator.data is None:
            return None
        scan = self.coordinator.data
        return {"raw_datetime": scan.raw_datetime, "bca": scan.bca, "mfa": scan.mfa}


class InBodyExtraSensor(CoordinatorEntity[InBodyCoordinator], SensorEntity):
    """A sensor for one extra numeric field of the BCA / MFA block."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: InBodyCoordinator, metric: ExtraMetric) -> None:
        super().__init__(coordinator)
        self._metric = metric
        self._attr_entity_registry_enabled_default = metric.featured
        self._attr_unique_id = f"{coordinator.uid}_{metric.slug}"
        self._attr_name = metric.name
        self._attr_native_unit_of_measurement = metric.unit
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.uid)},
            name="InBody",
            manufacturer="InBody",
            model=_model(coordinator),
        )

    @property
    def native_value(self) -> float | None:
        scan = self.coordinator.data
        if scan is None:
            return None
        return read_metric(scan.bca, scan.mfa, self._metric)
