import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import UnitOfInformation, UnitOfTime, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

def safe_get(data, path, default=None):
    """Safely travel down highly nested list/dict structures."""
    current = data
    for key in path:
        if isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError):
                return default
        elif isinstance(current, dict):
            current = current.get(key)
        else:
            return default
        if current is None:
            return default
    return current

# Definition mapping matching the hardware data dumps
SENSOR_TYPES = (
    # --- CORE SYSTEM INFO ---
    {
        "key": "model_name",
        "name": "Model Name",
        "path": ["device", 0, "device", "modelname"],
        "icon": "mdi:router"
    },
    {
        "key": "software_version",
        "name": "Firmware Version",
        "path": ["device", 0, "device", "main", "version"],
        "icon": "mdi:package-up"
    },
    {
        "key": "uptime",
        "name": "System Uptime",
        "path": ["device", 0, "device", "uptime"],
        "device_class": SensorDeviceClass.DURATION,
        "native_unit_of_measurement": UnitOfTime.SECONDS,
        "state_class": SensorStateClass.TOTAL_INCREASING
    },
    {
        "key": "boot_count",
        "name": "Boot Counter",
        "path": ["device", 0, "device", "numberofboots"],
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:counter"
    },
    # --- WAN & NETWORK IDENTIFIERS ---
    {
        "key": "wan_status",
        "name": "WAN Link Status",
        "path": ["wan_status", "status"],
        "icon": "mdi:wan"
    },
    {
        "key": "network_type",
        "name": "Cellular Generation",
        "path": ["network_type", "cellular", "network_type"],
        "icon": "mdi:signal-cellular-5g"
    },
    {
        "key": "provider",
        "name": "Network Carrier",
        "path": ["provider", "cellular", "provider"],
        "icon": "mdi:antenna"
    },
    # --- CELLULAR DATA TRAFFIC METERING ---
    {
        "key": "session_duration",
        "name": "Cellular Session Duration",
        "path": ["session", 0, "cellular", "session", "duration"],
        "device_class": SensorDeviceClass.DURATION,
        "native_unit_of_measurement": UnitOfTime.SECONDS,
        "state_class": SensorStateClass.TOTAL_INCREASING
    },
    {
        "key": "bytes_received",
        "name": "Mobile Data Downloaded",
        "path": ["session", 0, "cellular", "session", "data", "received"],
        "device_class": SensorDeviceClass.DATA,
        "native_unit_of_measurement": UnitOfInformation.BYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING
    },
    {
        "key": "bytes_sent",
        "name": "Mobile Data Uploaded",
        "path": ["session", 0, "cellular", "session", "data", "sent"],
        "device_class": SensorDeviceClass.DATA,
        "native_unit_of_measurement": UnitOfInformation.BYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING
    },
    # --- 4G LTE TELEMETRY ---
    {
        "key": "4g_rsrp",
        "name": "4G RSRP",
        "path": ["cellular_4g", 0, "cellular", "interfaces", 0, "rsrp"],
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "native_unit_of_measurement": SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        "state_class": SensorStateClass.MEASUREMENT
    },
    {
        "key": "4g_rsrq",
        "name": "4G RSRQ",
        "path": ["cellular_4g", 0, "cellular", "interfaces", 0, "rsrq"],
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:signal-cellular-outline"
    },
    {
        "key": "4g_sinr",
        "name": "4G SINR",
        "path": ["cellular_4g", 0, "cellular", "interfaces", 0, "connect_info", "sinr"],
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:signal-cellular-outline"
    },
    # --- 5G TELEMETRY ---
    {
        "key": "5g_rsrp",
        "name": "5G RSRP",
        "path": ["cellular_5g", 0, "cellular", "interfaces", 0, "rsrp"],
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "native_unit_of_measurement": SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        "state_class": SensorStateClass.MEASUREMENT
    },
    {
        "key": "5g_rsrq",
        "name": "5G RSRQ",
        "path": ["cellular_5g", 0, "cellular", "interfaces", 0, "rsrq"],
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:signal-cellular-outline"
    },
    {
        "key": "5g_sinr",
        "name": "5G SINR",
        "path": ["cellular_5g", 0, "cellular", "interfaces", 0, "connect_info", "sinr"],
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:signal-cellular-outline"
    },
    # --- WIRELESS TRAFFIC COUNTERS ---
    {
        "key": "wifi_24_rx",
        "name": "Wi-Fi 2.4G Received Traffic",
        "path": ["wifi_24_stats", 0, "wireless", "ssid", "stats", "rx", "bytes"],
        "device_class": SensorDeviceClass.DATA,
        "native_unit_of_measurement": UnitOfInformation.BYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING
    },
    {
        "key": "wifi_24_tx",
        "name": "Wi-Fi 2.4G Transmitted Traffic",
        "path": ["wifi_24_stats", 0, "wireless", "ssid", "stats", "tx", "bytes"],
        "device_class": SensorDeviceClass.DATA,
        "native_unit_of_measurement": UnitOfInformation.BYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING
    },
    {
        "key": "wifi_5_rx",
        "name": "Wi-Fi 5G Received Traffic",
        "path": ["wifi_5_stats", 0, "wireless", "ssid", "stats", "rx", "bytes"],
        "device_class": SensorDeviceClass.DATA,
        "native_unit_of_measurement": UnitOfInformation.BYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING
    },
    {
        "key": "wifi_5_tx",
        "name": "Wi-Fi 5G Transmitted Traffic",
        "path": ["wifi_5_stats", 0, "wireless", "ssid", "stats", "tx", "bytes"],
        "device_class": SensorDeviceClass.DATA,
        "native_unit_of_measurement": UnitOfInformation.BYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING
    },
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up platform entities based on parsed layout descriptors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [SagemcomRouterSensor(coordinator, description, entry) for description in SENSOR_TYPES]
    
    # Extract Ethernet ports dynamically from the LAN metrics array
    if coordinator.data and "lan_stats" in coordinator.data:
        interfaces = safe_get(coordinator.data, ["lan_stats", 0, "lan", "interfaces"], [])
        for idx, iface in enumerate(interfaces):
            entities.append(SagemcomEthernetSensor(coordinator, entry, idx, iface.get("name", f"eth{idx}")))

    async_add_entities(entities)

class SagemcomRouterSensor(CoordinatorEntity, SensorEntity):
    """Core tracking properties representing logical device fields."""

    def __init__(self, coordinator, description, entry):
        """Initialize operational metric attributes."""
        super().__init__(coordinator)
        self._description = description
        self._entry = entry
        
        self._attr_unique_id = f"{entry.entry_id}_{description['key']}"
        self._attr_name = f"Sagemcom {description['name']}"
        self._attr_device_class = description.get("device_class")
        self._attr_native_unit_of_measurement = description.get("native_unit_of_measurement")
        self._attr_state_class = description.get("state_class")
        self._attr_icon = description.get("icon")
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Sagemcom 5G Router",
            "manufacturer": "Sagemcom",
            "model": "F@st 5866T",
        }

    @property
    def native_value(self):
        """Derive the type-casted tracking value using structural dictionary layout keys."""
        raw_val = safe_get(self.coordinator.data, self._description["path"])
        if raw_val is None:
            return None
        if self._attr_device_class in [SensorDeviceClass.DATA, SensorDeviceClass.DURATION, SensorDeviceClass.SIGNAL_STRENGTH]:
            return int(raw_val)
        return raw_val

class SagemcomEthernetSensor(CoordinatorEntity, SensorEntity):
    """Dynamic tracker managing individual wired LAN port connectivity statuses."""

    def __init__(self, coordinator, entry, index, port_name):
        """Initialize individual connection node attributes."""
        super().__init__(coordinator)
        self._entry = entry
        self._index = index
        self._port_name = port_name
        
        self._attr_unique_id = f"{entry.entry_id}_lan_{port_name}"
        self._attr_name = f"Sagemcom LAN Port {port_name.upper()} Link Speed"
        self._attr_icon = "mdi:ethernet-cable"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
        }

    @property
    def native_value(self):
        """Render current link throughput metrics or identify unplugged cables."""
        status = safe_get(self.coordinator.data, ["lan_stats", 0, "lan", "interfaces", self._index, "status"])
        speed = safe_get(self.coordinator.data, ["lan_stats", 0, "lan", "interfaces", self._index, "curbitrate"])
        
        if status == "Up":
            return f"{speed} Mbps" if speed else "Connected"
        return "Disconnected"