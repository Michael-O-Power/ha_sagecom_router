import asyncio
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN

class SagemcomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a UI setup config flow for the Sagemcom 5G Router."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step when a user adds the integration."""
        errors = {}

        if user_input is not None:
            host = user_input["host"]
            test_url = f"http://{host}/api/v1/wan/status"
            
            try:
                # Test connection by trying to reach the router's native API
                session = self.hass.helpers.aiohttp_client.async_get_clientsession()
                async with asyncio.timeout(5):
                    response = await session.get(test_url)
                    if response.status == 200:
                        return self.async_create_entry(
                            title=f"Sagemcom 5G Router ({host})", 
                            data=user_input
                        )
                    else:
                        errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host", default="192.168.1.1"): str,
            }),
            errors=errors,
        )