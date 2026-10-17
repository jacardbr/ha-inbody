"""Constants for the InBody integration."""

DOMAIN = "inbody"

CONF_LOGIN_ID = "login_id"
CONF_PASSWORD = "password"
CONF_COUNTRY = "country"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_COUNTRY = "BR"
DEFAULT_SCAN_INTERVAL = 30  # minutes
MIN_SCAN_INTERVAL = 5  # minutes
MAX_SCAN_INTERVAL = 1440  # minutes
