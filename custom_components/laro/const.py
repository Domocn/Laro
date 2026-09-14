"""Constants for Laro integration."""

DOMAIN = "laro"
CONF_URL = "url"
CONF_TOKEN = "token"

# Default values
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

# Platforms
PLATFORMS = ["sensor", "calendar"]

# Services
SERVICE_ADD_TO_SHOPPING_LIST = "add_to_shopping_list"
SERVICE_CREATE_MEAL_PLAN = "create_meal_plan"
SERVICE_IMPORT_RECIPE = "import_recipe"

# Attributes
ATTR_RECIPE_ID = "recipe_id"
ATTR_RECIPE_NAME = "recipe_name"
ATTR_DATE = "date"
ATTR_MEAL_TYPE = "meal_type"
ATTR_ITEMS = "items"
ATTR_URL = "url"
