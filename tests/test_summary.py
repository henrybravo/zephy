#!/usr/bin/env python3
"""Test script to verify summary report shows counts correctly."""

from zephy.config import ComparisonReport, MatchResult, AzureResource, TFEResource
from zephy.report_generator import print_summary_report

# Create mock data
azure_resources = [
    AzureResource(
        id="/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
        name="vm1",
        type="Microsoft.Compute/virtualMachines",
        resource_group="rg1",
        location="eastus",
        provider="Microsoft.Compute",
        rg_tags="",
        raw_data={},
    ),
    AzureResource(
        id="/subscriptions/test/resourceGroups/rg2/providers/Microsoft.Storage/storageAccounts/stor1",
        name="stor1",
        type="Microsoft.Storage/storageAccounts",
        resource_group="rg2",
        location="westus",
        provider="Microsoft.Storage",
        rg_tags="",
        raw_data={},
    ),
]

tfe_resources = [
    TFEResource(
        id="/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
        name="vm1",
        type="azurerm_linux_virtual_machine",
        provider="azurerm",
        workspace="workspace1",
        module_path="",
        ws_tags="",
        raw_data={},
    ),
    TFEResource(
        id="/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
        name="vm1",
        type="azurerm_linux_virtual_machine",
        provider="azurerm",
        workspace="workspace2",  # Multi-workspace
        module_path="",
        ws_tags="",
        raw_data={},
    ),
]

# Create match result
match = MatchResult(
    azure_resource=azure_resources[0],
    tfe_resources=[tfe_resources[0], tfe_resources[1]],
    match_status="matched",
    resource_group="rg1",
    workspace_names=["workspace1", "workspace2"],
)

report = ComparisonReport(
    matches=[match],
    total_azure_resources=2,
    total_tfe_resources=2,
    matched_count=1,
    unmanaged_count=1,
    orphaned_count=0,
    multi_workspace_count=1,
)

# Test the summary report
print("Testing summary report with counts:")
print_summary_report(
    report,
    "test-org",
    "test-subscription",
    ["/tmp/test1.csv", "/tmp/test2.csv"],
    resource_group_count=2,
    workspace_count=2,
)
