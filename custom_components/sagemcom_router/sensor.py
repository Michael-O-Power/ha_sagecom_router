import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import (
    UnitOfDataRate,
    UnitOfTime,
    UnitOfInformation,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Define our sensor descriptions cleanly
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="network_type",
        name="Network Type",
        icon="mdi:signal-5g",
    ),
    SensorEntityDescription(
        key="sim_status",
        name="SIM Status",
        icon="mdi:sim",
    ),
    SensorEntityDescription(
        key="provider",
        name="Service Provider",
        icon="mdi:tower-cell",
    ),
    SensorEntityDescription(
        key="wan_status",
        name="Internet Connectivity",
        icon="mdi:earth",
    ),
    SensorEntityDescription(
        key="rsrp",
        name="5G Signal Strength (RSRP)",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal-cellular-3",
    ),
    SensorEntityDescription(
        key="session_duration",
        name="Session Duration",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:clock-outline",
    ),
    SensorEntityDescription(
        key="data_received",
        name="Data Received",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="data_sent",
        name="Data Sent",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:upload",
    ),
)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Sagemcom router sensors."""
    domain_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = domain_data["coordinator"]
    host = domain_data["host"]

    # Map the coordinator to our visual sensors
    entities = [SagemcomSensor(coordinator, entry.entry_id, host, description) for description in SENSOR_TYPES]
    async_add_entities(entities)


class SagemcomSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sagemcom Router sensor."""

    def __init__(self, coordinator, entry_id, host, description: SensorEntityDescription):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._host = host
        
        # Unique ID ensures HA remembers history and allows UI renaming
        self._attr_unique_id = f"sagemcom_{host}_{description.key}"

        # Tie this sensor to the central Router Device inside HA
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Sagemcom F@st 5866T 5G Modem",
            manufacturer="Sagemcom",
            model="F@st 5866T",
            configuration_url=f"http://{host}",
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get(self.entity_description.key)
        return None