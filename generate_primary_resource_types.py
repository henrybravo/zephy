#!/usr/bin/env python3
"""
Script to generate PRIMARY_RESOURCE_TYPES.json with Azure primary resource types.

This script uses the Azure SDK to query resource providers and filters for primary
infrastructure resources that should be tracked by the Azure TFE Resources Toolkit.
"""

import json
import sys
from typing import List, Set

try:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.resource import ResourceManagementClient
except ImportError as e:
    print(f"Error: Missing required Azure SDK packages: {e}", file=sys.stderr)
    print("Install with: pip install azure-identity azure-mgmt-resource", file=sys.stderr)
    sys.exit(1)


def get_all_resource_types(credential: DefaultAzureCredential, subscription_id: str) -> Set[str]:
    """Get all Azure resource types using Azure SDK."""
    print("Fetching all Azure resource types using Azure SDK...")

    try:
        client = ResourceManagementClient(credential, subscription_id)

        resource_types = set()
        # Get all resource providers
        providers = client.providers.list()

        for provider in providers:
            if provider.resource_types:
                for resource_type in provider.resource_types:
                    # Format: Microsoft.Compute/virtualMachines
                    full_type = f"{provider.namespace}/{resource_type.resource_type}"
                    resource_types.add(full_type)

        print(f"Found {len(resource_types)} total resource types")
        return resource_types

    except Exception as e:
        print(f"Error fetching resource types: {e}", file=sys.stderr)
        sys.exit(1)


def filter_primary_resource_types(all_types: Set[str]) -> List[str]:
    """Filter for primary infrastructure resource types."""
    print("Filtering for primary resource types...")

    # Primary resource type patterns (full Microsoft.Provider/resourceType format)
    primary_patterns = {
        # Compute
        "Microsoft.Compute/virtualMachines",
        "Microsoft.Compute/virtualMachineScaleSets",
        "Microsoft.Compute/disks",
        "Microsoft.Compute/availabilitySets",
        "Microsoft.Compute/snapshots",
        "Microsoft.Compute/images",
        "Microsoft.Compute/galleries",
        "Microsoft.Compute/proximityPlacementGroups",
        "Microsoft.Compute/hostGroups",
        "Microsoft.Compute/sshPublicKeys",

        # Web/App Services
        "Microsoft.Web/sites",
        "Microsoft.Web/serverFarms",
        "Microsoft.Web/staticSites",
        "Microsoft.Web/hostingEnvironments",
        "Microsoft.Web/certificates",
        "Microsoft.Web/customDomains",

        # Storage
        "Microsoft.Storage/storageAccounts",

        # Database
        "Microsoft.Sql/servers",
        "Microsoft.Sql/databases",
        "Microsoft.Sql/managedInstances",
        "Microsoft.Sql/elasticPools",
        "Microsoft.Sql/failoverGroups",
        "Microsoft.DBforPostgreSQL/servers",
        "Microsoft.DBforMySQL/servers",
        "Microsoft.DBforMariaDB/servers",
        "Microsoft.DocumentDB/databaseAccounts",

        # Containers
        "Microsoft.ContainerService/managedClusters",
        "Microsoft.ContainerInstance/containerGroups",
        "Microsoft.ContainerRegistry/registries",

        # Networking
        "Microsoft.Network/virtualNetworks",
        "Microsoft.Network/applicationGateways",
        "Microsoft.Network/loadBalancers",
        "Microsoft.Network/publicIPAddresses",
        "Microsoft.Network/networkSecurityGroups",
        "Microsoft.Network/routeTables",
        "Microsoft.Network/networkInterfaces",
        "Microsoft.Network/virtualNetworkGateways",
        "Microsoft.Network/localNetworkGateways",
        "Microsoft.Network/connections",
        "Microsoft.Network/expressRouteCircuits",
        "Microsoft.Network/trafficManagerProfiles",
        "Microsoft.Network/networkWatchers",
        "Microsoft.Network/bastionHosts",
        "Microsoft.Network/firewallPolicies",
        "Microsoft.Network/webApplicationFirewallPolicies",

        # Security
        "Microsoft.KeyVault/vaults",

        # Analytics & Data
        "Microsoft.Synapse/workspaces",
        "Microsoft.DataFactory/factories",
        "Microsoft.StreamAnalytics/streamingjobs",
        "Microsoft.DataLakeStore/accounts",
        "Microsoft.DataLakeAnalytics/accounts",

        # IoT
        "Microsoft.Devices/IotHubs",
        "Microsoft.IoTHub/hubs",

        # Media
        "Microsoft.Media/mediaservices",

        # Machine Learning
        "Microsoft.MachineLearningServices/workspaces",

        # Search
        "Microsoft.Search/searchServices",

        # Messaging
        "Microsoft.EventHub/namespaces",
        "Microsoft.ServiceBus/namespaces",
        "Microsoft.NotificationHubs/namespaces",
        "Microsoft.Relay/namespaces",

        # Logic Apps
        "Microsoft.Logic/workflows",

        # API Management
        "Microsoft.ApiManagement/service",

        # App Configuration
        "Microsoft.AppConfiguration/configurationStores",

        # Cache
        "Microsoft.Cache/redis",

        # Functions
        "Microsoft.Web/functions",  # Function Apps
    }

    # Filter resource types that exactly match our primary patterns
    primary_types = [rt for rt in all_types if rt in primary_patterns]
    print(f"Found {len(primary_types)} exact matches from primary patterns")

    # Additional filtering for common infrastructure patterns
    additional_count = 0

    # Look for other common infrastructure resource types
    for resource_type in all_types:
        if resource_type in primary_types:
            continue  # Already included

        # Skip auxiliary operations and metadata
        resource_name = resource_type.split('/', 1)[1] if '/' in resource_type else resource_type

        skip_indicators = [
            'operations', 'locations', 'checknameavailability', 'usages',
            'diagnostics', 'metrics', 'logs', 'audits', 'access', 'permissions',
            'roles', 'policies', 'tags', 'locks', 'deployments', 'templates',
            'scripts', 'runcommands', 'extensions', 'patches', 'assessments',
            'configurations', 'settings', 'properties', 'metadata', 'status',
            'state', 'support', 'cases', 'tenants', 'changes', 'ownerships',
            'transfers', 'moves', 'validations', 'checks', 'availabilities',
            'quotas', 'limits', 'usages', 'billings'
        ]

        if any(skip in resource_name.lower() for skip in skip_indicators):
            continue

        # Include additional infrastructure resources that might be useful
        include_patterns = [
            'virtualmachines', 'storageaccounts', 'databases', 'servers',
            'networks', 'securitygroups', 'keyvaults', 'loadbalancers',
            'applicationgateways', 'containers', 'kubernetes', 'webapps',
            'functions', 'redis', 'cosmosdb', 'search', 'eventhubs',
            'servicebus', 'logicapps', 'apimanagement'
        ]

        if any(pattern in resource_name.lower() for pattern in include_patterns):
            primary_types.append(resource_type)
            additional_count += 1

    print(f"Added {additional_count} additional resource types from pattern matching")

    # Remove duplicates and sort
    filtered_types = sorted(list(set(primary_types)))

    print(f"Total filtered to {len(filtered_types)} primary resource types")
    return filtered_types


