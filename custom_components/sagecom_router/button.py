import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Sagemcom Router button platforms from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Register the WPS trigger button entity
    async_add_entities([SagemcomWpsButton(coordinator, entry)])

class SagemcomWpsButton(ButtonEntity):
    """Interactive button entity to trigger the router's virtual WPS pairing switch."""

    def __init__(self, coordinator, entry):
        """Initialize the button attributes."""
        self._coordinator = coordinator
        self._entry = entry
        
        self._attr_unique_id = f"{entry.entry_id}_wps_pushbutton"
        self._attr_name = "Sagemcom Trigger WPS Pairing"
        self._attr_icon = "mdi:wps"
        
        # Group this execution entity inside your main router device panel
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
        }

    async def async_press(self) -> None:
        """Execute the API call when the button is clicked in the Home Assistant UI."""
        host = self._entry.data["host"]
        url = f"http://{host}/api/v1/wireless/wps/pushbutton"
        session = self._coordinator.hass.helpers.aiohttp_client.async_get_clientsession()
        
        _LOGGER.info("Sending command execution to WPS endpoint: %s", url)
        
        try:
            # We explicitly pass an empty JSON object payload context to fulfill strict REST API body requirements
            response = await session.post(url, json={})
            
            if response.status in [200, 201, 204]:
                _LOGGER.info("WPS button press successfully received by Sagemcom Router.")
            else:
                _LOGGER.error(
                    "Router rejected the WPS command execution. Status code received: %s", 
                    response.status
                )
        except Exception as err:
            _LOGGER.error("Failed to communicate with router WPS execution engine: %s", err)