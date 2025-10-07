"""CSV report generation and summary statistics."""

import csv
from datetime import datetime
from pathlib import Path
from typing import List

from .config import AzureResource, ComparisonReport, MatchResult, TFEResource

from . import logger


def generate_timestamp() -> str:
    """Generate timestamp string for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_csv_report(filename: str, data: List[dict], fieldnames: List[str]) -> None:
    """Write data to CSV file with UTF-8 BOM encoding.

    Args:
        filename: Output filename
        data: List of dictionaries to write
        fieldnames: CSV column names
    """
    try:
        with open(filename, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        logger.get_logger(__name__).info(f"Generated CSV report: {filename}")
    except Exception as e:
        logger.get_logger(__name__).error(f"Failed to write CSV report {filename}: {e}")
        raise


def generate_resources_comparison_csv(
    matches: List[MatchResult], output_dir: str
) -> str:
    """Generate resources comparison CSV report.

    Args:
        matches: List of match results
        output_dir: Output directory

    Returns:
        Path to generated CSV file
    """
    timestamp = generate_timestamp()
    filename = f"{output_dir}/resources_comparison_{timestamp}.csv"

    data = []
    for match in matches:
        # Use first workspace for matched resources, empty for others
        workspace = match.workspace_names[0] if match.workspace_names else ""

        row = {
            "resource_id": (
                match.azure_resource.id
                if match.azure_resource
                else (match.tfe_resources[0].id if match.tfe_resources else "")
            ),
            "resource_name": (
                match.azure_resource.name
                if match.azure_resource
                else (match.tfe_resources[0].name if match.tfe_resources else "")
            ),
            "resource_type": (
                match.azure_resource.type
                if match.azure_resource
                else (match.tfe_resources[0].type if match.tfe_resources else "")
            ),
            "azure_rg": match.resource_group,
            "tfe_workspace": workspace,
            "match_status": match.match_status,
            "provider": (
                match.azure_resource.provider
                if match.azure_resource
                else (match.tfe_resources[0].provider if match.tfe_resources else "")
            ),
        }
        data.append(row)

    fieldnames = [
        "resource_id",
        "resource_name",
        "resource_type",
        "azure_rg",
        "tfe_workspace",
        "match_status",
        "provider",
    ]
    write_csv_report(filename, data, fieldnames)
    return filename


def generate_unmanaged_resources_csv(
    matches: List[MatchResult], output_dir: str
) -> str:
    """Generate unmanaged resources CSV report.

    Args:
        matches: List of match results
        output_dir: Output directory

    Returns:
        Path to generated CSV file
    """
    timestamp = generate_timestamp()
    filename = f"{output_dir}/unmanaged_resources_{timestamp}.csv"

    data = []
    for match in matches:
        if match.match_status == "unmanaged" and match.azure_resource:
            row = {
                "resource_id": match.azure_resource.id,
                "resource_name": match.azure_resource.name,
                "resource_type": match.azure_resource.type,
                "azure_rg": match.azure_resource.resource_group,
                "provider": match.azure_resource.provider,
            }
            data.append(row)

    fieldnames = [
        "resource_id",
        "resource_name",
        "resource_type",
        "azure_rg",
        "provider",
    ]
    write_csv_report(filename, data, fieldnames)
    return filename


def generate_multi_workspace_resources_csv(
    matches: List[MatchResult], output_dir: str
) -> str:
    """Generate multi-workspace resources CSV report.

    Args:
        matches: List of match results
        output_dir: Output directory

    Returns:
        Path to generated CSV file
    """
    timestamp = generate_timestamp()
    filename = f"{output_dir}/multi_workspace_resources_{timestamp}.csv"

    data = []
    for match in matches:
        if len(match.workspace_names) > 1 and match.azure_resource:
            row = {
                "resource_id": match.azure_resource.id,
                "resource_name": match.azure_resource.name,
                "resource_type": match.azure_resource.type,
                "azure_rg": match.azure_resource.resource_group,
                "workspaces": ", ".join(sorted(match.workspace_names)),
                "count": len(match.workspace_names),
            }
            data.append(row)

    fieldnames = [
        "resource_id",
        "resource_name",
        "resource_type",
        "azure_rg",
        "workspaces",
        "count",
    ]
    write_csv_report(filename, data, fieldnames)
    return filename


def generate_tfe_resources_inventory_csv(
    tfe_resources: List[TFEResource], output_dir: str
) -> str:
    """Generate TFE resources inventory CSV report.

    Args:
        tfe_resources: List of all TFE resources
        output_dir: Output directory

    Returns:
        Path to generated CSV file
    """
    timestamp = generate_timestamp()
    filename = f"{output_dir}/tfe_resources_inventory_{timestamp}.csv"

    data = []
    for resource in tfe_resources:
        row = {
            "resource_id": resource.id,
            "resource_name": resource.name,
            "resource_type": resource.type,
            "provider": resource.provider,
            "workspace": resource.workspace,
            "module_path": resource.module_path,
            "ws_tags": resource.ws_tags,
        }
        data.append(row)

    fieldnames = [
        "resource_id",
        "resource_name",
        "resource_type",
        "provider",
        "workspace",
        "module_path",
        "ws_tags",
    ]
    write_csv_report(filename, data, fieldnames)
    return filename


def generate_azure_resources_inventory_csv(
    azure_resources: List[AzureResource], output_dir: str
) -> str:
    """Generate Azure resources inventory CSV report.

    Args:
        azure_resources: List of all Azure resources
        output_dir: Output directory

    Returns:
        Path to generated CSV file
    """
    timestamp = generate_timestamp()
    filename = f"{output_dir}/azure_resources_inventory_{timestamp}.csv"

    data = []
    for resource in azure_resources:
        row = {
            "resource_id": resource.id,
            "resource_name": resource.name,
            "resource_type": resource.type,
            "resource_group": resource.resource_group,
            "location": resource.location,
            "provider": resource.provider,
            "rg_tags": resource.rg_tags,
        }
        data.append(row)

    fieldnames = [
        "resource_id",
        "resource_name",
        "resource_type",
        "resource_group",
        "location",
        "provider",
        "rg_tags",
    ]
    write_csv_report(filename, data, fieldnames)
    return filename


def generate_all_reports(
    report: ComparisonReport,
    azure_resources: List[AzureResource],
    tfe_resources: List[TFEResource],
    output_dir: str,
) -> List[str]:
    """Generate all CSV reports.

    Args:
        report: Comparison report
        azure_resources: List of all Azure resources
        tfe_resources: List of all TFE resources
        output_dir: Output directory

    Returns:
        List of generated CSV filenames
    """
    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    files = []

    # Resources comparison report
    files.append(generate_resources_comparison_csv(report.matches, output_dir))

    # Unmanaged resources report
    files.append(generate_unmanaged_resources_csv(report.matches, output_dir))

    # Multi-workspace resources report
    files.append(generate_multi_workspace_resources_csv(report.matches, output_dir))

    # TFE resources inventory report
    files.append(generate_tfe_resources_inventory_csv(tfe_resources, output_dir))

    # Azure resources inventory report
    files.append(generate_azure_resources_inventory_csv(azure_resources, output_dir))

    return files


def print_summary_report(
    report: ComparisonReport,
    tfe_org: str,
    azure_subscription: str,
    generated_files: List[str],
    resource_group_count: int = 0,
    workspace_count: int = 0,
) -> None:
    """Print summary statistics to stdout.

    Args:
        report: Comparison report
        tfe_org: TFE organization name
        azure_subscription: Azure subscription ID
        generated_files: List of generated CSV files
    """
    print("=== Zephy - Azure-TFE Resources Comparator Summary ===")
    print(f"Azure Subscription: {azure_subscription}")
    print(f"TFE Organization: {tfe_org}")
    print()
    print("Azure Resources:")
    print(f"  Total Resource Groups: {resource_group_count}")
    print(f"  Total Resources: {report.total_azure_resources}")
    print("  Primary Resources: N/A")  # We don't distinguish in report
    print()
    print("TFE Workspaces:")
    print(f"  Total Workspaces: {workspace_count}")
    print(f"  Total Resources in State: {report.total_tfe_resources}")
    print()
    print("Comparison Results:")
    total_compared = report.matched_count + report.unmanaged_count
    if total_compared > 0:
        percentage = (report.matched_count / total_compared) * 100
        print(f"  Matched Resources: {report.matched_count} ({percentage:.1f}%)")
    else:
        print(f"  Matched Resources: {report.matched_count}")
    print(f"  Unmanaged Azure Resources: {report.unmanaged_count}")
    if report.total_tfe_resources > 0:
        orphaned_percentage = (report.orphaned_count / report.total_tfe_resources) * 100
        print(
            f"  Orphaned TFE Resources: {report.orphaned_count} ({orphaned_percentage:.1f}%)"
        )
    else:
        print(f"  Orphaned TFE Resources: {report.orphaned_count}")
    print(f"  Multi-Workspace Resources: {report.multi_workspace_count}")
    print()
    print("Reports Generated:")
    for file_path in generated_files:
        filename = Path(file_path).name
        print(f"  - {filename}")
