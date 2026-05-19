import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import (
    UnitOfTime,
    UnitOfInformation,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)

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
        "name": "System Uptime (s)",
        "path": ["device", 0, "device", "uptime"],
        "device_class": SensorDeviceClass.DURATION,
        "native_unit_of_measurement": UnitOfTime.SECONDS,
        "state_class": SensorStateClass.TOTAL_INCREASING
    },
    {
        "key": "uptime_formatted",
        "name": "System Uptime",
        "path": ["device", 0, "device", "uptime"],
        "icon": "mdi:clock-check-outline"
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
        "path": ["wan", "status"],
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
    {
        "key": "sim_status",
        "name": "SIM Status",
        "path": ["sim_status", 0, "cellular", "sim_status_extended"],
        "icon": "mdi:sim"
    },
    # --- NETWORK CLIENT COUNTERS ---
    {
        "key": "clients_ethernet",
        "name": "Active Ethernet Clients",
        "path": ["hosts", 0, "hosts", "list"],
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:lan-connect"
    },
    {
        "key": "clients_wifi",
        "name": "Active Wi-Fi Clients",
        "path": ["hosts", 0, "hosts", "list"],
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:wifi-star"
    },
    # --- CELLULAR DATA TRAFFIC METERING ---
    {
        "key": "session_duration",
        "name": "Cellular Session Duration",
        "path": ["session", 0, "cellular", "session", "duration"],
        "device_class": SensorDeviceClass.DURATION,
        "native_unit_of_measurement": UnitOfTime.HOURS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:clock-outline"
    },
    {
        "key": "bytes_received",
        "name": "Mobile Data Downloaded",
        "path": ["session", 0, "cellular", "session", "data", "received"],
        "device_class": SensorDeviceClass.DATA_SIZE,
        "native_unit_of_measurement": UnitOfInformation.BYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:download"
    },
    {
        "key": "data_received_gb",
        "name": "Data Received",
        "path": ["session", 0, "cellular", "session", "data", "received"],
        "device_class": SensorDeviceClass.DATA_SIZE,
        "native_unit_of_measurement": UnitOfInformation.GIGABYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:download-network"
    },
    {
        "key": "bytes_sent",
        "name": "Mobile Data Uploaded",
        "path": ["session", 0, "cellular", "session", "data", "sent"],
        "device_class": SensorDeviceClass.DATA_SIZE,
        "native_unit_of_measurement": UnitOfInformation.BYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:upload"
    },
    {
        "key": "data_sent_gb",
        "name": "Data Sent",
        "path": ["session", 0, "cellular", "session", "data", "sent"],
        "device_class": SensorDeviceClass.DATA_SIZE,
        "native_unit_of_measurement": UnitOfInformation.GIGABYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:upload-network"
    },
    # --- 4G LTE TELEMETRY ---
    {
        "key": "4g_rsrp",
        "name": "4G Signal Strength (RSRP)",
        "path": ["interface_4g", 0, "cellular", "interfaces", 0, "rsrp"],
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "native_unit_of_measurement": SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:signal-cellular-3"
    },
    {
        "key": "4g_rsrq",
        "name": "4G Signal Quality (RSRQ)",
        "path": ["interface_4g", 0, "cellular", "interfaces", 0, "rsrq"],
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:signal-cellular-outline"
    },
    {
        "key": "4g_sinr",
        "name": "4G Signal:Noise Ratio (SINR)",
        "path": ["interface_4g", 0, "cellular", "interfaces", 0, "connect_info", "sinr"],
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:signal-cellular-outline"
    },
    # --- 5G TELEMETRY ---
    {
        "key": "5g_rsrp",
        "name": "5G Signal Strength (RSRP)",
        "path": ["interface_5g", 0, "cellular", "interfaces", 0, "rsrp"],
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "native_unit_of_measurement": SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:signal-cellular-3"
    },
    {
        "key": "5g_rsrq",
        "name": "5G Signal Quality (RSRQ)",
        "path": ["interface_5g", 0, "cellular", "interfaces", 0, "rsrq"],
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:signal-cellular-outline"
    },
    {
        "key": "5g_sinr",
        "name": "5G Signal:Noise Ratio (SINR)",
        "path": ["interface_5g", 0, "cellular", "interfaces", 0, "connect_info", "sinr"],
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:signal-cellular-outline"
    },
    {
        "key": "5g_band",
        "name": "5G Band",
        "path": ["interface_5g", 0, "cellular", "interfaces", 0, "bandinfo"],
        "icon": "mdi:radio-tower"
    },
    # --- WIRELESS TRAFFIC COUNTERS ---
    {
        "key": "wifi_24_rx",
        "name": "Wi-Fi 2.4G Received Traffic",
        "path": ["wifi_24_stats", 0, "wireless", "ssid", "stats", "rx", "bytes"],
        "device_class": SensorDeviceClass.DATA_SIZE,
        "native_unit_of_measurement": UnitOfInformation.BYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING
    },
    {
        "key": "wifi_24_tx",
        "name": "Wi-Fi 2.4G Transmitted Traffic",
        "path": ["wifi_24_stats", 0, "wireless", "ssid", "stats", "tx", "bytes"],
        "device_class": SensorDeviceClass.DATA_SIZE,
        "native_unit_of_measurement": UnitOfInformation.BYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING
    },
    {
        "key": "wifi_5_rx",
        "name": "Wi-Fi 5G Received Traffic",
        "path": ["wifi_5_stats", 0, "wireless", "ssid", "stats", "rx", "bytes"],
        "device_class": SensorDeviceClass.DATA_SIZE,
        "native_unit_of_measurement": UnitOfInformation.BYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING
    },
    {
        "key": "wifi_5_tx",
        "name": "Wi-Fi 5G Transmitted Traffic",
        "path": ["wifi_5_stats", 0, "wireless", "ssid", "stats", "tx", "bytes"],
        "device_class": SensorDeviceClass.DATA_SIZE,
        "native_unit_of_measurement": UnitOfInformation.BYTES,
        "state_class": SensorStateClass.TOTAL_INCREASING
    },
)

