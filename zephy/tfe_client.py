"""Terraform Enterprise API client."""

import gzip
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Dict, List, Optional

import requests

from .config import TFEResource
from .constants import DEFAULT_TFE_BASE_URL, TFE_RATE_LIMIT_REQUESTS_PER_SECOND
from .utils import normalize_resource_id, parse_provider_from_tfe_provider

from . import logger


class RateLimiter:
    """Rate limiter for TFE API calls."""

    def __init__(self, max_rate: int = TFE_RATE_LIMIT_REQUESTS_PER_SECOND):
        self.max_rate = max_rate
        self.min_interval = 1.0 / max_rate
        self.last_request = 0.0
        self.lock = Lock()

    def wait(self) -> None:
        """Wait to respect rate limit."""
        with self.lock:
            elapsed = time.time() - self.last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request = time.time()


class TFEClient:
    """Client for Terraform Enterprise API."""

    def __init__(self, token: str, base_url: str = DEFAULT_TFE_BASE_URL, ssl_verify: bool = True):
        """Initialize TFE client.

        Args:
            token: TFE API token
            base_url: TFE API base URL
            ssl_verify: Whether to verify SSL certificates
        """
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.ssl_verify = ssl_verify
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/vnd.api+json",
            }
        )
        self.rate_limiter = RateLimiter()
        self.log = logger.get_logger(__name__)

        # Test connectivity
        self.log.info(f"TFE Client initialized for {self.base_url}")

    # type: ignore[return]
    def _get(
            self,
            endpoint: str,
            params: Optional[Dict] = None,
            timeout: int = 30) -> Dict:
        """Make authenticated GET request with rate limiting and retry logic."""
        url = f"{self.base_url}{endpoint}"

        for attempt in range(4):  # 3 retries + 1 initial attempt
            try:
                self.rate_limiter.wait()
                self.log.debug(
                    f"Making TFE API request: {url} (attempt {
                        attempt + 1})")

                response = self.session.get(
                    url, params=params, timeout=timeout, verify=self.ssl_verify)
                self.log.debug(f"Request sent, waiting for response...")

                if response.status_code in [200, 201]:
                    return response.json()
                elif response.status_code in [429, 502, 503, 504] and attempt < 3:
                    # Retryable errors
                    wait_time = 2**attempt
                    self.log.warning(
                        f"TFE API request failed with {
                            response.status_code}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    # Non-retryable error
                    error_msg = f"TFE API request failed: {
                        response.status_code} {
                        response.reason}"
                    try:
                        error_data = response.json()
                        if "errors" in error_data:
                            error_msg += (
                                f" - {error_data['errors'][0].get('detail', '')}"
                            )
                    except BaseException:
                        pass
                    raise requests.HTTPError(error_msg, response=response)

            except requests.Timeout as e:
                if attempt == 3:
                    raise requests.Timeout(
                        f"TFE API request timed out after {timeout}s: {e}"
                    )
                wait_time = 2**attempt
                self.log.warning(
                    f"TFE API request timed out, retrying in {wait_time}s..."
                )
                time.sleep(wait_time)

            except requests.RequestException as e:
                if attempt == 3:
                    raise requests.RequestException(
                        f"TFE API network error: {e}")
                wait_time = 2**attempt
                self.log.warning(
                    f"TFE API network error, retrying in {wait_time}s...")
                time.sleep(wait_time)

            except Exception as e:
                raise requests.RequestException(
                    f"Unexpected error in TFE API request: {e}"
                ) from e

    def get_workspaces(
        self, organization: str, workspace_filter: Optional[List[str]] = None
    ) -> List[Dict]:
        """Get all workspaces for an organization, optionally filtered.

        Args:
            organization: TFE organization name
            workspace_filter: List of workspace names to include (None for all)

        Returns:
            List of workspace dictionaries
        """
        self.log.info(
            f"Starting to fetch workspaces for organization: {organization}")
        workspaces = []
        page = 1

        while True:
            params = {"page[size]": 100, "page[number]": page}
            self.log.debug(f"Fetching page {page} of workspaces")
            response = self._get(
                f"/organizations/{organization}/workspaces", params=params
            )

            # Validate API response structure
            if not isinstance(response, dict) or "data" not in response:
                raise ValueError(f"Invalid API response structure for workspaces")
            if not isinstance(response["data"], list):
                raise ValueError(f"API response data is not a list for workspaces")

            page_workspaces = response["data"]
            if workspace_filter:
                # Filter workspaces by name
                page_workspaces = [
                    ws
                    for ws in page_workspaces
                    if ws["attributes"]["name"] in workspace_filter
                ]

            workspaces.extend(page_workspaces)

            # Check if there are more pages
            links = response.get("links", {})
            if "next" not in links or not page_workspaces:
                # Stop if no next link OR no data in this page
                break

            page += 1

        self.log.info(
            f"Retrieved {
                len(workspaces)} workspaces from TFE organization '{organization}'")
        return workspaces

    def get_current_state_version(self, workspace_id: str) -> Optional[Dict]:
        """Get current state version for a workspace.

        Args:
            workspace_id: TFE workspace ID

        Returns:
            State version dictionary or None if no state exists
        """
        try:
            response = self._get(
                f"/workspaces/{workspace_id}/current-state-version")
            # Validate response structure
            if not isinstance(response, dict):
                raise ValueError(f"Invalid API response structure for state version")
            data = response.get("data")
            if data is not None and not isinstance(data, dict):
                raise ValueError(f"API response data is not a dict for state version")
            return data
        except requests.HTTPError as e:
            if e.response and e.response.status_code == 404:
                # Workspace has no current state version, try to get the latest
                # state version
                self.log.debug(
                    f"No current state version for workspace {workspace_id}, trying to get latest")
                return self._get_latest_state_version(workspace_id)
            raise

    def _get_latest_state_version(self, workspace_id: str) -> Optional[Dict]:
        """Get the latest state version for a workspace.

        Args:
            workspace_id: TFE workspace ID

        Returns:
            Latest state version dictionary or None
        """
        try:
            # Get state versions sorted by creation date (newest first)
            response = self._get(
                f"/workspaces/{workspace_id}/state-versions?page[size]=1"
            )
            state_versions = response.get("data", [])

            if state_versions:
                self.log.debug(
                    f"Found latest state version for workspace {workspace_id}"
                )
                return state_versions[0]
            else:
                self.log.debug(
                    f"No state versions found for workspace {workspace_id}")
                return None

        except Exception as e:
            self.log.debug(
                f"Failed to get latest state version for workspace {workspace_id}: {e}")
            return None

    def download_state_file(self, state_version: Dict) -> Dict:
        """Download state file from hosted URL.

        Args:
            state_version: State version dictionary from get_current_state_version

        Returns:
            Parsed JSON state file
        """
        # Validate input
        if not isinstance(state_version, dict) or "attributes" not in state_version:
            raise ValueError("Invalid state_version structure")
        attributes = state_version["attributes"]
        if not isinstance(attributes, dict) or "hosted-json-state-download-url" not in attributes:
            raise ValueError("Invalid state_version attributes")

        hosted_url = attributes["hosted-json-state-download-url"]
        self.log.debug(f"Downloading state file from: {hosted_url}")

        # Note: This URL is pre-signed and doesn't need authentication
        response = requests.get(hosted_url, timeout=30, verify=self.ssl_verify)
        response.raise_for_status()
        state_data = response.json()
        # Validate response is dict
        if not isinstance(state_data, dict):
            raise ValueError("Downloaded state file is not valid JSON dict")
        return state_data

    def get_workspace_state_resources(
            self, workspace: Dict) -> List[TFEResource]:
        """Get all resources from a workspace's current state.

        Args:
            workspace: Workspace dictionary

        Returns:
            List of TFEResource objects
        """
        workspace_id = workspace["id"]
        workspace_name = workspace["attributes"]["name"]

        try:
            # Get current state version
            state_version = self.get_current_state_version(workspace_id)

            # Check if state version exists
            if not state_version:
                self.log.warning(
                    f"Workspace '{workspace_name}' has no state version at all"
                )
                return []

            attributes = state_version.get("attributes", {})
            self.log.debug(
                f"State version attributes keys: {
                    list(
                        attributes.keys())}")
            json_url = attributes.get("hosted-json-state-download-url")
            binary_url = attributes.get("hosted-state-download-url")
            self.log.debug(f"JSON URL: {json_url}")
            self.log.debug(f"Binary URL: {binary_url}")

            # Try to download JSON state file first (preferred method)
            if json_url:
                try:
                    self.log.info(
                        f"Downloading JSON state file for workspace '{workspace_name}'")
                    state_data = self.download_state_file(state_version)
                    resources = []
                    for resource in state_data.get("resources", []):
                        if resource.get(
                                "mode") == "managed":  # Skip data sources
                            for instance in resource.get("instances", []):
                                azure_id = instance.get(
                                    "attributes", {}).get("id", "")
                                if azure_id and azure_id.startswith(
                                        "/subscriptions/"):
                                    # Valid Azure resource
                                    tfe_resource = TFEResource(
                                        id=normalize_resource_id(azure_id),
                                        name=resource.get("name", ""),
                                        type=resource.get("type", ""),
                                        provider=parse_provider_from_tfe_provider(
                                            resource.get("provider", "")
                                        ),
                                        workspace=workspace_name,
                                        module_path=resource.get("module", ""),
                                        raw_data=instance.get("attributes", {}),
                                    )
                                    resources.append(tfe_resource)

                    self.log.info(
                        f"Extracted {
                            len(resources)} Azure resources from downloaded state file for workspace '{workspace_name}'")
                    return resources
                except Exception as e:
                    self.log.warning(
                        f"Failed to download/parse JSON state file for workspace '{workspace_name}': {e}")

            # Try to download binary state file and parse as JSON (higher
            # priority than inference)
            if binary_url:
                try:
                    self.log.info(
                        f"Trying to download binary state file for workspace '{workspace_name}'")
                    # Download state data from hosted state URL (requires auth
                    # header)
                    response = requests.get(
                        binary_url,
                        headers={"Authorization": f"Bearer {self.token}"},
                        timeout=30,
                        allow_redirects=True,
                        verify=self.ssl_verify,
                    )
                    response.raise_for_status()

                    # Get the response content as bytes first
                    state_bytes = response.content
                    self.log.debug(
                        f"Downloaded state file content length: {
                            len(state_bytes)} bytes")

                    # Try to decompress if it's gzipped
                    try:
                        decompressed = gzip.decompress(state_bytes)
                        state_content = decompressed.decode("utf-8")
                        self.log.debug(
                            f"Decompressed gzipped state file, new length: {
                                len(state_content)}")
                    except gzip.BadGzipFile:
                        # Not gzipped, treat as plain text
                        state_content = state_bytes.decode("utf-8")
                        self.log.debug("State file is not gzipped")

                    # Try to parse as JSON
                    try:
                        state_data = json.loads(state_content)
                        self.log.info(
                            f"Binary state file parsed as JSON for workspace '{workspace_name}', extracting resources")
                        resources = []
                        for resource in state_data.get("resources", []):
                            if resource.get(
                                    "mode") == "managed":  # Skip data sources
                                for instance in resource.get("instances", []):
                                    azure_id = instance.get(
                                        "attributes", {}).get("id", "")
                                    if azure_id and azure_id.startswith(
                                        "/subscriptions/"
                                    ):
                                        # Valid Azure resource
                                        tfe_resource = TFEResource(
                                            id=normalize_resource_id(azure_id),
                                            name=resource.get("name", ""),
                                            type=resource.get("type", ""),
                                            provider=parse_provider_from_tfe_provider(
                                                resource.get("provider", "")
                                            ),
                                            workspace=workspace_name,
                                            module_path=resource.get("module", ""),
                                            raw_data=instance.get("attributes", {}),
                                        )
                                        resources.append(tfe_resource)

                        if resources:
                            self.log.info(
                                f"Extracted {
                                    len(resources)} Azure resources with real IDs from binary state file for workspace '{workspace_name}'")
                            return resources
                        else:
                            self.log.debug(
                                f"No Azure resources found in binary state file for workspace '{workspace_name}'")

                    except (ValueError, json.JSONDecodeError) as e:
                        self.log.warning(
                            f"Binary state file content is not valid JSON for workspace '{workspace_name}': {e}")

                except Exception as e:
                    self.log.warning(
                        f"Failed to download/parse binary state file for workspace '{workspace_name}': {e}")

            # Fallback: Try to get resource information from outputs (some
            # Azure resource IDs might be exposed there)
            try:
                outputs = self._get_state_version_outputs(state_version)
                resources_from_outputs = self._extract_resources_from_outputs(
                    outputs, workspace_name
                )
                if resources_from_outputs:
                    self.log.info(
                        f"Extracted {
                            len(resources_from_outputs)} Azure resources from outputs for workspace '{workspace_name}'")
                    return resources_from_outputs
            except Exception as e:
                self.log.debug(
                    f"Failed to extract resources from outputs for workspace '{workspace_name}': {e}")

            # Last resort: Try to infer Azure resource IDs from resource names and types
            # This is a heuristic approach for when state files are not
            # available
            resources_list = attributes.get("resources", [])
            if resources_list:
                inferred_resources = self._infer_azure_resources_from_summary(
                    resources_list, workspace_name
                )
                if inferred_resources:
                    self.log.info(
                        f"Inferred {
                            len(inferred_resources)} potential Azure resources from state summary for workspace '{workspace_name}'")
                    return inferred_resources

            self.log.warning(
                f"Workspace '{workspace_name}' has no extractable Azure resource information")
            return []

        except Exception as e:
            self.log.error(
                f"Failed to get state for workspace '{workspace_name}': {e}")
            return []

    def _get_state_version_outputs(self, state_version: Dict) -> List[Dict]:
        """Get outputs from a state version.

        Args:
            state_version: State version dictionary

        Returns:
            List of output dictionaries
        """
        outputs_url = (
            state_version.get("relationships", {})
            .get("outputs", {})
            .get("links", {})
            .get("related")
        )
        if not outputs_url:
            return []

        try:
            # Convert relative URL to full URL
            if outputs_url.startswith("/"):
                outputs_url = f"{self.base_url}{outputs_url}"

            response = self._get(outputs_url.replace(self.base_url, ""))
            return response.get("data", [])
        except Exception:
            return []

    def _extract_resources_from_outputs(
        self, outputs: List[Dict], workspace_name: str
    ) -> List[TFEResource]:
        """Try to extract Azure resource IDs from state version outputs.

        Args:
            outputs: List of output dictionaries
            workspace_name: Name of the workspace

        Returns:
            List of TFEResource objects
        """
        resources = []
        for output in outputs:
            output_value = output.get("attributes", {}).get("value", "")

            # Check if output value looks like an Azure resource ID
            if isinstance(output_value, str) and output_value.startswith(
                "/subscriptions/"
            ):
                # This might be an Azure resource ID in an output
                tfe_resource = TFEResource(
                    id=normalize_resource_id(output_value),
                    name=output.get("id", ""),  # Output name as resource name
                    type="output",  # Special type for outputs
                    provider="azurerm",
                    workspace=workspace_name,
                    module_path="",
                    raw_data={"output_value": output_value},
                )
                resources.append(tfe_resource)

        return resources

    def _infer_azure_resources_from_summary(
        self, resources_list: List[Dict], workspace_name: str
    ) -> List[TFEResource]:
        """Infer potential Azure resources from state summary when full state is not available.

        This is a fallback heuristic that creates placeholder entries for Azure resources
        that might exist based on resource types and names.

        Args:
            resources_list: List of resource summaries from state version
            workspace_name: Name of the workspace

        Returns:
            List of inferred TFEResource objects
        """
        inferred_resources = []

        for resource in resources_list:
            resource_type = resource.get("type", "")
            resource_name = resource.get("name", "")

            # Only process azurerm provider resources
            if "azurerm" in resource.get("provider", ""):
                # For some common resource types, we can infer they likely have Azure resource IDs
                # This is not perfect but better than showing no resources at
                # all
                if resource_type in [
                    "azurerm_resource_group",
                    "azurerm_storage_account",
                    "azurerm_virtual_machine",
                    "azurerm_container_app",
                    "azurerm_log_analytics_workspace",
                    "azurerm_container_app_environment",
                    "azurerm_user_assigned_identity",
                ]:
                    # Create an inferred resource entry
                    # Note: This won't have the actual Azure resource ID, but
                    # indicates the resource exists
                    inferred_resource = TFEResource(
                        # Placeholder ID
                        id=f"inferred-{workspace_name}-{resource_type}-{resource_name}",
                        name=resource_name,
                        type=resource_type,
                        provider="azurerm",
                        workspace=workspace_name,
                        module_path=resource.get("module", ""),
                        raw_data={
                            "inferred": True,
                            "reason": "State file not available for parsing",
                            "summary_info": resource,
                        },
                    )
                    inferred_resources.append(inferred_resource)

        return inferred_resources

    def get_all_resources(
        self,
        organization: str,
        workspace_filter: Optional[List[str]] = None,
        max_workers: int = 10,
    ) -> List[TFEResource]:
        """Get all resources from all workspaces in an organization.

        Args:
            organization: TFE organization name
            workspace_filter: List of workspace names to include
            max_workers: Maximum concurrent downloads

        Returns:
            List of all TFEResource objects
        """
        # Get workspaces
        workspaces = self.get_workspaces(organization, workspace_filter)
        if not workspaces:
            self.log.warning(
                f"No workspaces found in organization '{organization}'")
            return []

        # Download state files concurrently
        all_resources = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_workspace = {
                executor.submit(self.get_workspace_state_resources, ws): ws
                for ws in workspaces
            }

            # Collect results
            for future in as_completed(future_to_workspace):
                workspace = future_to_workspace[future]
                try:
                    resources = future.result()
                    all_resources.extend(resources)
                except Exception as e:
                    workspace_name = workspace["attributes"]["name"]
                    self.log.error(
                        f"Failed to process workspace '{workspace_name}': {e}"
                    )

        self.log.info(
            f"Retrieved {
                len(all_resources)} total resources from {
                len(workspaces)} workspaces")
        return all_resources
