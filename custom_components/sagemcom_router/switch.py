import logging
from typing import Any
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    domain_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = domain_data["coordinator"]
    async_add_entities([SagemcomGuestWiFiSwitch(coordinator, entry.entry_id)])

class SagemcomGuestWiFiSwitch(CoordinatorEntity, SwitchEntity):
    """Switch tracking and driving the operational bounds of Guest broadcasts."""
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator)
        self.entry_id = entry_id
        self._attr_unique_id = f"sagemcom_{entry_id}_guest_wifi_toggle"
        self._attr_name = "Guest Wireless Access"
        self._attr_icon = "mdi:wifi-lock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_wifi_guest")},
            name="Guest Wi-Fi Network",
            manufacturer="Sagemcom Network",
            via_device=(DOMAIN, entry_id)
        )

    @property
    def is_on(self) -> bool:
        if not self.coordinator.data: return False
        
        # Check the flattened guest structure for activation flag
        g24_en = self.coordinator.data.get("wifi_guest24", [{}])[0].get("guest24", {}).get("enable", "false")
        g5_en = self.coordinator.data.get("wifi_guest5", [{}])[0].get("guest5", {}).get("enable", "false")
        
        return str(g24_en).lower() == "true" or str(g5_en).lower() == "true"

    async def _async_trigger_put(self, endpoint: str, ssid: str, enable_val: str) -> None:
        """Execute the strict PUT url-encoded form handshake the router demands."""
        if not self.coordinator._logged_in:
            await self.coordinator._async_login()
            
        headers = self.coordinator._base_headers.copy()
        headers["Cookie"] = self.coordinator._active_cookie
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        
        url = f"{self.coordinator.base_url}/{endpoint}"
        payload = {"ssid": ssid, "enable": enable_val}
        
        async with self.coordinator.session.put(url, data=payload, headers=headers, skip_auto_headers={"Cookie"}) as resp:
            if resp.status in [401, 403]:
                await self.coordinator._async_login()
                headers["Cookie"] = self.coordinator._active_cookie
                async with self.coordinator.session.put(url, data=payload, headers=headers, skip_auto_headers={"Cookie"}) as retry_resp:
                    retry_resp.raise_for_status()
            else:
                resp.raise_for_status()

    async def async_turn_on(self, **kwargs: Any) -> None:
        try:
            # Dynamically grab the router's configured Guest SSID to build the payload
            ssid = self.coordinator.data.get("wifi_guest24", [{}])[0].get("guest24", {}).get("ssid", "WiFi-Guest")
            await self._async_trigger_put("wireless/guest24", ssid, "1")
            await self._async_trigger_put("wireless/guest5", ssid, "1")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to enable Guest Wireless Access: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            ssid = self.coordinator.data.get("wifi_guest24", [{}])[0].get("guest24", {}).get("ssid", "WiFi-Guest")
            await self._async_trigger_put("wireless/guest24", ssid, "0")
            await self._async_trigger_put("wireless/guest5", ssid, "0")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to disable Guest Wireless Access: %s", err)