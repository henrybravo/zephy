"""Configuration management for Azure TFE Resources Toolkit."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AzureResource:
    """Azure resource data model."""

    id: str
    name: str
    type: str
    resource_group: str
    location: str
    provider: str
    raw_data: dict


@dataclass
class TFEResource:
    """Terraform Enterprise resource data model."""

    id: str
    name: str
    type: str
    provider: str
    workspace: str
    module_path: str
    raw_data: dict


@dataclass
class MatchResult:
    """Resource matching result."""

    azure_resource: Optional[AzureResource]
    tfe_resources: List[TFEResource]
    match_status: str  # 'matched', 'unmanaged', 'orphaned'
    resource_group: str
    workspace_names: List[str]


@dataclass
class ComparisonReport:
    """Complete comparison report."""

    matches: List[MatchResult]
    total_azure_resources: int
    total_tfe_resources: int
    matched_count: int
    unmanaged_count: int
    orphaned_count: int
    multi_workspace_count: int


@dataclass
class Config:
    """Configuration for Azure TFE Resources Toolkit."""

    # Required arguments
    tfe_org: str = ""
    azure_subscription: str = ""

    # Optional filtering
    workspaces: List[str] = field(default_factory=list)
    resource_groups: List[str] = field(default_factory=list)

    # Authentication
    tfe_token: Optional[str] = None
    tfe_creds_file: Optional[str] = None
    azure_creds_file: Optional[str] = None
    azcli_manually: bool = False
    azure_input_file: Optional[str] = None

    # TFE configuration
    tfe_base_url: str = "https://app.terraform.io/api/v2"
    tfe_ssl_verify: bool = True

    # Processing options
    resource_mode: str = "primary"  # 'primary' or 'detailed'
    cache_ttl: int = 60  # minutes
    no_cache: bool = False

    # Output options
    output_dir: str = "."
    save_resources: bool = False
    logfile_dir: str = "."

    # Execution options
    debug: bool = False
    dry_run: bool = False
    parallel: int = 10

    # Config file path (not in config file itself)
    config_file: Optional[str] = None

    def __post_init__(self):
        """Validate configuration after initialization."""
        # Only validate non-required fields here
        if self.resource_mode not in ["primary", "detailed"]:
            raise ValueError("resource_mode must be 'primary' or 'detailed'")

        if self.cache_ttl < 0:
            raise ValueError("cache_ttl must be non-negative")

        if self.parallel < 1:
            raise ValueError("parallel must be at least 1")


def load_config_from_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")

    # Validate field names and types
    valid_fields = {
        "tfe_org": str,
        "azure_subscription": str,
        "workspaces": (list, str),
        "resource_groups": (list, str),
        "tfe_token": str,
        "tfe_creds_file": str,
        "azure_creds_file": str,
        "azcli_manually": bool,
        "azure_input_file": (str, type(None)),
        "tfe_base_url": str,
        "tfe_ssl_verify": bool,
        "resource_mode": str,
        "cache_ttl": int,
        "no_cache": bool,
        "output_dir": str,
        "save_resources": bool,
        "logfile_dir": str,
        "debug": bool,
        "dry_run": bool,
        "parallel": int,
    }

    unknown_fields = []
    for key in data:
        if key not in valid_fields:
            unknown_fields.append(key)

    if unknown_fields:
        logger.warning(
            f"Unknown fields in config file: {
                ', '.join(unknown_fields)}")

    # Check for credentials in config file
    credential_fields = ["tfe_token"]
    for field in credential_fields:
        if field in data and data[field]:
            logger.warning(
                f"Config file contains credential field '{field}'. Consider using environment variables instead.")

    # Normalize array fields (accept both lists and comma-separated strings)
    for field_name in ["workspaces", "resource_groups"]:
        if field_name in data:
            value = data[field_name]
            if isinstance(value, str):
                data[field_name] = [
                    item.strip() for item in value.split(",") if item.strip()
                ]
            elif isinstance(value, list):
                data[field_name] = [str(item) for item in value]
            else:
                raise ValueError(
                    f"Field '{field_name}' must be a list or comma-separated string"
                )

    return data


def merge_configs(
    cli_args: Dict[str, Any], config_file_data: Optional[Dict[str, Any]] = None
) -> Config:
    """Merge CLI arguments with config file data (CLI takes precedence)."""
    # Start with defaults
    merged = {
        "tfe_org": "",
        "azure_subscription": "",
        "workspaces": [],
        "resource_groups": [],
        "tfe_token": None,
        "tfe_creds_file": None,
        "azure_creds_file": None,
        "azcli_manually": False,
        "azure_input_file": None,
        "tfe_base_url": "https://app.terraform.io/api/v2",
        "tfe_ssl_verify": True,
        "resource_mode": "primary",
        "cache_ttl": 60,
        "no_cache": False,
        "output_dir": ".",
        "save_resources": False,
        "logfile_dir": ".",
        "debug": False,
        "dry_run": False,
        "parallel": 10,
        "config_file": cli_args.get("config"),
    }

    # Apply config file values
    if config_file_data:
        for key, value in config_file_data.items():
            if key in merged:
                merged[key] = value

    # Apply CLI arguments (highest priority) - only if they were actually provided
    # CLI args that weren't provided will have None values
    for key, value in cli_args.items():
        if key in merged and value is not None:
            merged[key] = value

    return Config(**merged)  # type: ignore[arg-type]
