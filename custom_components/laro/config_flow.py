"""Config flow for Laro integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_URL
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_TOKEN

_LOGGER = logging.getLogger(__name__)

# Cloud-first default; self-host / HA add-on users can enter a LAN URL instead.
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="https://laro.food"): str,
        vol.Required(CONF_TOKEN): str,
    }
)


class LaroConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Laro."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_url: str | None = None
        self._discovered_name: str | None = None

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle Zeroconf discovery."""
        _LOGGER.debug("Zeroconf discovery: %s", discovery_info)

        # Extract host and port from discovery
        host = discovery_info.host
        port = discovery_info.port or 8001
        name = discovery_info.name.replace("._laro._tcp.local.", "")

        self._discovered_url = f"http://{host}:{port}"
        self._discovered_name = name

        # Check if already configured
        await self.async_set_unique_id(f"laro_{host}_{port}")
        self._abort_if_unique_id_configured(
            updates={CONF_URL: self._discovered_url}
        )

        # Verify it's actually a Laro instance
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{self._discovered_url}/api/health",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if response.status != 200:
                    return self.async_abort(reason="cannot_connect")
        except Exception:
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm Zeroconf discovery and get API token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN]

            # Validate token
            session = async_get_clientsession(self.hass)
            try:
                async with session.get(
                    f"{self._discovered_url}/api/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        user_id = user_data.get("id", "default")

                        await self.async_set_unique_id(f"laro_{user_id}")
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=f"Laro ({self._discovered_name or user_data.get('email', 'User')})",
                            data={CONF_URL: self._discovered_url, CONF_TOKEN: token},
                        )
                    else:
                        errors["base"] = "invalid_auth"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during zeroconf confirm")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
            description_placeholders={
                "name": self._discovered_name or "Laro",
                "url": self._discovered_url,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate connection
            session = async_get_clientsession(self.hass)
            url = user_input[CONF_URL].rstrip("/")
            token = user_input[CONF_TOKEN]

            try:
                async with session.get(
                    f"{url}/api/health",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        # Get user info for unique ID
                        async with session.get(
                            f"{url}/api/auth/me",
                            headers={"Authorization": f"Bearer {token}"},
                        ) as user_response:
                            if user_response.status == 200:
                                user_data = await user_response.json()
                                user_id = user_data.get("id", "default")

                                await self.async_set_unique_id(f"laro_{user_id}")
                                self._abort_if_unique_id_configured()

                                return self.async_create_entry(
                                    title=f"Laro ({user_data.get('email', 'User')})",
                                    data={CONF_URL: url, CONF_TOKEN: token},
                                )
                            else:
                                errors["base"] = "invalid_auth"
                    elif response.status == 401:
                        errors["base"] = "invalid_auth"
                    else:
                        errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "url_hint": "Cloud: https://laro.food — Self-host: http://192.168.1.100:8001",
                "token_hint": "API token from Laro → Settings → API Tokens",
            },
        )


class LaroOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Laro options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )
