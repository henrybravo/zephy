"""Tests for utils module."""

import pytest

from zephy.utils import normalize_resource_id, parse_provider_from_type, parse_provider_from_tfe_provider


class TestNormalizeResourceId:
    """Test resource ID normalization."""

    def test_normalize_basic_resource_id(self):
        """Test basic resource ID normalization."""
        resource_id = "/subscriptions/abc123/resourceGroups/my-rg/providers/Microsoft.Compute/virtualMachines/vm1"
        expected = "/subscriptions/abc123/resourcegroups/my-rg/providers/microsoft.compute/virtualmachines/vm1"
        assert normalize_resource_id(resource_id) == expected

    def test_normalize_with_trailing_slash(self):
        """Test normalization removes trailing slashes."""
        resource_id = "/subscriptions/abc123/resourceGroups/my-rg/providers/Microsoft.Compute/virtualMachines/vm1/"
        expected = "/subscriptions/abc123/resourcegroups/my-rg/providers/microsoft.compute/virtualmachines/vm1"
        assert normalize_resource_id(resource_id) == expected

    def test_normalize_empty_string(self):
        """Test normalization of empty string."""
        assert normalize_resource_id("") == ""

    def test_normalize_none_input(self):
        """Test normalization handles None gracefully."""
        assert normalize_resource_id(None) == ""

    def test_normalize_case_insensitive(self):
        """Test that normalization is case insensitive."""
        id1 = "/SUBSCRIPTIONS/ABC123/RESOURCEGROUPS/MY-RG/PROVIDERS/MICROSOFT.COMPUTE/VIRTUALMACHINES/VM1"
        id2 = "/subscriptions/abc123/resourceGroups/my-rg/providers/Microsoft.Compute/virtualMachines/vm1"
        assert normalize_resource_id(id1) == normalize_resource_id(id2)


class TestParseProviderFromType:
    """Test provider parsing from resource type."""

    def test_parse_standard_provider(self):
        """Test parsing standard Azure provider."""
        resource_type = "Microsoft.Compute/virtualMachines"
        assert parse_provider_from_type(resource_type) == "Microsoft.Compute"

    def test_parse_simple_provider(self):
        """Test parsing simple provider name."""
        resource_type = "azurerm_linux_virtual_machine"
        assert parse_provider_from_type(resource_type) == "azurerm_linux_virtual_machine"

    def test_parse_no_slash(self):
        """Test parsing when no slash is present."""
        resource_type = "Microsoft.Storage"
        assert parse_provider_from_type(resource_type) == "Microsoft.Storage"


class TestParseProviderFromTfeProvider:
    """Test provider parsing from TFE provider string."""

    def test_parse_hashicorp_provider(self):
        """Test parsing HashiCorp registry provider."""
        provider_string = 'provider["registry.terraform.io/hashicorp/azurerm"]'
        assert parse_provider_from_tfe_provider(provider_string) == "azurerm"

    def test_parse_simple_provider(self):
        """Test parsing simple provider reference."""
        provider_string = 'provider["azurerm"]'
        assert parse_provider_from_tfe_provider(provider_string) == "azurerm"

    def test_parse_unknown_format(self):
        """Test parsing unknown provider format."""
        provider_string = "some.unknown.format"
        assert parse_provider_from_tfe_provider(provider_string) == "unknown"