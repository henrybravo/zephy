"""Azure Resource Manager API client."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.resources.models import GenericResource

from .config import AzureResource
from .constants import PRIMARY_RESOURCE_TYPES
from .utils import parse_provider_from_type

from . import logger


class AzureClient:
    """Client for Azure Resource Manager API."""

    def __init__(self, credential: DefaultAzureCredential, subscription_id: str):
        """Initialize Azure client.

        Args:
            credential: Azure credential object
            subscription_id: Azure subscription ID
        """
        self.credential = credential
        self.subscription_id = subscription_id
        self.client = ResourceManagementClient(credential, subscription_id)
        self.log = logger.get_logger(__name__)

    def get_resource_groups(self, rg_filter: Optional[List[str]] = None) -> List[str]:
        """Get all resource groups in subscription, optionally filtered.

        Args:
            rg_filter: List of resource group names to include (None for all)

        Returns:
            List of resource group names
        """
        try:
            resource_groups = []
            for rg in self.client.resource_groups.list():
                rg_name = rg.name
                if rg_filter is None or rg_name in rg_filter:
                    resource_groups.append(rg_name)

            self.log.info(
                f"Retrieved {len(resource_groups)} resource groups from Azure subscription"
            )
            return resource_groups

        except Exception as e:
            self.log.error(f"Failed to get resource groups: {e}")
            raise

    def get_resource_group_tags(self) -> Dict[str, str]:
        """Get tags for all resource groups in subscription.

        Returns:
            Dict mapping resource group name to tags string (pipe-separated)
        """
        try:
            rg_tags = {}
            for rg in self.client.resource_groups.list():
                tags = rg.tags or {}
                # Convert tags dict to pipe-separated string
                tags_str = "|".join(f"{k}:{v}" for k, v in tags.items()) if tags else ""
                rg_tags[rg.name] = tags_str

            self.log.debug(f"Retrieved tags for {len(rg_tags)} resource groups")
            return rg_tags

        except Exception as e:
            self.log.error(f"Failed to get resource group tags: {e}")
            raise

    def get_resources_in_subscription(
        self, resource_mode: str = "primary", rg_tags: Optional[Dict[str, str]] = None
    ) -> List[AzureResource]:
        """Get all resources in subscription using efficient single API call.

        Args:
            resource_mode: 'primary' or 'detailed'
            rg_tags: Dict mapping resource group names to tags strings

        Returns:
            List of AzureResource objects
        """
        try:
            resources = []
            # Use list() for all resources in subscription - more efficient
            # than per-RG
            for resource in self.client.resources.list():
                azure_resource = self._convert_to_azure_resource(resource, rg_tags)
                if self._should_include_resource(azure_resource, resource_mode):
                    resources.append(azure_resource)

            self.log.info(
                f"Retrieved {len(resources)} resources from Azure subscription (mode: {resource_mode})"
            )
            return resources

        except Exception as e:
            self.log.error(f"Failed to get resources from subscription: {e}")
            raise

    def get_resources_in_resource_group(
        self,
        resource_group: str,
        resource_mode: str = "primary",
        rg_tags: Optional[Dict[str, str]] = None,
    ) -> List[AzureResource]:
        """Get all resources in a specific resource group.

        Args:
            resource_group: Resource group name
            resource_mode: 'primary' or 'detailed'
            rg_tags: Dict mapping resource group names to tags strings

        Returns:
            List of AzureResource objects
        """
        try:
            resources = []
            for resource in self.client.resources.list_by_resource_group(
                resource_group
            ):
                azure_resource = self._convert_to_azure_resource(resource, rg_tags)
                if self._should_include_resource(azure_resource, resource_mode):
                    resources.append(azure_resource)

            self.log.debug(
                f"Retrieved {len(resources)} resources from resource group '{resource_group}'"
            )
            return resources

        except Exception as e:
            self.log.error(
                f"Failed to get resources from resource group '{resource_group}': {e}"
            )
            raise

    def _convert_to_azure_resource(
        self, resource: GenericResource, rg_tags: Optional[Dict[str, str]] = None
    ) -> AzureResource:
        """Convert Azure SDK resource object to AzureResource dataclass.

        Args:
            resource: Azure SDK GenericResource object
            rg_tags: Dict mapping resource group names to tags strings

        Returns:
            AzureResource object
        """
        rid = resource.id or ""
        rg_name = self._extract_resource_group_from_id(rid)
        tags_str = (rg_tags or {}).get(rg_name, "")
        return AzureResource(
            id=rid.lower(),
            name=resource.name or "",
            type=resource.type or "",
            resource_group=rg_name,
            location=resource.location or "",
            provider=parse_provider_from_type(resource.type or ""),
            rg_tags=tags_str,
            raw_data={
                "id": resource.id,
                "name": resource.name,
                "type": resource.type,
                "location": resource.location,
                "tags": resource.tags,
                "sku": resource.sku.as_dict() if resource.sku else None,
            },
        )

    def _extract_resource_group_from_id(self, resource_id: str) -> str:
        """Extract resource group name from Azure resource ID.

        Args:
            resource_id: Azure resource ID

        Returns:
            Resource group name
        """
        if not resource_id:
            return ""

        # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/...
        parts = resource_id.split("/")
        try:
            rg_index = parts.index("resourceGroups")
            return parts[rg_index + 1]
        except (ValueError, IndexError):
            return ""

    def _should_include_resource(
        self, resource: AzureResource, resource_mode: str
    ) -> bool:
        """Determine if resource should be included based on mode.

        Args:
            resource: AzureResource object
            resource_mode: 'primary' or 'detailed'

        Returns:
            True if resource should be included
        """
        if resource_mode == "detailed":
            return True  # Include all resources

        if resource_mode == "primary":
            return resource.type in PRIMARY_RESOURCE_TYPES

        return False

    def get_all_resources(
        self, rg_filter: Optional[List[str]] = None, resource_mode: str = "primary"
    ) -> List[AzureResource]:
        """Get all resources, optionally filtered by resource groups.

        Args:
            rg_filter: List of resource group names to include
            resource_mode: 'primary' or 'detailed'

        Returns:
            List of AzureResource objects
        """
        # Get resource group tags
        rg_tags = self.get_resource_group_tags()

        if rg_filter:
            # Get resources from specific resource groups
            all_resources = []
            for rg in rg_filter:
                try:
                    resources = self.get_resources_in_resource_group(
                        rg, resource_mode, rg_tags
                    )
                    all_resources.extend(resources)
                except Exception as e:
                    self.log.warning(f"Skipping resource group '{rg}': {e}")
                    continue
            return all_resources
        else:
            # Get all resources in subscription
            return self.get_resources_in_subscription(resource_mode, rg_tags)


def load_resources_from_json_file(
    file_path: str, rg_tags_file: Optional[str] = None
) -> List[AzureResource]:
    """Load Azure resources from JSON file (for manual CLI mode).

    Args:
        file_path: Path to JSON file from 'az resource list'
        rg_tags_file: Optional path to JSON file from 'az group list' for resource group tags

    Returns:
        List of AzureResource objects

    Raises:
        FileNotFoundError: If file not found
        ValueError: If JSON is invalid
    """
    json_path = Path(file_path)
    if not json_path.exists():
        raise FileNotFoundError(f"Azure resources file not found: {file_path}")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in Azure resources file: {e}")

    # Validate data is a list
    if not isinstance(data, list):
        raise ValueError("Azure resources file must contain a JSON array")

    # Load resource group tags if file provided
    rg_tags_map: Dict[str, str] = {}
    if rg_tags_file:
        rg_tags_map = _load_resource_group_tags_from_file(rg_tags_file)

    resources = []
    for item in data:
        # Validate item is dict
        if not isinstance(item, dict):
            raise ValueError("Each item in Azure resources file must be a JSON object")
        # Validate required fields
        if "id" not in item or not isinstance(item.get("id"), str):
            raise ValueError("Each Azure resource must have a valid 'id' string field")

        # Extract resource group name
        rg_name = item.get("resourceGroup", "")
        # Get tags for this resource group from RG tags file
        tags_str = rg_tags_map.get(rg_name, "")

        # If no RG tags available, fall back to resource's own tags
        if not tags_str and "tags" in item and item["tags"]:
            resource_tags = item["tags"]
            tags_str = "|".join(f"{k}:{v}" for k, v in resource_tags.items())

        # Convert az resource list format to AzureResource
        azure_resource = AzureResource(
            id=item.get("id", "").lower(),
            name=item.get("name", ""),
            type=item.get("type", ""),
            resource_group=rg_name,
            location=item.get("location", ""),
            provider=parse_provider_from_type(item.get("type", "")),
            rg_tags=tags_str,
            raw_data=item,
        )
        resources.append(azure_resource)

    log = logger.get_logger(__name__)
    log.info(f"Loaded {len(resources)} resources from JSON file: {file_path}")
    if rg_tags_file:
        rg_count = len([r for r in resources if r.rg_tags])
        log.info(
            f"Loaded resource group tags from {rg_tags_file} - {rg_count} resources have tags"
        )
    return resources


def _load_resource_group_tags_from_file(file_path: str) -> Dict[str, str]:
    """Load resource group tags from az group list JSON file.

    Args:
        file_path: Path to JSON file from 'az group list'

    Returns:
        Dict mapping resource group name to tags string (pipe-separated)

    Raises:
        FileNotFoundError: If file not found
        ValueError: If JSON is invalid
    """
    json_path = Path(file_path)
    if not json_path.exists():
        raise FileNotFoundError(f"Resource group tags file not found: {file_path}")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in resource group tags file: {e}")

    # Validate data is a list
    if not isinstance(data, list):
        raise ValueError("Resource group tags file must contain a JSON array")

    rg_tags = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        rg_name = item.get("name", "")
        if not rg_name:
            continue
        tags = item.get("tags") or {}
        # Convert tags dict to pipe-separated string
        tags_str = "|".join(f"{k}:{v}" for k, v in tags.items()) if tags else ""
        rg_tags[rg_name] = tags_str

    logger.get_logger(__name__).debug(
        f"Loaded tags for {len(rg_tags)} resource groups from {file_path}"
    )
    return rg_tags


def print_manual_azure_commands(subscription_id: str) -> None:
    """Print Azure CLI commands for manual resource collection.

    Args:
        subscription_id: Azure subscription ID
    """
    print("Azure CLI Manual Mode Activated")
    print()
    print("Please run the following commands to generate resource data:")
    print()
    print("1. Export resources:")
    print(
        f"   az resource list --subscription {subscription_id} --output json > azure_resources_{subscription_id}.json"
    )
    print()
    print("2. Export resource groups (recommended for resource group tags):")
    print(
        f"   az group list --subscription {subscription_id} --output json > azure_resource_groups_{subscription_id}.json"
    )
    print()
    print("3. After files are generated, run the toolkit again with:")
    print(
        f"   python -m zephy --azure-input-file azure_resources_{subscription_id}.json \\"
    )
    print(
        f"                   --azure-rg-tags-file azure_resource_groups_{subscription_id}.json [other options]"
    )
    print()
    print("Note:")
    print(
        "  - The --azure-rg-tags-file argument is optional but recommended to include resource group tags in the output"
    )
    print(
        "  - Files will be read from the current directory unless full paths are specified"
    )
