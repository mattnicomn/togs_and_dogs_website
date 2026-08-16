"""Single runtime boundary for generated service and window metadata."""

from common.generated_service_types import SERVICE_TYPES


SERVICE_METADATA = SERVICE_TYPES["services"]
WINDOW_METADATA = SERVICE_TYPES["windows"]
ALL_WINDOW_IDS = tuple(WINDOW_METADATA)