# Granular hardware metrics exactly mapping the router's nested JSON
PORT_METRIC_DEFINITIONS = [
    {"key": "curbitrate", "suffix": "Link Speed", "icon": "mdi:speedometer", "unit": "Mbps"},
    {"dir": "tx", "key": "packets", "suffix": "Packets Sent", "icon": "mdi:upload", "class": SensorDeviceClass.DATA_SIZE, "unit": "packets"},
    {"dir": "rx", "key": "packets", "suffix": "Packets Received", "icon": "mdi:download", "class": SensorDeviceClass.DATA_SIZE, "unit": "packets"},
    {"dir": "tx", "key": "bytes", "suffix": "Bytes Sent", "icon": "mdi:upload", "class": SensorDeviceClass.DATA_SIZE, "unit": UnitOfInformation.BYTES},
    {"dir": "rx", "key": "bytes", "suffix": "Bytes Received", "icon": "mdi:download", "class": SensorDeviceClass.DATA_SIZE, "unit": UnitOfInformation.BYTES},
    {"dir": "tx", "key": "packetserrors", "suffix": "Errors Sent", "icon": "mdi:alert-outline", "unit": "errors"},
    {"dir": "rx", "key": "packetserrors", "suffix": "Errors Received", "icon": "mdi:alert-outline", "unit": "errors"},
    {"dir": "tx", "key": "packetsdiscards", "suffix": "Discarded Packets Sent", "icon": "mdi:delete-empty", "unit": "packets"},
    {"dir": "rx", "key": "packetsdiscards", "suffix": "Discarded Packets Received", "icon": "mdi:delete-empty", "unit": "packets"},
    {"dir": "tx", "key": "unicastpackets", "suffix": "Unicast Packets Sent", "icon": "mdi:arrow-up-bold", "unit": "packets"},
    {"dir": "rx", "key": "unicastpackets", "suffix": "Unicast Packets Received", "icon": "mdi:arrow-down-bold", "unit": "packets"},
    {"dir": "tx", "key": "multicastpackets", "suffix": "Multicast Packets Sent", "icon": "mdi:groups", "unit": "packets"},
    {"dir": "rx", "key": "multicastpackets", "suffix": "Multicast Packets Received", "icon": "mdi:groups", "unit": "packets"},
    {"dir": "tx", "key": "broadcastpackets", "suffix": "Broadcast Packets Sent", "icon": "mdi:bullhorn-variant", "unit": "packets"},
    {"dir": "rx", "key": "broadcastpackets", "suffix": "Broadcast Packets Received", "icon": "mdi:bullhorn-variant", "unit": "packets"},
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up platform entities based on parsed layout descriptors."""
    domain_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = domain_data["coordinator"]
    host = domain_data["host"]
    
    entities = [SagemcomRouterSensor(coordinator, description, entry.entry_id, host) for description in SENSOR_TYPES]
    
    # Spawn ETH0, ETH1, ETH2 as Independent Hardware Devices
    if coordinator.data and "lan_stats" in coordinator.data:
        interfaces = safe_get(coordinator.data, ["lan_stats", 0, "lan", "interfaces"], [])
        for idx, iface in enumerate(interfaces):
            port_label = iface.get("name", f"eth{idx}")
            for metric in PORT_METRIC_DEFINITIONS:
                entities.append(SagemcomEthernetPortSensor(coordinator, entry.entry_id, host, idx, port_label, metric))

    # Spawn Connected Clients as Independent Devices (Adds MAC address sensing)
    if coordinator.data and "hosts" in coordinator.data:
        clients = safe_get(coordinator.data, ["hosts", 0, "hosts", "list"], [])
        for client in clients:
            mac = client.get("macaddress")
            if not mac or mac == "unknown":
                continue
                
            hostname = client.get("hostname") or f"Device-{mac[-5:].replace(':', '')}"
            
            entities.append(SagemcomClientSensor(coordinator, entry.entry_id, mac, hostname, "status", "Connection Status", "mdi:lan-pending"))
            entities.append(SagemcomClientSensor(coordinator, entry.entry_id, mac, hostname, "ipaddress", "IP Address", "mdi:ip"))
            entities.append(SagemcomClientSensor(coordinator, entry.entry_id, mac, hostname, "macaddress", "MAC Address", "mdi:network-outline"))
            
            if client.get("link") == "Ethernet":
                entities.append(SagemcomClientSensor(coordinator, entry.entry_id, mac, hostname, "speed", "Link Speed", "mdi:ethernet-cable", "Mbps"))
            else:
                entities.append(SagemcomClientSensor(coordinator, entry.entry_id, mac, hostname, "rssi", "Signal Strength", "mdi:wifi", "dBm"))

    async_add_entities(entities)


class SagemcomRouterSensor(CoordinatorEntity, SensorEntity):
    """Core tracking properties representing logical device fields."""
    def __init__(self, coordinator, description, entry_id, host):
        super().__init__(coordinator)
        self._description = description
        
        self._attr_unique_id = f"sagemcom_{host}_{description['key']}"
        self._attr_name = f"{description['name']}"
        self._attr_device_class = description.get("device_class")
        self._attr_native_unit_of_measurement = description.get("native_unit_of_measurement")
        self._attr_state_class = description.get("state_class")
        self._attr_icon = description.get("icon")
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Sagemcom F@st 5866T 5G Modem",
            "manufacturer": "Sagemcom",
            "model": "F@st 5866T",
            "configuration_url": f"http://{host}",
        }

    @property
    def native_value(self):
        """Derive the type-casted tracking value using structural dictionary layout keys."""
        if not self.coordinator.data:
            return None
            
        raw_val = safe_get(self.coordinator.data, self._description["path"])
        
        if self._description["key"] == "clients_ethernet" and isinstance(raw_val, list):
            return sum(1 for c in raw_val if c.get("active") and c.get("link") == "Ethernet")
            
        if self._description["key"] == "clients_wifi" and isinstance(raw_val, list):
            return sum(1 for c in raw_val if c.get("active") and c.get("link") != "Ethernet")
        
        if raw_val is None or raw_val == "":
            return None
            
        if self._description["key"] == "uptime_formatted":
            seconds = int(raw_val)
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            return f"{h}h {m}m {s}s"
            
        if self._description["key"] in ["data_received_gb", "data_sent_gb"]:
            return round(int(raw_val) / (1024 ** 3), 2)
            
        if self._description["key"] == "session_duration":
            return round(int(raw_val) / 3600, 2)
            
        if self._attr_device_class in [SensorDeviceClass.DATA_SIZE, SensorDeviceClass.SIGNAL_STRENGTH, SensorDeviceClass.DURATION]:
            return int(raw_val)
            
        return raw_val


class SagemcomEthernetPortSensor(CoordinatorEntity, SensorEntity):
    """Spawns physical LAN ports as independent Hardware Devices, handling Disconnected states securely."""
    def __init__(self, coordinator, entry_id, host, index, port_name, metric_def):
        super().__init__(coordinator)
        self._index = index
        self._port_name = port_name
        self._metric_key = metric_def["key"]
        self._metric_def = metric_def
        
        self._attr_unique_id = f"sagemcom_{host}_lan_{port_name}_{self._metric_key}"
        self._attr_name = f"LAN Port {port_name.upper()} {metric_def['suffix']}"
        self._attr_icon = metric_def["icon"]
        
        if "class" in metric_def:
            self._attr_device_class = metric_def["class"]
        if "unit" in metric_def:
            self._attr_native_unit_of_measurement = metric_def["unit"]
            
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_lan_{port_name}")},
            name=f"LAN Port {port_name.upper()}",
            manufacturer="Sagemcom Interface",
            via_device=(DOMAIN, entry_id)
        )

    @property
    def native_value(self):
        """Parse raw values adaptive to nested trees, returning None (Unavailable) if cable unplugged."""
        if not self.coordinator.data:
            return None
            
        base_path = ["lan_stats", 0, "lan", "interfaces", self._index]
        status = safe_get(self.coordinator.data, base_path + ["status"])
        
        if status != "Up":
            if self._metric_key == "curbitrate":
                return "Disconnected"
            # Return None to force 'Unavailable' in the UI so numerical graphs don't crash to 0
            return None
            
        if self._metric_key == "curbitrate":
            speed = safe_get(self.coordinator.data, base_path + ["curbitrate"])
            return int(speed) if speed else 0
            
        dir_key = self._metric_def.get("dir")
        if dir_key:
            val = safe_get(self.coordinator.data, base_path + [dir_key, self._metric_key])
            if val is not None and str(val).strip() != "":
                # Sagemcom 32-bit int rollover bug fix: force abs() value
                return abs(int(val))
                
        return 0


class SagemcomClientSensor(CoordinatorEntity, SensorEntity):
    """Spawns Connected Clients as independent devices linked to the Router."""
    def __init__(self, coordinator, entry_id, mac, hostname, metric_key, metric_name, icon, unit=None):
        super().__init__(coordinator)
        self._mac = mac
        self._metric_key = metric_key
        
        self._attr_unique_id = f"sagemcom_client_{mac}_{metric_key}"
        self._attr_name = metric_name
        self._attr_icon = icon
        if unit:
            self._attr_native_unit_of_measurement = unit
            
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=hostname,
            manufacturer="Network Client",
            via_device=(DOMAIN, entry_id)
        )

    @property
    def native_value(self):
        """Secure lookup evaluating dropping connections gracefully."""
        if not self.coordinator.data:
            return None
            
        clients = safe_get(self.coordinator.data, ["hosts", 0, "hosts", "list"], [])
        for client in clients:
            if client.get("macaddress") == self._mac:
                if self._metric_key == "status":
                    return "Connected" if client.get("active") else "Disconnected"
                    
                if not client.get("active"):
                    return "Disconnected" if self._metric_key == "speed" else None
                    
                if self._metric_key == "ipaddress":
                    return client.get("ipaddress")
                if self._metric_key == "macaddress":
                    return self._mac
                if self._metric_key == "speed":
                    return safe_get(client, ["ethernet", "speed"]) or 0
                if self._metric_key == "rssi":
                    rssi_val = safe_get(client, ["wireless", "rssi0"]) or client.get("rssi")
                    return int(rssi_val) if rssi_val else None
                    
        return "Disconnected" if self._metric_key == "status" else None