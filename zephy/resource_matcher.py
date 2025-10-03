"""Resource matching and comparison logic."""

from collections import defaultdict
from typing import Dict, List, Optional

from .config import AzureResource, ComparisonReport, MatchResult, TFEResource
from .utils import normalize_resource_id

from . import logger


def match_resources(
    azure_resources: List[AzureResource], tfe_resources: List[TFEResource]
) -> ComparisonReport:
    """Match Azure resources with TFE resources using resource IDs.

    Args:
        azure_resources: List of Azure resources
        tfe_resources: List of TFE resources

    Returns:
        ComparisonReport with match results and statistics
    """
    log = logger.get_logger(__name__)

    # Index Azure resources by normalized ID
    azure_index: Dict[str, AzureResource] = {}
    for resource in azure_resources:
        normalized_id = normalize_resource_id(resource.id)
        azure_index[normalized_id] = resource

    # Index TFE resources by normalized ID (multiple workspaces may manage
    # same resource)
    tfe_index: Dict[str, List[TFEResource]] = defaultdict(list)
    for tfe_resource in tfe_resources:
        normalized_id = normalize_resource_id(tfe_resource.id)
        tfe_index[normalized_id].append(tfe_resource)

    # All unique resource IDs from both sources
    all_ids = set(azure_index.keys()) | set(tfe_index.keys())

    matches: List[MatchResult] = []
    matched_count = 0
    unmanaged_count = 0
    orphaned_count = 0
    multi_workspace_count = 0

    for resource_id in all_ids:
        azure_res = azure_index.get(resource_id)
        tfe_res_list = tfe_index.get(resource_id, [])

        # Determine match status
        if azure_res and tfe_res_list:
            status = "matched"
            matched_count += 1
            if len(tfe_res_list) > 1:
                multi_workspace_count += 1
        elif azure_res and not tfe_res_list:
            status = "unmanaged"
            unmanaged_count += 1
        else:  # tfe_res_list but not azure_res
            status = "orphaned"
            orphaned_count += 1

        # Extract workspace names
        workspace_names = [r.workspace for r in tfe_res_list]

        # Determine resource group (from Azure resource if available)
        resource_group = azure_res.resource_group if azure_res else "N/A"

        match_result = MatchResult(
            azure_resource=azure_res,
            tfe_resources=tfe_res_list,
            match_status=status,
            resource_group=resource_group,
            workspace_names=workspace_names,
        )
        matches.append(match_result)

    # Create comparison report
    report = ComparisonReport(
        matches=matches,
        total_azure_resources=len(azure_resources),
        total_tfe_resources=len(tfe_resources),
        matched_count=matched_count,
        unmanaged_count=unmanaged_count,
        orphaned_count=orphaned_count,
        multi_workspace_count=multi_workspace_count,
    )

    log.info(
        f"Comparison complete: {matched_count} matched, {unmanaged_count} unmanaged, "
        f"{orphaned_count} orphaned, {multi_workspace_count} multi-workspace"
    )

    return report


def filter_matches_by_resource_groups(
    matches: List[MatchResult], resource_groups: Optional[List[str]] = None
) -> List[MatchResult]:
    """Filter match results by resource groups.

    Args:
        matches: List of match results
        resource_groups: List of resource group names to include (None for all)

    Returns:
        Filtered list of match results
    """
    if not resource_groups:
        return matches

    filtered = []
    for match in matches:
        # Include if it's an Azure resource in one of the specified RGs
        if (
            match.azure_resource
            and match.azure_resource.resource_group in resource_groups
        ):
            filtered.append(match)
        # Orphaned resources are excluded when RG filtering is specified

    return filtered


def get_unmanaged_resources(matches: List[MatchResult]) -> List[MatchResult]:
    """Extract unmanaged Azure resources from match results.

    Args:
        matches: List of match results

    Returns:
        List of unmanaged resource matches
    """
    return [m for m in matches if m.match_status == "unmanaged"]


def get_multi_workspace_resources(
        matches: List[MatchResult]) -> List[MatchResult]:
    """Extract resources managed by multiple workspaces.

    Args:
        matches: List of match results

    Returns:
        List of multi-workspace resource matches
    """
    return [m for m in matches if len(m.workspace_names) > 1]


def get_matched_resources(matches: List[MatchResult]) -> List[MatchResult]:
    """Extract matched resources from match results.

    Args:
        matches: List of match results

    Returns:
        List of matched resource matches
    """
    return [m for m in matches if m.match_status == "matched"]


def get_orphaned_resources(matches: List[MatchResult]) -> List[MatchResult]:
    """Extract orphaned TFE resources from match results.

    Args:
        matches: List of match results

    Returns:
        List of orphaned resource matches
    """
    return [m for m in matches if m.match_status == "orphaned"]
