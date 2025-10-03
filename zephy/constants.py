"""Constants for Azure TFE Resources Toolkit."""

import json
from pathlib import Path

# Default API URLs (can be overridden in config)
DEFAULT_TFE_BASE_URL = "https://app.terraform.io/api/v2"

# Retry configuration
RETRY_MAX_ATTEMPTS = 3
RETRY_INITIAL_DELAY = 1
RETRY_MAX_DELAY = 30
RETRY_BACKOFF_FACTOR = 2

# Rate limiting
TFE_RATE_LIMIT_REQUESTS_PER_SECOND = 30


# Primary resource types (default filtering mode) - loaded from JSON file
def _load_primary_resource_types() -> list[str]:
    """Load primary resource types from JSON file."""
    # Try package location first, then parent directory
    json_paths = [
        Path(__file__).parent / "PRIMARY_RESOURCE_TYPES.json",
        Path(__file__).parent.parent / "PRIMARY_RESOURCE_TYPES.json",
    ]

    for json_path in json_paths:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            continue

    # If both locations fail, fallback to basic list
    print(
        f"Warning: Could not load PRIMARY_RESOURCE_TYPES.json from any location. "
        f"Tried: {', '.join(str(p) for p in json_paths)}"
    )
    return [
        "Microsoft.Compute/virtualMachines",
        "Microsoft.Web/sites",
        "Microsoft.Storage/storageAccounts",
        "Microsoft.Sql/servers",
        "Microsoft.ContainerService/managedClusters",
    ]


PRIMARY_RESOURCE_TYPES = _load_primary_resource_types()
