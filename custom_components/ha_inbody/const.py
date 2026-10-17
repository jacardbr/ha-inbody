"""Constants for the InBody integration."""

DOMAIN = "ha_inbody"

CONF_LOGIN_ID = "login_id"
CONF_PASSWORD = "password"
CONF_COUNTRY = "country"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_IMPORT_HISTORY = "import_history"  # one-shot flag set by the setup form

DEFAULT_COUNTRY = "BR"
DEFAULT_SCAN_INTERVAL = 30  # minutes
MIN_SCAN_INTERVAL = 5  # minutes
MAX_SCAN_INTERVAL = 1440  # minutes
