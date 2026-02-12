"""The luxer integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers import aiohttp_client

from .const import CONF_EMAIL, CONF_TOKEN
from .const import DOMAIN as DOMAIN
from .coordinator import LuxerDataUpdateCoordinator
from .luxerone import LuxerOneClient

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

type LuxerConfigEntry = ConfigEntry[LuxerDataUpdateCoordinator]

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LuxerConfigEntry) -> bool:
    """Set up luxer from a config entry."""
    email = entry.data[CONF_EMAIL]
    token = entry.data[CONF_TOKEN]

    session = aiohttp_client.async_get_clientsession(hass)
    client = LuxerOneClient(email, token, session)

    coordinator = LuxerDataUpdateCoordinator(hass, entry, client)

    # First refresh fetches locations (_async_setup) then deliveries
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LuxerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
