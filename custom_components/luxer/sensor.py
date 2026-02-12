"""Platform for sensor integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LuxerDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import LuxerConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: LuxerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Luxer One sensors - one per locker location."""
    coordinator = entry.runtime_data

    entities: list[LuxerPendingPackageSensor] = [
        LuxerPendingPackageSensor(coordinator, entry.entry_id, location)
        for location in coordinator.locations
    ]

    async_add_entities(entities)


class LuxerPendingPackageSensor(
    CoordinatorEntity[LuxerDataUpdateCoordinator], SensorEntity
):
    """Sensor showing the number of pending packages at a Luxer location."""

    _attr_native_unit_of_measurement = "packages"
    _attr_has_entity_name = True
    _attr_icon = "mdi:package"
    _attr_name = "Pending Packages"

    def __init__(
        self,
        coordinator: LuxerDataUpdateCoordinator,
        entry_id: str,
        location: dict[str, Any],
    ) -> None:
        """Initialize the sensor for a specific location."""
        super().__init__(coordinator)
        self._location_id: int = location["id"]
        self._location_name: str = location["name"]

        self._attr_unique_id = f"{entry_id}_{self._location_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._location_id))},
            name=self._location_name,
            manufacturer="Luxer One",
            entry_type=None,
        )

    @property
    def _deliveries(self) -> list[dict[str, Any]]:
        """Return the list of deliveries for this location."""
        if self.coordinator.data is None:
            return []
        return self.coordinator.data.get(self._location_id, [])

    @property
    def native_value(self) -> int:
        """Return the number of pending packages."""
        return len(self._deliveries)

    @property
    def entity_picture(self) -> str | None:
        """Return the label image of the first pending package, if any."""
        deliveries = self._deliveries
        if deliveries:
            pictures = deliveries[0].get("deliveryPictures", {})
            labels = pictures.get("labels", [])
            if labels:
                return labels[0]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw delivery data as an attribute."""
        return {"packages_json": self._deliveries}
