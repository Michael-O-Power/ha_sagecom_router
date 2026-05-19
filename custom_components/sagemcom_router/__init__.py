import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

# FIX: Import the aiohttp_client helper directly from the core architecture
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Add any platforms you build in the future to this list (e.g., "sensor", "device_tracker")
PLATFORMS = []

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sagemcom F@st 5866T Router from a config entry."""
    
    # FIX: Correctly fetch the aiohttp session using the helper function
    session = async_get_clientsession(hass)

    hass.data.setdefault(DOMAIN, {})
    
    # Store the network session and credentials so other files in your integration can access them
    hass.data[DOMAIN][entry.entry_id] = {
        "session": session,
        "host": entry.data.get("host"),
        "username": entry.data.get("username"),
        "password": entry.data.get("password")
    }

    # If you add sensors later, this commands HA to load them
    if PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("Sagemcom router integration successfully set up for %s", entry.data.get("host"))
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