"""Utility functions for Azure TFE Resources Toolkit."""

import re
import time
from functools import wraps
from typing import Any, Callable, TypeVar, cast
from urllib.parse import unquote

import requests

F = TypeVar("F", bound=Callable[..., Any])


class RetryableError(Exception):
    """Exception that should trigger a retry."""

    pass


class NonRetryableError(Exception):
    """Exception that should NOT trigger a retry."""

    pass


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: int = 1,
    max_delay: int = 30,
    backoff_factor: int = 2,
) -> Callable[[F], F]:
    """Decorator that implements exponential backoff retry logic.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        backoff_factor: Factor to multiply delay by on each retry

    Returns:
        Decorated function
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (
                    requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.RequestException,
                ) as e:
                    # Check if this is a retryable HTTP error
                    if isinstance(e, requests.exceptions.RequestException):
                        response = getattr(e, "response", None)
                        if response and response.status_code in [
                            429,
                            500,
                            502,
                            503,
                            504,
                        ]:
                            # Retryable server errors
                            pass
                        elif response and response.status_code in [400, 401, 403, 404]:
                            # Non-retryable client errors
                            raise NonRetryableError(
                                f"Non-retryable HTTP {response.status_code}: {e}"
                            ) from e
                        elif not response:
                            # Network-level errors are retryable
                            pass
                        else:
                            # Other HTTP errors - check if retryable
                            if response.status_code >= 500:
                                pass  # Server errors are retryable
                            else:
                                raise NonRetryableError(
                                    f"Non-retryable HTTP {response.status_code}: {e}"
                                ) from e

                    last_exception = e
                    if attempt == max_retries:
                        raise RetryableError(
                            f"Max retries exceeded: {e}") from e

                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Attempt {
                            attempt +
                            1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception

        return cast(F, wrapper)

    return decorator


def normalize_resource_id(resource_id: str) -> str:
    """Normalize Azure resource ID for case-insensitive matching.

    Args:
        resource_id: Azure resource ID to normalize

    Returns:
        Normalized resource ID (lowercase, no trailing slash)
    """
    if not resource_id:
        return ""

    # Convert to lowercase
    normalized = resource_id.lower()

    # Remove trailing slashes
    normalized = normalized.rstrip("/")

    # URL decode any encoded characters
    normalized = unquote(normalized)

    # Normalize subscription GUID format (ensure consistent formatting)
    # Azure resource IDs should already be properly formatted, but this
    # ensures consistency
    normalized = re.sub(
        r"/subscriptions/([a-f0-9-]{36})",
        lambda m: f"/subscriptions/{m.group(1).lower()}",
        normalized,
    )

    return normalized


def parse_provider_from_type(resource_type: str) -> str:
    """Extract provider namespace from Azure resource type.

    Args:
        resource_type: Azure resource type (e.g., 'Microsoft.Compute/virtualMachines')

    Returns:
        Provider namespace (e.g., 'Microsoft.Compute')
    """
    if "/" in resource_type:
        return resource_type.split("/")[0]
    return resource_type


def parse_provider_from_tfe_provider(provider_string: str) -> str:
    """Extract provider name from Terraform provider string.

    Args:
        provider_string: Terraform provider string (e.g., 'provider["registry.terraform.io/hashicorp/azurerm"]')

    Returns:
        Provider name (e.g., 'azurerm')
    """
    # Extract provider name from registry.terraform.io/hashicorp/azurerm format
    match = re.search(
        r'registry\.terraform\.io/[^/]+/([^"\]]+)',
        provider_string)
    if match:
        return match.group(1)

    # Fallback: extract from simpler formats
    match = re.search(r'provider\["([^"]+)"\]', provider_string)
    if match:
        provider = match.group(1)
        # Remove registry prefix if present
        if "/" in provider:
            provider = provider.split("/")[-1]
        return provider

    return "unknown"
