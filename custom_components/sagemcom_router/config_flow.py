import asyncio
import hashlib
import logging
import random
import voluptuous as vol
import aiohttp  # Imported directly to configure an unsafe cookie jar
from yarl import URL
from homeassistant import config_entries
from homeassistant.helpers import selector
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
                base_url = URL(f"http://{host}/")
                
                # CRITICAL FIX: Instantiate a clean cookie jar that permits raw IP address cookies
                cookie_jar = aiohttp.CookieJar(unsafe=True)
                
                async with aiohttp.ClientSession(cookie_jar=cookie_jar) as session:
                    # Pre-populate the unsafe jar with the router's environmental defaults
                    session.cookie_jar.update_cookies({
                        "modeSelected": "admin",
                        "currentLanguage": "EN",
                        "backgroundColor": "restgui-tpg-theme"
                    }, base_url)

                    headers = {
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "Origin": f"http://{host}",
                        "Referer": f"http://{host}/"
                    }

                    # Step 1: Initialize baseline session (captures BBOX_ID safely now!)
                    _LOGGER.debug("Initializing session cookies at %s", base_url)
                    await session.get(base_url)

                    # Step 2: POST to login-params
                    params_url = f"http://{host}/api/v1/login-params"
                    salt = None
                    nonce = None

                    async with asyncio.timeout(5):
                        async with session.post(params_url, data={"login": username}, headers=headers) as resp:
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
                        # Grab whatever jar cookies exist for debugging
                        jar_cookies = {c.key: c.value for c in session.cookie_jar.filter_cookies(base_url)}
                        _LOGGER.error("Handshake failed. Cryptographic tokens missing. Active Jar: %s", jar_cookies)
                        errors["base"] = "cannot_connect"
                    else:
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
                        
                        # Add salt & nonce to our unsafe cookie jar container
                        session.cookie_jar.update_cookies({
                            "salt": salt,
                            "nonce": nonce
                        }, base_url)
                        
                        # ==================== EXPLICIT OUTGOING LOGS ====================
                        active_cookies = {c.key: c.value for c in session.cookie_jar.filter_cookies(base_url)}
                        _LOGGER.warning("--- DEBUGGING SAGEMCOM OUTGOING REQUEST ---")
                        _LOGGER.warning("Target URL: %s", login_url)
                        _LOGGER.warning("Outgoing Form Payload: %s", payload)
                        _LOGGER.warning("Active Session Jar Cookies: %s", active_cookies)
                        _LOGGER.warning("Outgoing Request Headers: %s", headers)
                        # ================================================================

                        async with session.post(login_url, data=payload, headers=headers) as login_resp:
                            if login_resp.status in [200, 201]:
                                _LOGGER.info("Successfully authenticated with Sagemcom Router!")
                                return self.async_create_entry(
                                    title=f"Sagemcom F@st 5866T ({host})", data=user_input
                                )
                            else:
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