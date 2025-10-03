"""Authentication helpers for Azure and TFE."""

import os
from pathlib import Path
from typing import Optional

from azure.identity import DefaultAzureCredential

from . import logger


def get_azure_credential(
        creds_file: Optional[str] = None) -> DefaultAzureCredential:
    """Get Azure credential using DefaultAzureCredential with optional custom credential file.

    Args:
        creds_file: Path to JSON file with Azure service principal credentials

    Returns:
        Azure credential object

    Raises:
        FileNotFoundError: If creds_file is specified but not found
        ValueError: If creds_file contains invalid JSON
    """
    if creds_file:
        creds_path = Path(creds_file)
        if not creds_path.exists():
            raise FileNotFoundError(
                f"Azure credentials file not found: {creds_file}")

        # For service principal from file, we rely on DefaultAzureCredential
        # which will pick up AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID from env
        # The creds file should set these environment variables before calling
        # this
        logger.get_logger(__name__).info(
            f"Using Azure credentials from file: {creds_file}"
        )

    # DefaultAzureCredential handles the fallback chain automatically:
    # 1. Environment variables (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)
    # 2. Azure CLI credentials (az login)
    # 3. Managed Identity (for CI/CD environments)
    return DefaultAzureCredential()


def get_tfe_token(
        token: Optional[str] = None,
        creds_file: Optional[str] = None) -> str:
    """Get TFE API token from various sources.

    Priority order:
    1. Direct token parameter
    2. TFE_TOKEN environment variable
    3. Credentials file

    Args:
        token: Direct token value
        creds_file: Path to file containing token

    Returns:
        TFE API token

    Raises:
        ValueError: If no token can be found
        FileNotFoundError: If creds_file is specified but not found
    """
    log = logger.get_logger(__name__)

    # 1. Direct token parameter
    if token:
        log.debug("Using TFE token from direct parameter")
        return token

    # 2. Environment variable
    env_token = os.getenv("TFE_TOKEN")
    if env_token:
        log.debug("Using TFE token from TFE_TOKEN environment variable")
        return env_token

    # 3. Credentials file
    if creds_file:
        creds_path = Path(creds_file)
        if not creds_path.exists():
            raise FileNotFoundError(
                f"TFE credentials file not found: {creds_file}")

        try:
            with open(creds_path, "r", encoding="utf-8") as f:
                file_token = f.read().strip()
                if file_token:
                    log.debug(f"Using TFE token from file: {creds_file}")
                    return file_token
        except IOError as e:
            raise ValueError(f"Failed to read TFE credentials file: {e}")

    # No token found
    raise ValueError(
        "TFE token not found. Provide via --tfe-token, TFE_TOKEN environment variable, "
        "or --tfe-creds-file parameter")


def load_azure_creds_from_file(creds_file: str) -> dict:
    """Load Azure service principal credentials from JSON file and set environment variables.

    Args:
        creds_file: Path to JSON credentials file

    Returns:
        Dict containing credential information

    Raises:
        FileNotFoundError: If file not found
        ValueError: If JSON is invalid or missing required fields
    """
    creds_path = Path(creds_file)
    if not creds_path.exists():
        raise FileNotFoundError(
            f"Azure credentials file not found: {creds_file}")

    try:
        import json

        with open(creds_path, "r", encoding="utf-8") as f:
            creds = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in Azure credentials file: {e}")

    # Validate required fields
    required_fields = ["client_id", "client_secret", "tenant_id"]
    missing_fields = [field for field in required_fields if field not in creds]
    if missing_fields:
        raise ValueError(
            f"Azure credentials file missing required fields: {missing_fields}"
        )

    # Set environment variables for DefaultAzureCredential
    os.environ["AZURE_CLIENT_ID"] = creds["client_id"]
    os.environ["AZURE_CLIENT_SECRET"] = creds["client_secret"]
    os.environ["AZURE_TENANT_ID"] = creds["tenant_id"]

    # Optional subscription_id
    if "subscription_id" in creds:
        os.environ["AZURE_SUBSCRIPTION_ID"] = creds["subscription_id"]

    logger.get_logger(__name__).info(
        f"Loaded Azure credentials from file: {creds_file}"
    )
    return creds
