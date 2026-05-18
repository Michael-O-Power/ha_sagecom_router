import asyncio
import hashlib
import logging
import random
import voluptuous as vol
import aiohttp
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
                cookie_jar = aiohttp.CookieJar(unsafe=True)
                
                async with aiohttp.ClientSession(cookie_jar=cookie_jar) as session:
                    base_headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "application/json, text/plain, */*",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Origin": f"http://{host}",
                        "Referer": f"http://{host}/",
                    }
                    
                    session.cookie_jar.update_cookies({
                        "modeSelected": "admin",
                        "currentLanguage": "EN",
                        "backgroundColor": "restgui-tpg-theme"
                    }, base_url)

                    # Step 1: Initialize baseline session
                    await session.get(base_url, headers=base_headers)

                    # Step 2: POST to login-params
                    params_url = f"http://{host}/api/v1/login-params"
                    salt = None
                    nonce = None

                    headers_params = base_headers.copy()
                    headers_params["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"

                    async with asyncio.timeout(5):
                        async with session.post(params_url, data={"login": username}, headers=headers_params) as resp:
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

                    # Fallback collection
                    jar_cookies = {k: m.value for k, m in session.cookie_jar.filter_cookies(base_url).items()}
                    if not salt: salt = jar_cookies.get("salt")
                    if not nonce: nonce = jar_cookies.get("nonce")
                    bbox_id = jar_cookies.get("BBOX_ID")

                    if not salt or not nonce:
                        _LOGGER.error("Handshake failed. Cryptographic tokens missing. Active Jar: %s", jar_cookies)
                        errors["base"] = "cannot_connect"
                    else:
                        # Step 3: Cryptographic Signature
                        # FIX: Scale down cnonce to a standard 9-digit safe integer to prevent router overflows
                        cnonce = str(random.randint(100000000, 999999999))
                        auth_key = self._calculate_auth_key(username, password, salt, nonce, cnonce)

                        # Step 4: Final Authenticated Challenge
                        login_url = f"http://{host}/api/v1/login"
                        payload = {
                            "login": username,
                            "auth_key": auth_key,
                            "cnonce": cnonce
                        }
                        
                        cookie_parts = [
                            "modeSelected=admin",
                            f"salt={salt}",
                            "backgroundColor=restgui-tpg-theme",
                            "currentLanguage=EN",
                            f"nonce={nonce}"
                        ]
                        if bbox_id:
                            cookie_parts.append(f"BBOX_ID={bbox_id}")
                        
                        headers_login = base_headers.copy()
                        headers_login["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
                        headers_login["Cookie"] = "; ".join(cookie_parts)

                        # ==================== LOGS REMAIN ACTIVE ====================
                        _LOGGER.warning("--- DEBUGGING SAGEMCOM OUTGOING REQUEST ---")
                        _LOGGER.warning("Target URL: %s", login_url)
                        _LOGGER.warning("Outgoing Form Payload: %s", payload)
                        _LOGGER.warning("Outgoing Request Headers (MANUAL COOKIE): %s", headers_login)
                        # ============================================================

                        async with session.post(
                            login_url, 
                            data=payload, 
                            headers=headers_login, 
                            skip_auto_headers={"Cookie"}
                        ) as login_resp:
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