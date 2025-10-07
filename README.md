# zephy

[![PyPI version](https://badge.fury.io/py/zephy.svg)](https://badge.fury.io/py/zephy)
[![Python Version](https://img.shields.io/pypi/pyversions/zephy.svg)](https://pypi.org/project/zephy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI Downloads](https://img.shields.io/pypi/dm/zephy.svg)](https://pypi.org/project/zephy/)
[![Downloads](https://pepy.tech/badge/zephy)](https://pepy.tech/project/zephy)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Azure TFE Resources Toolkit

Compare Azure resources deployed in a subscription against resources managed by Terraform Enterprise (TFE) workspaces. Identifies resource coverage gaps, unmanaged resources, and provides detailed resource inventory reports.

## Features

- **Resource Discovery**: Automatically discover all Azure resources in a subscription
- **TFE Integration**: Connect to Terraform Enterprise to analyze workspace state files
- **Coverage Analysis**: Identify which Azure resources are NOT managed by Terraform
- **Resource Matching**: Advanced matching algorithm using Azure resource IDs
- **CSV Reports**: Generate Excel-compatible CSV reports with UTF-8 BOM encoding
- **Caching**: Optional file system caching for improved performance
- **Manual Mode**: Fallback to manual Azure CLI commands when API access fails
- **Dry Run**: Preview execution plan without making API calls

## Installation

Requires Python 3.10 or higher.

```bash
pip install zephy
```

Now you can use it:

```bash
zephy --help
```

### Install From Source

```bash
git clone https://github.com/henrybravo/zephy.git
cd zephy
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

--or--

### Install From Source Using `uv` (recommended)

*[about uv](https://docs.astral.sh/uv/)*

```bash
git clone https://github.com/henrybravo/zephy.git
cd zephy
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install -e .
```

## Quick Start

### Basic Usage

```bash
# Login with az cli
az login

# Set environment variables
export TFE_TOKEN="your-tfe-token"
export AZURE_SUBSCRIPTION_ID="your-subscription-id"

# Run comparison
zephy \
  --tfe-org your-org \
  --azure-subscription $AZURE_SUBSCRIPTION_ID
```

### Using Configuration File

```bash
# Create config.json (see config.example.json)
zephy --config config.json
```

### Manual Azure CLI Mode

```bash
# Generate commands for manual execution

# change to your id:
export AZURE_SUBSCRIPTION_ID="00000000-0000-0000-0000-000000000000"

zephy \
  --azure-subscription $AZURE_SUBSCRIPTION_ID \
  --azcli-manually

# Run the generated az commands manually, then:
zephy \
  --tfe-org your-org \
  --azure-subscription $AZURE_SUBSCRIPTION_ID \
  --azure-input-file azure_resources_$AZURE_SUBSCRIPTION_ID.json
```

## Authentication

### Azure Authentication

Uses `DefaultAzureCredential` with automatic fallback:

1. Environment variables (`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`)
2. Azure CLI (`az login`)
3. Managed Identity (for CI/CD)

For service principal authentication, create a JSON file with the following format and use `--azure-creds-file`:

```json
{
  "client_id": "your-service-principal-client-id",
  "client_secret": "your-service-principal-client-secret",
  "tenant_id": "your-azure-tenant-id",
  "subscription_id": "your-azure-subscription-id"
}
```

### TFE Authentication

Set the `TFE_TOKEN` environment variable or use `--tfe-token` parameter.

For token from file, create a plain text file containing only the TFE API token and use `--tfe-creds-file`:

```
your-tfe-api-token-here
```

For self-hosted TFE instances with self-signed SSL certificates, use `--no-tfe-ssl-verify` to skip SSL certificate verification.

## Configuration

### Command Line Arguments

```bash
zephy --help
```
![zephy help menu](./zephy-help.png)

### Configuration File

Create a `config.json` file (see `config.example.json` for template):

```json
{
  "tfe_base_url": "https://app.terraform.io/api/v2",
  "tfe_ssl_verify": true,
  "tfe_org": "your-tfe-organization",
  "azure_subscription": "your-azure-subscription-id",
  "workspaces": ["workspace-1", "workspace-2"],
  "resource_groups": ["prod-rg", "shared-rg"],
  "tfe_token": null,
  "tfe_creds_file": null,
  "azure_creds_file": null,
  "azcli_manually": false,
  "azure_input_file": null,
  "resource_mode": "primary",
  "cache_ttl": 60,
  "no_cache": false,
  "output_dir": "./reports",
  "save_resources": false,
  "logfile_dir": "./logs",
  "debug": false,
  "dry_run": false,
  "parallel": 10
}
```

## Output

Generates five CSV files:

1. **`resources_comparison_TIMESTAMP.csv`**: All resources with match status
2. **`unmanaged_resources_TIMESTAMP.csv`**: Azure resources NOT in TFE
3. **`multi_workspace_resources_TIMESTAMP.csv`**: Resources managed by multiple workspaces
4. **`tfe_resources_inventory_TIMESTAMP.csv`**: Complete inventory of all TFE resources
5. **`azure_resources_inventory_TIMESTAMP.csv`**: Complete inventory of all Azure resources

- *TFE workspace tags are only available for commercial TFE workspaces* 
- *Azure resource groups tags only when using the azure api and not the Manual Azure CLI Mode*

## Generating Primary Resource Types

To generate the `PRIMARY_RESOURCE_TYPES.json` file with the correct Azure resource types:

```bash
# Ensure you're logged in to Azure CLI
az login

# Run the generation script
python generate_primary_resource_types.py
```

This script:
- Queries Azure for all available resource types
- Filters for primary infrastructure resources (VMs, databases, networks, etc.)
- Excludes auxiliary/support resource types
- Saves the filtered list to `PRIMARY_RESOURCE_TYPES.json`

## Examples

### Filter by Workspaces

```bash
zephy \
  --tfe-org your-org \
  --azure-subscription $AZURE_SUBSCRIPTION_ID \
  --workspaces "prod-app,prod-db"
```

### Detailed Resource Mode

```bash
zephy \
  --tfe-org your-org \
  --azure-subscription $AZURE_SUBSCRIPTION_ID \
  --resource-mode detailed
```

### Dry Run

```bash
zephy \
  --tfe-org your-org \
  --azure-subscription $AZURE_SUBSCRIPTION_ID \
  --dry-run
```

### Advanced Options

```bash
# Filter by resource groups
zephy \
  --tfe-org your-org \
  --azure-subscription $AZURE_SUBSCRIPTION_ID \
  --resource-groups "prod-rg,shared-rg"

# Use detailed resource mode and increase parallel requests
zephy \
  --tfe-org your-org \
  --azure-subscription $AZURE_SUBSCRIPTION_ID \
  --resource-mode detailed \
  --parallel 20

# Disable caching and set custom cache TTL
zephy \
  --tfe-org your-org \
  --azure-subscription $AZURE_SUBSCRIPTION_ID \
  --no-cache \
  --cache-ttl 120

# Use service principal credentials from file
zephy \
  --tfe-org your-org \
  --azure-subscription $AZURE_SUBSCRIPTION_ID \
  --azure-creds-file azure-creds.json

# Use TFE token from file
zephy \
  --tfe-org your-org \
  --azure-subscription $AZURE_SUBSCRIPTION_ID \
  --tfe-creds-file tfe-token.txt

# Skip SSL verification for self-hosted TFE
zephy \
  --tfe-org your-org \
  --azure-subscription $AZURE_SUBSCRIPTION_ID \
  --tfe-base-url https://your-self-hosted-tfe.com/api/v2 \
  --no-tfe-ssl-verify
```

## Development

### Setup Development Environment

```bash
pip install -e .[dev]
```

### Run Tests

```bash
uv pip install pytest

pytest tests/ -v --cov=zephy --cov-report=html
```

### Code Quality

```bash
black zephy/
flake8 zephy/
mypy zephy/
```

## Security

- Credentials are never logged in plain text
- Sensitive data is redacted in logs
- Config files with credentials trigger warnings
- Use environment variables for credentials in production


## Configure Azure App Registration for SDK Access

This guide assumes you already created an App Registration in Azure AD and have the following environment variables set:

```bash
export AZURE_CLIENT_ID="<your-azure-client-id>"
export AZURE_TENANT_ID="<your-tenant-id>"
export AZURE_SUBSCRIPTION_ID="<your-azure-subscription-id>"
```

1. Login with Azure CLI

Login with a user that has Owner or User Access Administrator on the subscription:

```bash
az login --tenant $AZURE_TENANT_ID
az account set --subscription $AZURE_SUBSCRIPTION_ID
```

2. Assign RBAC Role to the Service Principal

The app registration (service principal) needs at least Reader role to list resources.

If you need deployment/management rights, use Contributor instead.

```bash
az role assignment create \
  --assignee $AZURE_CLIENT_ID \
  --role "Reader" \
  --scope /subscriptions/$AZURE_SUBSCRIPTION_ID
```

For Contributor role:

```bash
az role assignment create \
  --assignee $AZURE_CLIENT_ID \
  --role "Contributor" \
  --scope /subscriptions/$AZURE_SUBSCRIPTION_ID
```

3. Verify the Role Assignment

Check if the role was applied correctly:

```bash
az role assignment list \
  --assignee $AZURE_CLIENT_ID \
  --scope /subscriptions/$AZURE_SUBSCRIPTION_ID \
  --output table
```

4. Refresh Tokens if Access Was Just Granted

If you get AuthorizationFailed after role assignment:

```bash
az account clear
```

Then restart your app to pick up fresh tokens.

## License

MIT License
