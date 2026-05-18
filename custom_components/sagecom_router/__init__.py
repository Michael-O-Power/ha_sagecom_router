from datetime import timedelta
import logging
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

ENDPOINTS = {
    "device": "/api/v1/device",
    "wan_status": "/api/v1/wan/status",
    "network_type": "/api/v1/cellular/network_type",
    "provider": "/api/v1/cellular/provider",
    "session": "/api/v1/cellular/session",
    "cellular_4g": "/api/v1/cellular/interface",
    "cellular_5g": "/api/v1/cellular/interface_5g",
    "wifi_24_stats": "/api/v1/wireless/24/stats",
    "wifi_5_stats": "/api/v1/wireless/5/stats",
    "lan_stats": "/api/v1/lan/stats"
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sagemcom 5G Router from a config entry."""
    session = hass.helpers.aiohttp_client.async_get_clientsession()
    host = entry.data["host"]

    async def async_update_data():
        """Fetch data from all system endpoints concurrently."""
        data = {}
        for key, endpoint in ENDPOINTS.items():
            url = f"http://{host}{endpoint}"
            try:
                async with asyncio.timeout(5):
                    response = await session.get(url)
                    if response.status == 200:
                        data[key] = await response.json()
                    else:
                        _LOGGER.debug("Endpoint %s returned status %s", url, response.status)
            except Exception as err:
                _LOGGER.debug("Failed to update data endpoint %s: %s", key, err)
        
        if not data:
            raise UpdateFailed("Failed to communicate with Sagemcom Router endpoints")
        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Sagemcom Router Coordinator",
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok