"""Constants for the Mạnh Quân Solar integration."""

from typing import Final

DOMAIN: Final = "mqsolar_local"
CONF_HOST: Final = "host"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_TOPIC_CODE: Final = "topic_code"
ATTR_CONFIRM: Final = "confirm"
ATTR_CHARGE_MODE: Final = "charge_mode"
ATTR_MAX_CURRENT: Final = "max_current"
ATTR_MAX_VOLTAGE: Final = "max_voltage"

DEFAULT_MQTT_TOPIC_CODE: Final = "45a"
MQTT_RESPONSE_TIMEOUT: Final = 8
MQTT_TOPIC_DISCOVERY_TIMEOUT: Final = 4

SERVICE_RESTART: Final = "restart"
SERVICE_REBOOT_CHARGE: Final = "reboot_charge"
SERVICE_GET_CHARGER_CONFIG: Final = "get_charger_config"
SERVICE_SET_CHARGER_CONFIG: Final = "set_charger_config"

API_STATUS: Final = "/api/status"
API_CHARGER_DATA: Final = "/api/charger/data"
API_INVERTER_DATA: Final = "/api/data"

REQUEST_TIMEOUT: Final = 5
SCAN_TIMEOUT: Final = 1
SCAN_CONCURRENCY: Final = 48
UPDATE_INTERVAL_SECONDS: Final = 1
