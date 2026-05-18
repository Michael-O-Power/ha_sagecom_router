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
    
    def __init__(self):
        """Initialize the flow and a container for debug data."""
        self.debug_info = {}

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
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
                        "Accept": "application/json, text/plain, */*",
                        "Accept-Language": "en-AU,en-US;q=0.9,en-GB;q=0.8,en;q=0.7",
                        "Origin": f"http://{host}",
                        "Referer": f"http://{host}/",
                    }

                    # Step 1: Initialize baseline session
                    await session.get(base_url, headers=base_headers)
                    
                    jar_init = {k: m.value for k, m in session.cookie_jar.filter_cookies(base_url).items()}
                    # Ensure we send baseline tokens even if the GET dropped them
                    init_salt = jar_init.get("salt", "7UHqMkAHM8PNvh/O") 
                    init_nonce = jar_init.get("nonce", str(random.randint(100000000, 999999999)))

                    # Step 2: POST to login-params
                    params_url = f"http://{host}/api/v1/login-params"
                    
                    headers_params = base_headers.copy()
                    headers_params["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
                    
                    c_params = ["modeSelected=admin", f"salt={init_salt}", "backgroundColor=restgui-tpg-theme", "currentLanguage=EN", f"nonce={init_nonce}"]
                    headers_params["Cookie"] = "; ".join(c_params)

                    salt = None
                    nonce = None
                    bbox_id = None

                    # Log Params Request
                    self.debug_info["params_req_headers"] = str(headers_params)
                    self.debug_info["params_req_payload"] = f"login={username}"

                    async with asyncio.timeout(5):
                        async with session.post(
                            params_url, 
                            data=f"login={username}", 
                            headers=headers_params,
                            skip_auto_headers={"Cookie"}
                        ) as resp:
                            # Log Params Response
                            self.debug_info["params_resp_status"] = str(resp.status)
                            self.debug_info["params_resp_headers"] = str(resp.headers)
                            
                            if "salt" in resp.cookies:
                                salt = resp.cookies["salt"].value
                            if "nonce" in resp.cookies:
                                nonce = resp.cookies["nonce"].value
                            if "BBOX_ID" in resp.cookies:
                                bbox_id = resp.cookies["BBOX_ID"].value

                    jar_cookies = {k: m.value for k, m in session.cookie_jar.filter_cookies(base_url).items()}
                    if not salt: salt = jar_cookies.get("salt")
                    if not nonce: nonce = jar_cookies.get("nonce")
                    if not bbox_id: bbox_id = jar_cookies.get("BBOX_ID")

                    if not salt or not nonce:
                        self.debug_info["error"] = f"Missing tokens. Active Jar: {jar_cookies}"
                        return await self.async_step_debug_dump()
                    
                    # Step 3: Cryptographic Signature Generation
                    cnonce = f"{random.randint(1000000000000000, 9999999999999999)}000"
                    auth_key = self._calculate_auth_key(username, password, salt, nonce, cnonce)

                    # Step 4: Final Authenticated Challenge Setup
                    login_url = f"http://{host}/api/v1/login"
                    payload_str = f"login={username}&auth_key={auth_key}&cnonce={cnonce}"
                    
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

                    # Log Login Request
                    self.debug_info["login_req_headers"] = str(headers_login)
                    self.debug_info["login_req_payload"] = payload_str

                    async with session.post(
                        login_url, 
                        data=payload_str, 
                        headers=headers_login, 
                        skip_auto_headers={"Cookie"}
                    ) as login_resp:
                        # Log Login Response
                        self.debug_info["login_resp_status"] = str(login_resp.status)
                        error_body = await login_resp.text()
                        self.debug_info["login_resp_body"] = error_body

                        if login_resp.status in [200, 201]:
                            _LOGGER.info("Successfully authenticated with Sagemcom Router!")
                            return self.async_create_entry(
                                title=f"Sagemcom F@st 5866T ({host})", data=user_input
                            )
                        else:
                            # Forward directly to the UI Dump Step
                            return await self.async_step_debug_dump()

            except Exception as err:
                self.debug_info["error"] = str(err)
                return await self.async_step_debug_dump()

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

    async def async_step_debug_dump(self, user_input=None):
        """Show a UI block dumping all request and response info if auth fails."""
        if user_input is not None:
            # Clicking submit on the debug screen aborts the flow so you can start over
            return self.async_abort(reason="debug_finished")
            
        dump_text = (
            f"--- LOGIN PARAMS REQUEST ---\n"
            f"Headers: {self.debug_info.get('params_req_headers', '')}\n\n"
            f"--- LOGIN PARAMS RESPONSE ---\n"
            f"Status: {self.debug_info.get('params_resp_status', '')}\n"
            f"Headers: {self.debug_info.get('params_resp_headers', '')}\n\n"
            f"--- LOGIN REQUEST ---\n"
            f"Payload: {self.debug_info.get('login_req_payload', '')}\n"
            f"Headers: {self.debug_info.get('login_req_headers', '')}\n\n"
            f"--- LOGIN RESPONSE ---\n"
            f"Status: {self.debug_info.get('login_resp_status', '')}\n"
            f"Body: {self.debug_info.get('login_resp_body', '')}\n\n"
            f"--- EXCEPTIONS ---\n"
            f"{self.debug_info.get('error', 'None')}"
        )

        return self.async_show_form(
            step_id="debug_dump",
            data_schema=vol.Schema({
                vol.Optional("debug_data", default=dump_text): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                )
            }),
            errors={"base": "invalid_auth"}
        )