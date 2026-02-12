"""DataUpdateCoordinator for the luxer integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .luxerone import LuxerOneAuthorizationError, LuxerOneClient

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


class LuxerDataUpdateCoordinator(
    DataUpdateCoordinator[dict[int, list[dict[str, Any]]]]
):
    """Coordinator that fetches locations and pending deliveries from luxer."""

    locations: list[dict[str, Any]]

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: LuxerOneClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.locations = []

    async def _async_setup(self) -> None:
        """Fetch the list of locations once during first refresh."""
        try:
            self.locations = await self.client.locations()
        except LuxerOneAuthorizationError as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            msg = f"Error fetching locations: {err}"
            raise UpdateFailed(msg) from err

    async def _async_update_data(self) -> dict[int, list[dict[str, Any]]]:
        """Fetch pending deliveries and group them by location ID."""
        try:
            deliveries = await self.client.pending_packages()
        except LuxerOneAuthorizationError as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            msg = f"Error fetching deliveries: {err}"
            raise UpdateFailed(msg) from err

        grouped: dict[int, list[dict[str, Any]]] = {
            loc["id"]: [] for loc in self.locations
        }

        for delivery in deliveries:
            loc_id = delivery.get("locationId")
            if loc_id is not None:
                grouped.setdefault(loc_id, []).append(delivery)

        return grouped
