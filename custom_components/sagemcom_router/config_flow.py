import asyncio
import hashlib
import logging
import random
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
# Swapped to async_create_clientsession for an isolated cookie jar context
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class SagemcomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a UI setup config flow for the Sagemcom 5G Router."""
    VERSION = 1

    def _calculate_auth_key(self, username, password, salt, nonce, cnonce):
        """Replicate the router's web-GUI SHA-512 signature generation."""
        pw_hash = hashlib.sha512(f"{password}{salt}".encode("utf-8")).hexdigest()
        auth_string = f"{pw_hash}{nonce}{cnonce}"
        return hashlib.sha512(auth_string.encode("utf-8")).hexdigest()

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step when a user adds the integration."""
        errors = {}
        if user_input is not None:
            host = user_input["host"]
            username = user_input["username"]
            password = user_input["password"]

            try:
                # Create a standalone, pristine session instance
                session = async_create_clientsession(self.hass)
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Origin": f"http://{host}",
                    "Referer": f"http://{host}/"
                }

                # Step 1: Initialize baseline session
                _LOGGER.debug("Initializing session cookies at http://%s/", host)
                await session.get(f"http://{host}/")

                # Step 2: POST to login-params
                params_url = f"http://{host}/api/v1/login-params"
                salt = None
                nonce = None

                async with asyncio.timeout(5):
                    async with session.post(params_url, data={"login": username}, headers=headers) as resp:
                        _LOGGER.debug("login-params response status: %s", resp.status)
                        
                        try:
                            json_data = await resp.json()
                            if isinstance(json_data, dict):
                                salt = json_data.get("salt") or json_data.get("data", {}).get("salt")
                                nonce = json_data.get("nonce") or json_data.get("data", {}).get("nonce")
                        except Exception:
                            pass

                        if not salt and "salt" in resp.cookies:
                            salt = resp.cookies["salt"].value
                        if not nonce and "nonce" in resp.cookies:
                            nonce = resp.cookies["nonce"].value

                        if not salt or not nonce:
                            jar_cookies = session.cookie_jar.filter_cookies(resp.url)
                            if not salt and "salt" in jar_cookies:
                                salt = jar_cookies["salt"].value
                            if not nonce and "nonce" in jar_cookies:
                                nonce = jar_cookies["nonce"].value

                if not salt or not nonce:
                    _LOGGER.error("Handshake failed. Missing cryptographic cookies.")
                    errors["base"] = "cannot_connect"
                else:
                    _LOGGER.debug("Handshake success! Salt obtained, calculating auth token...")
                    
                    # Step 3: Cryptographic Signature
                    cnonce = str(random.randint(1000000000000000000, 9999999999999999999))
                    auth_key = self._calculate_auth_key(username, password, salt, nonce, cnonce)

                    # Step 4: Final Authenticated Challenge
                    login_url = f"http://{host}/api/v1/login"
                    payload = {
                        "login": username,
                        "auth_key": auth_key,
                        "cnonce": cnonce
                    }
                    
                    async with session.post(login_url, data=payload, headers=headers) as login_resp:
                        if login_resp.status in [200, 201]:
                            return self.async_create_entry(
                                title=f"Sagemcom F@st 5866T ({host})", data=user_input
                            )
                        else:
                            # Dump the actual error details from the router body
                            error_body = await login_resp.text()
                            _LOGGER.error(
                                "Authentication rejected by router status: %s. Response content: %s", 
                                login_resp.status, error_body
                            )
                            errors["base"] = "invalid_auth"

            except Exception as err:
                _LOGGER.exception("Unexpected connection exception encountered: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host", default="192.168.1.1"): str,
                vol.Required("username", default="admin"): str,
                vol.Required("password"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }),
            errors=errors,
        )