def save_to_json(resource_types: List[str], filename: str = "PRIMARY_RESOURCE_TYPES.json") -> None:
    """Save resource types to JSON file."""
    print(f"Saving to {filename}...")

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(resource_types, f, indent=2, ensure_ascii=False)

    print(f"Successfully saved {len(resource_types)} resource types to {filename}")


def get_subscription_id() -> str:
    """Get subscription ID from config.json, environment, or use dummy for provider listing."""
    # Try to get from config.json first
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            subscription_id = config.get('azure_subscription')
            if subscription_id:
                print(f"Using subscription from config.json: {subscription_id}")
                return subscription_id
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass  # Config not found or invalid, continue to next option

    # Try to get from environment
    import os
    subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
    if subscription_id:
        print(f"Using subscription from environment: {subscription_id}")
        return subscription_id

    # For provider listing, we can use a dummy subscription ID
    # The providers.list() API doesn't actually validate the subscription
    dummy_subscription = "00000000-0000-0000-0000-000000000000"
    print(f"No subscription found in config or environment, using dummy subscription for provider listing")
    return dummy_subscription


def main():
    """Main entry point."""
    print("Azure Primary Resource Types Generator")
    print("=" * 40)
    print("This script uses the Azure SDK to generate PRIMARY_RESOURCE_TYPES.json")
    print()

    # Get Azure credentials
    try:
        credential = DefaultAzureCredential()
        print("✓ Azure credentials initialized")
    except Exception as e:
        print(f"Error: Failed to initialize Azure credentials: {e}", file=sys.stderr)
        print("Please ensure you are logged in with 'az login' or have appropriate credentials", file=sys.stderr)
        sys.exit(1)

    # Get subscription ID
    subscription_id = get_subscription_id()

    # Get and filter resource types
    all_types = get_all_resource_types(credential, subscription_id)
    primary_types = filter_primary_resource_types(all_types)

    # Save to file
    save_to_json(primary_types)

    print("\nDone! You can now use PRIMARY_RESOURCE_TYPES.json in your Azure TFE Resources Toolkit.")


if __name__ == "__main__":
    main()