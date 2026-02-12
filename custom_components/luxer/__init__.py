"""The luxer integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryAuthFailed
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
    email = entry.data.get(CONF_EMAIL, "")
    token = entry.data.get(CONF_TOKEN)

    if not token:
        msg = "No API token - reauthentication required"
        raise ConfigEntryAuthFailed(msg)

    session = aiohttp_client.async_get_clientsession(hass)
    client = LuxerOneClient(email, token, session)

    coordinator = LuxerDataUpdateCoordinator(hass, entry, client)

    # First refresh fetches locations (_async_setup) then deliveries
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(
    hass: HomeAssistant,
    config_entry: LuxerConfigEntry,
) -> bool:
    """Migrate old config entries to the current version."""
    if config_entry.version < 2:  # noqa: PLR2004
        _LOGGER.debug("Migrating config entry from version %s", config_entry.version)

        old_data = {**config_entry.data}
        new_data = {
            CONF_EMAIL: old_data.get("username", ""),
        }

        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            version=2,
        )

        _LOGGER.info(
            "Migration to v2 complete for %s - reauthentication required",
            config_entry.title,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LuxerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
