"""Tests for config module."""

import json
import pytest
from zephy.config import Config, load_config_from_file, merge_configs


class TestConfig:
    """Test Config dataclass."""

    def test_valid_config(self):
        """Test creating a valid config."""
        config = Config(
            tfe_org="test-org",
            azure_subscription="test-sub",
            workspaces=["ws1", "ws2"],
            resource_groups=["rg1"],
            resource_mode="primary",
            cache_ttl=60,
            parallel=5,
        )
        assert config.tfe_org == "test-org"
        assert config.azure_subscription == "test-sub"
        assert config.workspaces == ["ws1", "ws2"]
        assert config.resource_groups == ["rg1"]
        assert config.resource_mode == "primary"
        assert config.cache_ttl == 60
        assert config.parallel == 5

    def test_invalid_resource_mode(self):
        """Test invalid resource_mode raises ValueError."""
        with pytest.raises(ValueError, match="resource_mode must be 'primary' or 'detailed'"):
            Config(tfe_org="test", azure_subscription="test", resource_mode="invalid")

    def test_negative_cache_ttl(self):
        """Test negative cache_ttl raises ValueError."""
        with pytest.raises(ValueError, match="cache_ttl must be non-negative"):
            Config(tfe_org="test", azure_subscription="test", cache_ttl=-1)

    def test_invalid_parallel(self):
        """Test parallel < 1 raises ValueError."""
        with pytest.raises(ValueError, match="parallel must be at least 1"):
            Config(tfe_org="test", azure_subscription="test", parallel=0)


class TestLoadConfigFromFile:
    """Test load_config_from_file function."""

    def test_load_valid_config(self, tmp_path):
        """Test loading valid config file."""
        config_data = {
            "tfe_org": "test-org",
            "azure_subscription": "test-sub",
            "workspaces": ["ws1", "ws2"],
            "resource_groups": "rg1,rg2",  # Test comma-separated string
            "resource_mode": "detailed",
            "cache_ttl": 120,
            "parallel": 10,
        }
        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        result = load_config_from_file(str(config_file))
        assert result["tfe_org"] == "test-org"
        assert result["azure_subscription"] == "test-sub"
        assert result["workspaces"] == ["ws1", "ws2"]
        assert result["resource_groups"] == ["rg1", "rg2"]
        assert result["resource_mode"] == "detailed"
        assert result["cache_ttl"] == 120
        assert result["parallel"] == 10

    def test_load_missing_file(self):
        """Test loading missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config_from_file("nonexistent.json")

    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON raises ValueError."""
        config_file = tmp_path / "invalid.json"
        with open(config_file, "w") as f:
            f.write("invalid json")

        with pytest.raises(ValueError, match="Invalid JSON"):
            load_config_from_file(str(config_file))

    def test_normalize_array_fields(self, tmp_path):
        """Test normalization of array fields."""
        config_data = {
            "tfe_org": "test-org",
            "azure_subscription": "test-sub",
            "workspaces": "ws1, ws2 , ws3",  # With spaces
            "resource_groups": ["rg1", "rg2"],  # Already list
        }
        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        result = load_config_from_file(str(config_file))
        assert result["workspaces"] == ["ws1", "ws2", "ws3"]
        assert result["resource_groups"] == ["rg1", "rg2"]

    def test_unknown_fields_warning(self, tmp_path, caplog):
        """Test warning for unknown fields."""
        config_data = {
            "tfe_org": "test-org",
            "azure_subscription": "test-sub",
            "unknown_field": "value",
        }
        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        result = load_config_from_file(str(config_file))
        assert "Unknown fields in config file: unknown_field" in caplog.text

    def test_credential_field_warning(self, tmp_path, caplog):
        """Test warning for credential fields."""
        config_data = {
            "tfe_org": "test-org",
            "azure_subscription": "test-sub",
            "tfe_token": "secret-token",
        }
        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        result = load_config_from_file(str(config_file))
        assert "Config file contains credential field 'tfe_token'" in caplog.text

    def test_invalid_field_type(self, tmp_path):
        """Test invalid field type raises ValueError."""
        config_data = {
            "tfe_org": "test-org",
            "azure_subscription": "test-sub",
            "workspaces": 123,  # Invalid type
        }
        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        with pytest.raises(ValueError, match="Field 'workspaces' must be a list or comma-separated string"):
            load_config_from_file(str(config_file))


class TestMergeConfigs:
    """Test merge_configs function."""

    def test_merge_cli_overrides_config(self):
        """Test CLI args override config file values."""
        cli_args = {
            "tfe_org": "cli-org",
            "azure_subscription": "cli-sub",
            "workspaces": ["cli-ws"],
        }
        config_file_data = {
            "tfe_org": "file-org",
            "azure_subscription": "file-sub",
            "workspaces": ["file-ws"],
            "resource_mode": "detailed",
        }

        result = merge_configs(cli_args, config_file_data)
        assert result.tfe_org == "cli-org"
        assert result.azure_subscription == "cli-sub"
        assert result.workspaces == ["cli-ws"]
        assert result.resource_mode == "detailed"  # From config file

    def test_merge_none_values_not_override(self):
        """Test None values in CLI don't override config file."""
        cli_args = {
            "tfe_org": "cli-org",
            "workspaces": None,  # None should not override
        }
        config_file_data = {
            "tfe_org": "file-org",
            "azure_subscription": "file-sub",
            "workspaces": ["file-ws"],
        }

        result = merge_configs(cli_args, config_file_data)
        assert result.tfe_org == "cli-org"
        assert result.azure_subscription == "file-sub"
        assert result.workspaces == ["file-ws"]

    def test_merge_no_config_file(self):
        """Test merging with no config file."""
        cli_args = {
            "tfe_org": "cli-org",
            "azure_subscription": "cli-sub",
        }

        result = merge_configs(cli_args, None)
        assert result.tfe_org == "cli-org"
        assert result.azure_subscription == "cli-sub"
        assert result.workspaces == []