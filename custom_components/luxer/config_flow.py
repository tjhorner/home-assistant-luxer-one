"""Config flow for luxer integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client

from .const import CONF_EMAIL, CONF_TOKEN, CONF_UUID, DOMAIN
from .luxerone import LuxerOneClient

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigFlowResult

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
    }
)

STEP_OTP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("otp"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for luxer."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._email: str
        self._uuid: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: ask for the email address and send an OTP."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._uuid = LuxerOneClient.generate_uuid()

            session = aiohttp_client.async_get_clientsession(self.hass)
            client = LuxerOneClient(self._email, session=session)

            try:
                ok = await client.request_otp()
                if not ok:
                    errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error requesting OTP")
                errors["base"] = "cannot_connect"

            if not errors:
                return await self.async_step_otp()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: verify the OTP code and create the config entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            client = LuxerOneClient(self._email, session=session)

            try:
                token = await client.verify_otp(user_input["otp"], self._uuid)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("OTP verification failed")
                errors["base"] = "invalid_auth"
            else:
                user = await client.user_info()
                title = f"{user['firstName']} {user['lastName']}"
                await self.async_set_unique_id(user["email"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_EMAIL: self._email,
                        CONF_TOKEN: token,
                        CONF_UUID: self._uuid,
                    },
                )

        return self.async_show_form(
            step_id="otp",
            data_schema=STEP_OTP_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"email": self._email},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the token expires."""
        # Support migrated v1 entries that may not have CONF_EMAIL yet
        self._email = entry_data.get(CONF_EMAIL, entry_data.get("username", ""))
        self._uuid = entry_data.get(CONF_UUID, LuxerOneClient.generate_uuid())
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt user to start the reauth OTP flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._uuid = LuxerOneClient.generate_uuid()

            session = aiohttp_client.async_get_clientsession(self.hass)
            client = LuxerOneClient(self._email, session=session)

            try:
                ok = await client.request_otp()
                if not ok:
                    errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error requesting OTP for reauth")
                errors["base"] = "cannot_connect"

            if not errors:
                return await self.async_step_reauth_otp()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL, default=self._email): str}
            ),
            errors=errors,
            description_placeholders={"email": self._email},
        )

    async def async_step_reauth_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Verify the OTP during reauthentication and update the token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            client = LuxerOneClient(self._email, session=session)

            try:
                token = await client.verify_otp(user_input["otp"], self._uuid)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Reauth OTP verification failed")
                errors["base"] = "invalid_auth"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        CONF_EMAIL: self._email,
                        CONF_TOKEN: token,
                        CONF_UUID: self._uuid,
                    },
                )

        return self.async_show_form(
            step_id="reauth_otp",
            data_schema=STEP_OTP_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"email": self._email},
        )


class CannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuthError(HomeAssistantError):
    """Error to indicate there is invalid auth."""
