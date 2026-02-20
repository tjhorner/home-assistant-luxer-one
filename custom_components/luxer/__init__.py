"""The luxer integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.core import ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ConfigEntryAuthFailed, ServiceValidationError
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import device_registry as dr

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

SERVICE_CREATE_TEMPORARY_ACCESS_CODE = "create_temporary_access_code"


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

    _async_register_services(hass)

    return True


def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    if hass.services.has_service(DOMAIN, SERVICE_CREATE_TEMPORARY_ACCESS_CODE):
        return

    async def async_handle_create_temporary_access_code(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle the create_temporary_access_code service call."""
        device_id: str | None = call.data.get("device_id")
        if not device_id:
            msg = "No device specified"
            raise ServiceValidationError(
                msg,
                translation_domain=DOMAIN,
                translation_key="no_device_specified",
            )

        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_id)
        if device is None:
            msg = "Device not found"
            raise ServiceValidationError(
                msg,
                translation_domain=DOMAIN,
                translation_key="device_not_found",
            )

        location_id: int | None = None
        for identifier in device.identifiers:
            if identifier[0] == DOMAIN:
                location_id = int(identifier[1])
                break

        if location_id is None:
            msg = "Device is not a Luxer One location"
            raise ServiceValidationError(
                msg,
                translation_domain=DOMAIN,
                translation_key="invalid_device",
            )

        config_entry_id = next(iter(device.config_entries), None)
        explicit_config_entry_id: str | None = call.data.get("config_entry_id")
        if explicit_config_entry_id:
            if explicit_config_entry_id not in device.config_entries:
                msg = "Device does not belong to the specified config entry"
                raise ServiceValidationError(
                    msg,
                    translation_domain=DOMAIN,
                    translation_key="config_entry_mismatch",
                )
            config_entry_id = explicit_config_entry_id

        if config_entry_id is None:
            msg = "No config entry found for device"
            raise ServiceValidationError(
                msg,
                translation_domain=DOMAIN,
                translation_key="no_config_entry",
            )

        entry = hass.config_entries.async_get_entry(config_entry_id)
        if entry is None or entry.runtime_data is None:
            msg = "Integration is not loaded"
            raise ServiceValidationError(
                msg,
                translation_domain=DOMAIN,
                translation_key="integration_not_loaded",
            )

        coordinator: LuxerDataUpdateCoordinator = entry.runtime_data
        client = coordinator.client

        available_rooms = await client.get_available_rooms()
        matching_rooms = [r for r in available_rooms if r["locationId"] == location_id]

        if not matching_rooms:
            msg = "No available rooms at this location"
            raise ServiceValidationError(
                msg,
                translation_domain=DOMAIN,
                translation_key="no_available_rooms",
            )

        room = matching_rooms[0]

        delivery_id = await client.create_temporary_access_code(
            location_id=room["locationId"],
            locker_id=room["lockerId"],
        )

        deliveries = await client.pending_packages()
        access_code: str | None = None
        for delivery in deliveries:
            if delivery.get("id") == delivery_id:
                access_code = delivery.get("accessCode")
                break

        await coordinator.async_request_refresh()

        return {
            "delivery_id": delivery_id,
            "access_code": access_code,
            "locker_location": room.get("lockerLocation", ""),
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_TEMPORARY_ACCESS_CODE,
        async_handle_create_temporary_access_code,
        supports_response=SupportsResponse.ONLY,
    )


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
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove services when the last config entry is unloaded
    if unload_ok and not hass.config_entries.async_loaded_entries(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_CREATE_TEMPORARY_ACCESS_CODE)

    return unload_ok
