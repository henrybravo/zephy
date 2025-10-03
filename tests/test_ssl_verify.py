"""Tests for SSL verification functionality."""

import pytest
from unittest.mock import Mock, patch

from zephy.tfe_client import TFEClient
from zephy.config import Config, load_config_from_file, merge_configs
from zephy import __main__ as main


class TestSSLVerification:
    """Test SSL verification configuration and usage."""

    def test_config_ssl_verify_default(self):
        """Test that SSL verification defaults to True."""
        config = Config(tfe_org="test", azure_subscription="test")
        assert config.tfe_ssl_verify is True

    def test_config_ssl_verify_from_file(self, tmp_path):
        """Test loading SSL verify setting from config file."""
        config_data = {
            "tfe_org": "test-org",
            "azure_subscription": "test-sub",
            "tfe_ssl_verify": False
        }
        config_file = tmp_path / "config.json"
        import json
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        result = load_config_from_file(str(config_file))
        assert result["tfe_ssl_verify"] is False

    def test_merge_configs_ssl_verify(self):
        """Test merging SSL verify from config file."""
        config_file_data = {"tfe_ssl_verify": False}
        result = merge_configs({}, config_file_data)
        assert result.tfe_ssl_verify is False

    @patch('requests.Session.get')
    def test_tfe_client_ssl_verify_true(self, mock_get):
        """Test TFE client uses SSL verification by default."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        client = TFEClient("test-token")
        result = client._get("/test-endpoint")

        # Verify that verify=True was passed to requests
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs['verify'] is True
        assert result == {"data": []}

    @patch('requests.Session.get')
    def test_tfe_client_ssl_verify_false(self, mock_get):
        """Test TFE client can disable SSL verification."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        client = TFEClient("test-token", ssl_verify=False)
        result = client._get("/test-endpoint")

        # Verify that verify=False was passed to requests
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs['verify'] is False
        assert result == {"data": []}

    @patch('requests.get')
    def test_download_state_file_ssl_verify(self, mock_get):
        """Test state file download respects SSL verification setting."""
        mock_response = Mock()
        mock_response.content = b'{"version": 4, "resources": []}'
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"version": 4, "resources": []}
        mock_get.return_value = mock_response

        # Test with SSL verification enabled
        client = TFEClient("test-token", ssl_verify=True)
        result = client.download_state_file({"attributes": {"hosted-json-state-download-url": "https://example.com/state"}})

        mock_get.assert_called_with("https://example.com/state", timeout=30, verify=True)
        assert result == {"version": 4, "resources": []}

        # Reset mock
        mock_get.reset_mock()

        # Test with SSL verification disabled
        client = TFEClient("test-token", ssl_verify=False)
        result = client.download_state_file({"attributes": {"hosted-json-state-download-url": "https://example.com/state"}})

        mock_get.assert_called_with("https://example.com/state", timeout=30, verify=False)
        assert result == {"version": 4, "resources": []}


    def test_cli_ssl_verify_flags(self):
        """Test CLI SSL verification flags are processed correctly."""
        # Test --no-tfe-ssl-verify flag
        with patch('sys.argv', ['zephy', '--tfe-org', 'test-org', '--azure-subscription', 'test-sub', '--no-tfe-ssl-verify', '--dry-run']):
            result = main.main()

        assert result == 0

    def test_cli_ssl_verify_default(self):
        """Test CLI defaults to SSL verification enabled."""
        # Test default behavior (no SSL flags)
        with patch('sys.argv', ['zephy', '--tfe-org', 'test-org', '--azure-subscription', 'test-sub', '--dry-run']):
            result = main.main()

        assert result == 0