"""Platform for sensor integration."""
from __future__ import annotations

import logging
import json
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .luxerone import LuxerOneClient

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    luxer_api = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [PendingPackageSensor(entry.entry_id, luxer_api=luxer_api)], True
    )


class PendingPackageSensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_name = "Pending Luxer Packages"
    _attr_native_unit_of_measurement = "packages"
    _attr_has_entity_name = True
    _attr_icon = "mdi:package"

    def __init__(self, entry_id: str, luxer_api: LuxerOneClient) -> None:
        self._attr_unique_id = entry_id
        self._luxer_api = luxer_api

    async def async_update(self) -> None:
        pending_packages = await self._luxer_api.pending_packages()
        self._attr_native_value = len(pending_packages["data"])

        if len(pending_packages["data"]) > 0:
            self._attr_entity_picture = pending_packages["data"][0]["labels"][0]
        else:
            self._attr_entity_picture = None

        self._attr_extra_state_attributes = {"packages_json": pending_packages["data"]}
