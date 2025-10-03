"""Tests for resource_matcher module."""

import pytest
from zephy.config import AzureResource, TFEResource, ComparisonReport
from zephy.resource_matcher import (
    match_resources,
    filter_matches_by_resource_groups,
    get_unmanaged_resources,
    get_multi_workspace_resources,
    get_matched_resources,
    get_orphaned_resources,
)


@pytest.fixture
def sample_azure_resources():
    """Sample Azure resources for testing."""
    return [
        AzureResource(
            id="/subscriptions/sub1/resourcegroups/rg1/providers/microsoft.compute/virtualmachines/vm1",
            name="vm1",
            type="Microsoft.Compute/virtualMachines",
            resource_group="rg1",
            location="eastus",
            provider="Microsoft.Compute",
            raw_data={},
        ),
        AzureResource(
            id="/subscriptions/sub1/resourcegroups/rg1/providers/microsoft.storage/storageaccounts/stor1",
            name="stor1",
            type="Microsoft.Storage/storageAccounts",
            resource_group="rg1",
            location="eastus",
            provider="Microsoft.Storage",
            raw_data={},
        ),
        AzureResource(
            id="/subscriptions/sub1/resourcegroups/rg2/providers/microsoft.compute/virtualmachines/vm2",
            name="vm2",
            type="Microsoft.Compute/virtualMachines",
            resource_group="rg2",
            location="westus",
            provider="Microsoft.Compute",
            raw_data={},
        ),
    ]


@pytest.fixture
def sample_tfe_resources():
    """Sample TFE resources for testing."""
    return [
        TFEResource(
            id="/subscriptions/sub1/resourcegroups/rg1/providers/microsoft.compute/virtualmachines/vm1",
            name="vm1",
            type="azurerm_linux_virtual_machine",
            provider="azurerm",
            workspace="workspace1",
            module_path="",
            raw_data={},
        ),
        TFEResource(
            id="/subscriptions/sub1/resourcegroups/rg1/providers/microsoft.storage/storageaccounts/stor1",
            name="stor1",
            type="azurerm_storage_account",
            provider="azurerm",
            workspace="workspace1",
            module_path="",
            raw_data={},
        ),
        TFEResource(
            id="/subscriptions/sub1/resourcegroups/rg1/providers/microsoft.storage/storageaccounts/stor1",
            name="stor1",
            type="azurerm_storage_account",
            provider="azurerm",
            workspace="workspace2",  # Multi-workspace
            module_path="",
            raw_data={},
        ),
        TFEResource(
            id="/subscriptions/sub1/resourcegroups/rg3/providers/microsoft.network/virtualnetworks/vnet1",
            name="vnet1",
            type="azurerm_virtual_network",
            provider="azurerm",
            workspace="workspace1",
            module_path="",
            raw_data={},
        ),  # Orphaned - no matching Azure resource
    ]


class TestMatchResources:
    """Test match_resources function."""

    def test_match_resources_basic(self, sample_azure_resources, sample_tfe_resources):
        """Test basic resource matching."""
        report = match_resources(sample_azure_resources, sample_tfe_resources)

        assert isinstance(report, ComparisonReport)
        assert report.total_azure_resources == 3
        assert report.total_tfe_resources == 4
        assert report.matched_count == 2  # vm1 and stor1
        assert report.unmanaged_count == 1  # vm2
        assert report.orphaned_count == 1  # vnet1
        assert report.multi_workspace_count == 1  # stor1

        assert len(report.matches) == 4  # 3 Azure + 1 orphaned

    def test_match_resources_no_matches(self):
        """Test matching with no overlapping resources."""
        azure_resources = [
            AzureResource(
                id="/subscriptions/sub1/resourcegroups/rg1/providers/microsoft.compute/virtualmachines/vm1",
                name="vm1",
                type="Microsoft.Compute/virtualMachines",
                resource_group="rg1",
                location="eastus",
                provider="Microsoft.Compute",
                raw_data={},
            )
        ]
        tfe_resources = [
            TFEResource(
                id="/subscriptions/sub1/resourcegroups/rg2/providers/microsoft.compute/virtualmachines/vm2",
                name="vm2",
                type="azurerm_linux_virtual_machine",
                provider="azurerm",
                workspace="workspace1",
                module_path="",
                raw_data={},
            )
        ]

        report = match_resources(azure_resources, tfe_resources)

        assert report.matched_count == 0
        assert report.unmanaged_count == 1
        assert report.orphaned_count == 1

    def test_match_resources_empty_inputs(self):
        """Test matching with empty inputs."""
        report = match_resources([], [])

        assert report.total_azure_resources == 0
        assert report.total_tfe_resources == 0
        assert report.matched_count == 0
        assert report.unmanaged_count == 0
        assert report.orphaned_count == 0
        assert report.multi_workspace_count == 0
        assert len(report.matches) == 0


class TestFilterMatchesByResourceGroups:
    """Test filter_matches_by_resource_groups function."""

    def test_filter_by_resource_groups(self, sample_azure_resources, sample_tfe_resources):
        """Test filtering matches by resource groups."""
        matches = match_resources(sample_azure_resources, sample_tfe_resources).matches

        filtered = filter_matches_by_resource_groups(matches, ["rg1"])

        # Should include matched and unmanaged in rg1, exclude rg2 and orphaned
        assert len(filtered) == 2  # vm1 (matched) and stor1 (matched)

    def test_filter_no_resource_groups(self, sample_azure_resources, sample_tfe_resources):
        """Test filtering with no RG filter returns all."""
        matches = match_resources(sample_azure_resources, sample_tfe_resources).matches

        filtered = filter_matches_by_resource_groups(matches, None)

        assert len(filtered) == len(matches)

    def test_filter_empty_resource_groups(self, sample_azure_resources, sample_tfe_resources):
        """Test filtering with empty RG list."""
        matches = match_resources(sample_azure_resources, sample_tfe_resources).matches

        filtered = filter_matches_by_resource_groups(matches, [])

        assert len(filtered) == len(matches)


class TestResourceFilters:
    """Test resource filter functions."""

    def test_get_unmanaged_resources(self, sample_azure_resources, sample_tfe_resources):
        """Test getting unmanaged resources."""
        matches = match_resources(sample_azure_resources, sample_tfe_resources).matches

        unmanaged = get_unmanaged_resources(matches)

        assert len(unmanaged) == 1
        assert unmanaged[0].match_status == "unmanaged"
        assert unmanaged[0].azure_resource.name == "vm2"

    def test_get_multi_workspace_resources(self, sample_azure_resources, sample_tfe_resources):
        """Test getting multi-workspace resources."""
        matches = match_resources(sample_azure_resources, sample_tfe_resources).matches

        multi = get_multi_workspace_resources(matches)

        assert len(multi) == 1
        assert len(multi[0].workspace_names) > 1
        assert "stor1" in multi[0].azure_resource.name

    def test_get_matched_resources(self, sample_azure_resources, sample_tfe_resources):
        """Test getting matched resources."""
        matches = match_resources(sample_azure_resources, sample_tfe_resources).matches

        matched = get_matched_resources(matches)

        assert len(matched) == 2  # vm1 and stor1
        for m in matched:
            assert m.match_status == "matched"

    def test_get_orphaned_resources(self, sample_azure_resources, sample_tfe_resources):
        """Test getting orphaned resources."""
        matches = match_resources(sample_azure_resources, sample_tfe_resources).matches

        orphaned = get_orphaned_resources(matches)

        assert len(orphaned) == 1
        assert orphaned[0].match_status == "orphaned"
        assert "vnet1" in orphaned[0].tfe_resources[0].name