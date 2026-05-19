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
        self.debug_info = {}

    def _pure_sha512_crypt(self, key: str, salt: str) -> str:
        """Pure python implementation of Unix SHA512 crypt to avoid missing 'crypt' module in Python 3.13+."""
        key_b = key.encode('utf-8')
        salt_b = salt.encode('utf-8')
        ctx_a = hashlib.sha512(key_b + salt_b)
        ctx_b = hashlib.sha512(key_b + salt_b + key_b)
        dgst_b = ctx_b.digest()
        key_len = len(key_b)
        for i in range(0, key_len, 64):
            ctx_a.update(dgst_b[:min(64, key_len - i)])
        k = key_len
        while k > 0:
            if k & 1:
                ctx_a.update(dgst_b)
            else:
                ctx_a.update(key_b)
            k >>= 1
        dgst_a = ctx_a.digest()
        ctx_dp = hashlib.sha512(key_b * key_len)
        dgst_dp = ctx_dp.digest()
        p_bytes = bytearray()
        for i in range(0, key_len, 64):
            p_bytes.extend(dgst_dp[:min(64, key_len - i)])
        ctx_ds = hashlib.sha512(salt_b * (16 + dgst_a[0]))
        dgst_ds = ctx_ds.digest()
        salt_len = len(salt_b)
        s_bytes = bytearray()
        for i in range(0, salt_len, 64):
            s_bytes.extend(dgst_ds[:min(64, salt_len - i)])
        dgst = dgst_a
        for i in range(5000):
            ctx_c = hashlib.sha512()
            if i % 2 != 0:
                ctx_c.update(p_bytes)
            else:
                ctx_c.update(dgst)
            if i % 3 != 0:
                ctx_c.update(s_bytes)
            if i % 7 != 0:
                ctx_c.update(p_bytes)
            if i % 2 != 0:
                ctx_c.update(dgst)
            else:
                ctx_c.update(p_bytes)
            dgst = ctx_c.digest()
        b64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        def _b64_from_24bit(b2, b1, b0, n):
            w = (b2 << 16) | (b1 << 8) | b0
            return "".join(b64[(w >> (6 * i)) & 0x3f] for i in range(n))
        order = [
            (0, 21, 42), (22, 43, 1), (44, 2, 23), (3, 24, 45), (25, 46, 4),
            (47, 5, 26), (6, 27, 48), (28, 49, 7), (50, 8, 29), (9, 30, 51),
            (31, 52, 10), (53, 11, 32), (12, 33, 54), (34, 55, 13), (56, 14, 35),
            (15, 36, 57), (37, 58, 16), (59, 17, 38), (18, 39, 60), (40, 61, 19),
            (62, 20, 41)
        ]
        res = "".join(_b64_from_24bit(dgst[b2], dgst[b1], dgst[b0], 4) for b2, b1, b0 in order)
        res += _b64_from_24bit(0, 0, dgst[63], 2)
        return f"$6${salt}${res}"

    def _calculate_auth_key(self, username, password, salt, nonce, cnonce):
        """Replicate the customized F@st 5866T web-GUI SHA-512 signature generation."""
        # 1. f = cryptSha512(password, salt)
        f_val = self._pure_sha512_crypt(password, salt)
        
        # 2. substring(3) removes the "$6$" prefix, leaving the raw "salt$hash" sequence
        f_sub = f_val[3:]
        
        # 3. g = sha512(username + ":" + nonce + ":" + f.substring(3))
        g_str = f"{username}:{nonce}:{f_sub}"
        g = hashlib.sha512(g_str.encode("utf-8")).hexdigest()
        
        # 4. auth_key = sha512(g + ":0:" + cnonce)
        auth_string = f"{g}:0:{cnonce}"
        return hashlib.sha512(auth_string.encode("utf-8")).hexdigest()

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step when a user adds the integration."""
        errors = {}
        dump_text = ""

        if user_input is not None:
            host = user_input.get("host", "192.168.1.1").strip()
            username = user_input.get("username", "admin").strip()
            password = user_input.get("password", "").strip()

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
                        "Connection": "keep-alive"
                    }

                    # Step 1: Initialize baseline session
                    await session.get(base_url, headers=base_headers)
                    
                    jar_init = {k: m.value for k, m in session.cookie_jar.filter_cookies(base_url).items()}
                    init_salt = jar_init.get("salt", "7UHqMkAHM8PNvh/O") 
                    init_nonce = jar_init.get("nonce", str(random.randint(1000000000, 9999999999)))

                    # Step 2: POST to login-params
                    params_url = f"http://{host}/api/v1/login-params"
                    headers_params = base_headers.copy()
                    
                    c_params = ["modeSelected=admin", f"salt={init_salt}", "backgroundColor=restgui-tpg-theme", "currentLanguage=EN", f"nonce={init_nonce}"]
                    headers_params["Cookie"] = "; ".join(c_params)

                    salt = None
                    nonce = None
                    bbox_id = None

                    self.debug_info["params_req_headers"] = str(headers_params)

                    async with asyncio.timeout(5):
                        async with session.post(
                            params_url, 
                            data={"login": username}, 
                            headers=headers_params,
                            skip_auto_headers={"Cookie"}
                        ) as resp:
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
                        errors["base"] = "cannot_connect"
                    else:
                        # Step 3: Cryptographic Signature Generation
                        cnonce = f"{random.randint(1000000000000000, 9999999999999999)}000"
                        auth_key = self._calculate_auth_key(username, password, salt, nonce, cnonce)

                        # Step 4: Final Authenticated Challenge Setup
                        login_url = f"http://{host}/api/v1/login"
                        
                        payload_dict = {
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
                        headers_login["Cookie"] = "; ".join(cookie_parts)

                        self.debug_info["login_req_payload"] = str(payload_dict)
                        self.debug_info["login_req_headers"] = str(headers_login)

                        async with session.post(
                            login_url, 
                            data=payload_dict, 
                            headers=headers_login, 
                            skip_auto_headers={"Cookie"}
                        ) as login_resp:
                            self.debug_info["login_resp_status"] = str(login_resp.status)
                            error_body = await login_resp.text()
                            self.debug_info["login_resp_body"] = error_body

                            if login_resp.status in [200, 201]:
                                _LOGGER.info("Successfully authenticated with Sagemcom Router!")
                                return self.async_create_entry(
                                    title=f"Sagemcom F@st 5866T ({host})", data=user_input
                                )
                            else:
                                _LOGGER.error("Auth rejected. Status: %s. Body: %s", login_resp.status, error_body)
                                errors["base"] = "invalid_auth"

            except Exception as err:
                self.debug_info["error"] = str(err)
                errors["base"] = "cannot_connect"

            # Render output directly back to the UI window on failure
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

        schema_dict = {
            vol.Required("host", default=user_input.get("host", "192.168.1.1") if user_input else "192.168.1.1"): str,
            vol.Required("username", default=user_input.get("username", "admin") if user_input else "admin"): str,
            vol.Required("password", default=user_input.get("password", "") if user_input else ""): str,
        }

        if dump_text:
            schema_dict[vol.Optional("debug_output", default=dump_text)] = selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )