import asyncio
import hashlib
import logging
import random
from datetime import timedelta

import aiohttp
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Sagemcom Router component (Legacy Hook)."""
    return True

# --- PURE PYTHON CRYPTO ENGINE ---
def _pure_sha512_crypt(key: str, salt: str) -> str:
    """Pure python implementation of Unix SHA512 crypt."""
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

def _calculate_auth_key(username, password, salt, nonce, cnonce):
    f_val = _pure_sha512_crypt(password, salt)
    f_sub = f_val[3:]
    g_str = f"{username}:{nonce}:{f_sub}"
    g = hashlib.sha512(g_str.encode("utf-8")).hexdigest()
    auth_string = f"{g}:0:{cnonce}"
    return hashlib.sha512(auth_string.encode("utf-8")).hexdigest()


class SagemcomDataCoordinator(DataUpdateCoordinator):
    """Class to manage continuous authentication and data fetching."""

    def __init__(self, hass: HomeAssistant, host, username, password):
        super().__init__(
            hass,
            _LOGGER,
            name=f"Sagemcom {host}",
            update_interval=timedelta(seconds=60),
        )
        self.host = host
        self.username = username
        self.password = password
        self.base_url = f"http://{host}/api/v1"
        self.session = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar(unsafe=True))
        
        self._logged_in = False
        self._active_cookie = ""
        self._base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-AU,en-US;q=0.9,en-GB;q=0.8,en;q=0.7",
            "Origin": f"http://{self.host}",
            "Referer": f"http://{self.host}/",
            "Connection": "keep-alive"
        }
        
        # Newly mapped endpoints from the F@st 5866T config.js trace
        self.endpoints = {
            "device": f"{self.base_url}/device",
            "network_type": f"{self.base_url}/cellular/network_type",
            "sim_status": f"{self.base_url}/cellular/interface/usim/status_extended",
            "provider": f"{self.base_url}/cellular/provider",
            "session": f"{self.base_url}/cellular/session",
            "wan": f"{self.base_url}/wan/status",
            "interface_5g": f"{self.base_url}/cellular/interface_5g",
            "interface_4g": f"{self.base_url}/cellular/interface",
            "lan_stats": f"{self.base_url}/lan/stats",
            "wifi_24_stats": f"{self.base_url}/wireless/24/stats",
            "wifi_5_stats": f"{self.base_url}/wireless/5/stats"
        }

    async def _async_login(self):
        """Perform the Javascript login handshake to get fresh cookies."""
        await self.session.get(f"http://{self.host}/", headers=self._base_headers)
        jar_init = {k: m.value for k, m in self.session.cookie_jar.filter_cookies(URL(f"http://{self.host}/")).items()}
        init_salt = jar_init.get("salt", "7UHqMkAHM8PNvh/O") 
        init_nonce = jar_init.get("nonce", str(random.randint(1000000000, 9999999999)))

        params_url = f"{self.base_url}/login-params"
        headers_params = self._base_headers.copy()
        c_params = ["modeSelected=admin", f"salt={init_salt}", "backgroundColor=restgui-tpg-theme", "currentLanguage=EN", f"nonce={init_nonce}"]
        headers_params["Cookie"] = "; ".join(c_params)

        salt = None
        nonce = None
        bbox_id = None

        async with asyncio.timeout(5):
            async with self.session.post(params_url, data={"login": self.username}, headers=headers_params, skip_auto_headers={"Cookie"}) as resp:
                resp.raise_for_status()
                if "salt" in resp.cookies: salt = resp.cookies["salt"].value
                if "nonce" in resp.cookies: nonce = resp.cookies["nonce"].value
                if "BBOX_ID" in resp.cookies: bbox_id = resp.cookies["BBOX_ID"].value

        jar_cookies = {k: m.value for k, m in self.session.cookie_jar.filter_cookies(URL(f"http://{self.host}/")).items()}
        if not salt: salt = jar_cookies.get("salt")
        if not nonce: nonce = jar_cookies.get("nonce")
        if not bbox_id: bbox_id = jar_cookies.get("BBOX_ID")

        if not salt or not nonce:
            raise UpdateFailed("Failed to retrieve salt/nonce during initialization")

        cnonce = f"{random.randint(1000000000000000, 9999999999999999)}000"
        auth_key = _calculate_auth_key(self.username, self.password, salt, nonce, cnonce)

        login_url = f"{self.base_url}/login"
        payload_dict = {"login": self.username, "auth_key": auth_key, "cnonce": cnonce}
        cookie_parts = ["modeSelected=admin", f"salt={salt}", "backgroundColor=restgui-tpg-theme", "currentLanguage=EN", f"nonce={nonce}"]
        if bbox_id: cookie_parts.append(f"BBOX_ID={bbox_id}")
        
        headers_login = self._base_headers.copy()
        headers_login["Cookie"] = "; ".join(cookie_parts)

        async with self.session.post(login_url, data=payload_dict, headers=headers_login, skip_auto_headers={"Cookie"}) as login_resp:
            if login_resp.status not in [200, 201]:
                raise UpdateFailed(f"Router rejected authentication: {login_resp.status}")
            
            if "BBOX_ID" in login_resp.cookies:
                final_bbox = login_resp.cookies["BBOX_ID"].value
                cookie_parts = [c for c in cookie_parts if not c.startswith("BBOX_ID=")]
                cookie_parts.append(f"BBOX_ID={final_bbox}")

            self._active_cookie = "; ".join(cookie_parts)
            self._logged_in = True

    async def _async_update_data(self):
        """Fetch data from API endpoints."""
        if not self._logged_in:
            await self._async_login()

        try:
            results = {}
            for key, url in self.endpoints.items():
                headers = self._base_headers.copy()
                headers["Cookie"] = self._active_cookie
                
                async with self.session.get(url, headers=headers, skip_auto_headers={"Cookie"}) as response:
                    if response.status in [401, 403]:
                        _LOGGER.info("Session expired. Re-authenticating...")
                        await self._async_login()
                        headers["Cookie"] = self._active_cookie
                        async with self.session.get(url, headers=headers, skip_auto_headers={"Cookie"}) as retry_resp:
                            retry_resp.raise_for_status()
                            text = await retry_resp.text()
                            results[key] = await retry_resp.json() if text else {}
                    else:
                        response.raise_for_status()
                        text = await response.text()
                        results[key] = await response.json() if text else {}

            return results

        except Exception as err:
            self._logged_in = False
            raise UpdateFailed(f"API Error: {err}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sagemcom Router from a config entry."""
    host = entry.data.get("host")
    username = entry.data.get("username")
    password = entry.data.get("password")

    coordinator = SagemcomDataCoordinator(hass, host, username, password)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "host": host,
    }

    if PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if PLATFORMS:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    else:
        unload_ok = True
        
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok