"""Integration tests for the Azure TFE Resources Toolkit."""

import pytest
from unittest.mock import Mock, patch

from zephy.config import Config
from zephy.resource_matcher import match_resources
from zephy.report_generator import generate_all_reports
from zephy import __main__ as main


class TestIntegrationWorkflow:
    """Test the complete workflow integration."""

    @patch('zephy.__main__.get_tfe_token')
    @patch('zephy.__main__.get_azure_credential')
    @patch('zephy.__main__.load_azure_resources')
    @patch('zephy.__main__.load_tfe_resources')
    @patch('zephy.__main__.generate_all_reports')
    @patch('zephy.__main__.print_summary_report')
    def test_main_workflow_success(self, mock_print_summary, mock_generate_reports,
                                  mock_load_tfe, mock_load_azure, mock_get_azure_cred,
                                  mock_get_tfe_token, tmp_path):
        """Test successful main workflow execution."""
        # Mock credentials
        mock_get_azure_cred.return_value = Mock()
        mock_get_tfe_token.return_value = "mock-token"

        # Mock resource loading
        mock_azure_resources = [
            Mock(id="/subscriptions/sub1/resourcegroups/rg1/providers/microsoft.compute/virtualmachines/vm1",
                 name="vm1", type="Microsoft.Compute/virtualMachines",
                 resource_group="rg1", location="eastus", provider="Microsoft.Compute", raw_data={})
        ]
        mock_tfe_resources = [
            Mock(id="/subscriptions/sub1/resourcegroups/rg1/providers/microsoft.compute/virtualmachines/vm1",
                 name="vm1", type="azurerm_linux_virtual_machine",
                 provider="azurerm", workspace="workspace1", module_path="", raw_data={})
        ]
        mock_load_azure.return_value = mock_azure_resources
        mock_load_tfe.return_value = mock_tfe_resources

        # Mock report generation
        mock_generate_reports.return_value = ["/tmp/report1.csv", "/tmp/report2.csv"]

        # Create config file
        config_file = tmp_path / "config.json"
        config_data = {
            "tfe_org": "test-org",
            "azure_subscription": "test-sub",
            "output_dir": str(tmp_path),
            "debug": False
        }
        import json
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        # Mock CLI args
        with patch('sys.argv', ['zephy', '--config', str(config_file)]):
            result = main.main()

        assert result == 0
        mock_get_azure_cred.assert_called_once()
        mock_get_tfe_token.assert_called_once()
        mock_load_azure.assert_called_once()
        mock_load_tfe.assert_called_once()
        mock_generate_reports.assert_called_once()
        mock_print_summary.assert_called_once()

    @patch('zephy.__main__.get_tfe_token')
    @patch('zephy.__main__.get_azure_credential')
    def test_main_missing_required_args(self, mock_get_azure_cred, mock_get_tfe_token):
        """Test main fails with missing required arguments."""
        with patch('sys.argv', ['zephy']):
            with pytest.raises(SystemExit) as exc_info:
                main.main()

        assert exc_info.value.code == 2  # argparse error

    @patch('zephy.__main__.get_tfe_token')
    @patch('zephy.__main__.get_azure_credential')
    @patch('zephy.__main__.load_azure_resources')
    @patch('zephy.__main__.load_tfe_resources')
    def test_main_dry_run_mode(self, mock_load_tfe, mock_load_azure, mock_get_azure_cred,
                              mock_get_tfe_token, capsys):
        """Test dry-run mode execution."""
        # Mock credentials
        mock_get_azure_cred.return_value = Mock()
        mock_get_tfe_token.return_value = "mock-token"

        # Mock resource loading (should not be called in dry-run)
        mock_load_azure.return_value = []
        mock_load_tfe.return_value = []

        with patch('sys.argv', ['zephy', '--tfe-org', 'test-org',
                               '--azure-subscription', 'test-sub', '--dry-run']):
            result = main.main()

        assert result == 0
        captured = capsys.readouterr()
        assert "DRY RUN MODE" in captured.out
        # In dry-run, resources should not be loaded
        mock_load_azure.assert_not_called()
        mock_load_tfe.assert_not_called()


class TestResourceMatchingIntegration:
    """Test resource matching with realistic data."""

    def test_full_matching_workflow(self):
        """Test complete matching workflow with realistic Azure and TFE resources."""
        from zephy.config import AzureResource, TFEResource

        # Create realistic Azure resources
        azure_resources = [
            AzureResource(
                id="/subscriptions/12345678-1234-1234-1234-123456789abc/resourceGroups/prod-rg/providers/Microsoft.Compute/virtualMachines/web-vm",
                name="web-vm",
                type="Microsoft.Compute/virtualMachines",
                resource_group="prod-rg",
                location="eastus",
                provider="Microsoft.Compute",
                raw_data={"sku": "Standard_DS1_v2"}
            ),
            AzureResource(
                id="/subscriptions/12345678-1234-1234-1234-123456789abc/resourceGroups/prod-rg/providers/Microsoft.Storage/storageAccounts/prodstorage",
                name="prodstorage",
                type="Microsoft.Storage/storageAccounts",
                resource_group="prod-rg",
                location="eastus",
                provider="Microsoft.Storage",
                raw_data={"sku": {"name": "Standard_LRS"}}
            ),
            AzureResource(
                id="/subscriptions/12345678-1234-1234-1234-123456789abc/resourceGroups/dev-rg/providers/Microsoft.Compute/virtualMachines/dev-vm",
                name="dev-vm",
                type="Microsoft.Compute/virtualMachines",
                resource_group="dev-rg",
                location="westus",
                provider="Microsoft.Compute",
                raw_data={"sku": "Standard_DS1_v2"}
            )
        ]

        # Create corresponding TFE resources
        tfe_resources = [
            TFEResource(
                id="/subscriptions/12345678-1234-1234-1234-123456789abc/resourceGroups/prod-rg/providers/Microsoft.Compute/virtualMachines/web-vm",
                name="web_server",
                type="azurerm_linux_virtual_machine",
                provider="azurerm",
                workspace="prod-workspace",
                module_path="modules/web",
                raw_data={"size": "Standard_DS1_v2"}
            ),
            TFEResource(
                id="/subscriptions/12345678-1234-1234-1234-123456789abc/resourceGroups/prod-rg/providers/Microsoft.Storage/storageAccounts/prodstorage",
                name="storage_account",
                type="azurerm_storage_account",
                provider="azurerm",
                workspace="prod-workspace",
                module_path="modules/storage",
                raw_data={"account_tier": "Standard"}
            ),
            TFEResource(
                id="/subscriptions/12345678-1234-1234-1234-123456789abc/resourceGroups/prod-rg/providers/Microsoft.Storage/storageAccounts/prodstorage",
                name="storage_account",
                type="azurerm_storage_account",
                provider="azurerm",
                workspace="staging-workspace",  # Multi-workspace
                module_path="modules/storage",
                raw_data={"account_tier": "Standard"}
            ),
            TFEResource(
                id="/subscriptions/12345678-1234-1234-1234-123456789abc/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
                name="test_network",
                type="azurerm_virtual_network",
                provider="azurerm",
                workspace="test-workspace",
                module_path="",
                raw_data={"address_space": ["10.0.0.0/16"]}
            )
        ]

        # Run matching
        report = match_resources(azure_resources, tfe_resources)

        # Verify results
        assert report.total_azure_resources == 3
        assert report.total_tfe_resources == 4
        assert report.matched_count == 2  # web-vm and prodstorage
        assert report.unmanaged_count == 1  # dev-vm
        assert report.orphaned_count == 1  # test-vnet
        assert report.multi_workspace_count == 1  # prodstorage

        # Check match details
        matches = report.matches
        assert len(matches) == 4

        # Find specific matches
        matched_results = [m for m in matches if m.match_status == "matched"]
        assert len(matched_results) == 2

        unmanaged_results = [m for m in matches if m.match_status == "unmanaged"]
        assert len(unmanaged_results) == 1
        assert unmanaged_results[0].azure_resource.name == "dev-vm"

        orphaned_results = [m for m in matches if m.match_status == "orphaned"]
        assert len(orphaned_results) == 1
        assert "test_network" in orphaned_results[0].tfe_resources[0].name

        multi_workspace_results = [m for m in matches if len(m.workspace_names) > 1]
        assert len(multi_workspace_results) == 1
        assert len(multi_workspace_results[0].workspace_names) == 2
        assert "prod-workspace" in multi_workspace_results[0].workspace_names
        assert "staging-workspace" in multi_workspace_results[0].workspace_names


class TestReportGenerationIntegration:
    """Test report generation with realistic data."""

    def test_generate_reports_with_real_data(self, tmp_path):
        """Test CSV report generation with realistic match data."""
        from zephy.config import AzureResource, TFEResource

        # Create test data
        azure_resources = [
            AzureResource(
                id="/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
                name="test-vm",
                type="Microsoft.Compute/virtualMachines",
                resource_group="test-rg",
                location="eastus",
                provider="Microsoft.Compute",
                raw_data={}
            )
        ]

        tfe_resources = [
            TFEResource(
                id="/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
                name="test_vm",
                type="azurerm_linux_virtual_machine",
                provider="azurerm",
                workspace="test-workspace",
                module_path="modules/compute",
                raw_data={}
            )
        ]

        # Generate reports
        report = match_resources(azure_resources, tfe_resources)
        output_dir = str(tmp_path / "reports")

        generated_files = generate_all_reports(report, azure_resources, tfe_resources, output_dir)

        # Verify files were created
        assert len(generated_files) == 5
        for file_path in generated_files:
            assert tmp_path.joinpath("reports").joinpath(file_path.split("/")[-1]).exists()

        # Check file contents (basic check)
        import csv
        with open(generated_files[0], 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]['resource_name'] == 'test-vm'
            assert rows[0]['match_status'] == 'matched'