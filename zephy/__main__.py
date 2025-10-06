"""Main CLI entry point for Azure TFE Resources Toolkit."""

from .tfe_client import TFEClient
from .resource_matcher import match_resources
from .report_generator import generate_all_reports, print_summary_report
from .logger import setup_logging
from .config import load_config_from_file, merge_configs
from .cache import get_cache_filename, load_from_cache, save_to_cache
from .azure_client import (
    AzureClient,
    load_resources_from_json_file,
    print_manual_azure_commands,
)
from .auth import get_azure_credential, get_tfe_token, load_azure_creds_from_file
from .__version__ import __author__, __date__, __version__
from . import logger
import argparse
import sys
import warnings
from typing import List, Optional

# Suppress Azure SDK syntax warnings
warnings.filterwarnings("ignore", category=SyntaxWarning, module="azure.*")


# Zephy ASCII art logo
ZEPHY_LOGO = """
 ███████╗███████╗██████╗ ██╗  ██╗██╗   ██╗
╚══███╔╝██╔════╝██╔══██╗██║  ██║╚██╗ ██╔╝
  ███╔╝ █████╗  ██████╔╝███████║ ╚████╔╝
 ███╔╝  ██╔══╝  ██╔═══╝ ██╔══██║  ╚██╔╝
███████╗███████╗██║     ██║  ██║   ██║
╚══════╝╚══════╝╚═╝     ╚═╝  ╚═╝   ╚═╝
"""


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with all CLI options."""
    description = f"""{ZEPHY_LOGO}
  Compare Azure-Terraform Enterprise Resources
-------------------------------------------------
author: {__author__}
version: {__version__}
date: {__date__}
"""
    parser = argparse.ArgumentParser(
        prog="zephy",
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  zephy --tfe-org my-org --azure-subscription abc123
  zephy --config config.json --debug
  zephy --tfe-org my-org --azure-subscription abc123 --dry-run
        """,
    )

    # Required arguments (can come from config file)
    parser.add_argument(
        "--tfe-org", help="TFE organization name (required, can be in config file)"
    )
    parser.add_argument(
        "--azure-subscription",
        help="Azure subscription ID (required, can be in config file)",
    )

    # Optional filtering
    parser.add_argument(
        "--workspaces",
        default=argparse.SUPPRESS,
        help="Comma-separated list of TFE workspace names (default: all)",
    )
    parser.add_argument(
        "--resource-groups",
        default=argparse.SUPPRESS,
        help="Comma-separated list of Azure resource group names (default: all)",
    )

    # Authentication
    parser.add_argument(
        "--tfe-token",
        default=argparse.SUPPRESS,
        help="TFE API token (overrides env var TFE_TOKEN)",
    )
    parser.add_argument(
        "--tfe-creds-file",
        default=argparse.SUPPRESS,
        help="Path to file containing TFE token",
    )
    parser.add_argument(
        "--tfe-ssl-verify",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Verify SSL certificates for TFE API calls (default: true)",
    )
    parser.add_argument(
        "--no-tfe-ssl-verify",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Skip SSL certificate verification for TFE API calls",
    )
    parser.add_argument(
        "--azure-creds-file",
        default=argparse.SUPPRESS,
        help="Path to JSON file with Azure service principal credentials",
    )
    parser.add_argument(
        "--azcli-manually",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Enable Azure CLI manual fallback mode",
    )
    parser.add_argument(
        "--azure-input-file",
        default=argparse.SUPPRESS,
        help="Path to JSON file from az resource list (for manual mode)",
    )

    # Processing options
    parser.add_argument(
        "--resource-mode",
        choices=["primary", "detailed"],
        default=argparse.SUPPRESS,
        help="Resource filtering: primary or detailed (default: primary)",
    )
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=argparse.SUPPRESS,
        help="Cache freshness in minutes (default: 60)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Disable cache reading (force fresh API calls)",
    )

    # Output options
    parser.add_argument(
        "--output-dir",
        default=argparse.SUPPRESS,
        help="Directory for CSV output files (default: .)",
    )
    parser.add_argument(
        "--save-resources",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Save intermediate JSON files (Azure/TFE resources)",
    )
    parser.add_argument(
        "--logfile-dir",
        default=argparse.SUPPRESS,
        help="Directory for log files (default: .)",
    )

    # Execution options
    parser.add_argument(
        "--debug",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Enable debug logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Show execution plan without making API calls",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=argparse.SUPPRESS,
        help="Number of concurrent API calls (default: 10)",
    )

    # Configuration
    parser.add_argument(
        "--config",
        help="Load configuration from JSON file (CLI args override file values)",
    )

    # Version argument
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    # Hidden about argument
    parser.add_argument(
        "--about",
        action="store_true",
        help=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
    )

    return parser


def print_about() -> None:
    """Print the Zephy logo and about text."""
    about_text = f"""{ZEPHY_LOGO}
"I am Zephyrus, the renewing west wind bearer of clarity across 
     clouded horizons, unraveler of resource enigmas."
..............................................
  Compare Azure-Terraform Enterprise Resources:
    <==----------------------------------------------------==>
      <== when your clouds' resource tagging strategy is missing ==>
        <==-------------------------------------------------------------==>
             .................................................................
"""
    print(about_text)


def parse_workspace_filter(workspaces_arg: Optional[str]) -> Optional[List[str]]:
    """Parse workspace filter argument."""
    if not workspaces_arg:
        return None
    return [ws.strip() for ws in workspaces_arg.split(",") if ws.strip()]


def parse_resource_group_filter(rg_arg: Optional[str]) -> Optional[List[str]]:
    """Parse resource group filter argument."""
    if not rg_arg:
        return None
    return [rg.strip() for rg in rg_arg.split(",") if rg.strip()]


def handle_manual_azure_mode(subscription_id: str) -> None:
    """Handle manual Azure CLI mode."""
    print_manual_azure_commands(subscription_id)
    sys.exit(0)


def load_azure_resources(config, azure_cred) -> List:
    """Load Azure resources from API or cache or manual file."""
    log = logger.get_logger(__name__)

    # Check for manual input file first
    if config.azure_input_file:
        log.info(
            f"Loading Azure resources from manual input file: {
                config.azure_input_file}"
        )
        return load_resources_from_json_file(config.azure_input_file)

    # Try cache first (unless disabled)
    if not config.no_cache:
        cache_file = get_cache_filename(
            "azure_resources",
            config.tfe_org,
            config.azure_subscription,
            config.resource_mode,
        )
        cached_data = load_from_cache(cache_file, config.cache_ttl)
        if cached_data:
            log.info("Using cached Azure resources")
            return cached_data

    # Fetch from API
    log.info("Fetching Azure resources from API")
    client = AzureClient(azure_cred, config.azure_subscription)
    resources = client.get_all_resources(config.resource_groups, config.resource_mode)

    # Save to cache if requested
    if config.save_resources:
        cache_file = get_cache_filename(
            "azure_resources",
            config.tfe_org,
            config.azure_subscription,
            config.resource_mode,
        )
        save_to_cache(resources, cache_file, config.cache_ttl)

    return resources


def load_tfe_resources(config, tfe_token) -> List:
    """Load TFE resources from API or cache."""
    log = logger.get_logger(__name__)

    # Try cache first (unless disabled)
    if not config.no_cache:
        cache_file = get_cache_filename(
            "tfe_resources",
            config.tfe_org,
            config.azure_subscription,
            config.resource_mode,
        )
        cached_data = load_from_cache(cache_file, config.cache_ttl)
        if cached_data:
            log.info("Using cached TFE resources")
            return cached_data

    # Fetch from API
    log.info("Fetching TFE resources from API")
    client = TFEClient(tfe_token, config.tfe_base_url, config.tfe_ssl_verify)
    resources = client.get_all_resources(
        config.tfe_org, config.workspaces, config.parallel
    )

    # Save to cache if requested
    if config.save_resources:
        cache_file = get_cache_filename(
            "tfe_resources",
            config.tfe_org,
            config.azure_subscription,
            config.resource_mode,
        )
        save_to_cache(resources, cache_file, config.cache_ttl)

    return resources


def main() -> int:
    """Main entry point."""
    try:
        # Parse CLI arguments
        parser = create_parser()
        cli_args = parser.parse_args()

        # Handle --about argument (hidden feature)
        if hasattr(cli_args, "about") and cli_args.about:
            print_about()
            return 0

        # Load config file if specified
        config_file_data = None
        if cli_args.config:
            config_file_data = load_config_from_file(cli_args.config)

        # Parse filter arguments
        workspace_filter = parse_workspace_filter(getattr(cli_args, "workspaces", None))
        rg_filter = parse_resource_group_filter(
            getattr(cli_args, "resource_groups", None)
        )

        # Handle SSL verify flags
        ssl_verify = True  # default
        if hasattr(cli_args, "tfe_ssl_verify") and cli_args.tfe_ssl_verify:
            ssl_verify = True
        elif hasattr(cli_args, "no_tfe_ssl_verify") and cli_args.no_tfe_ssl_verify:
            ssl_verify = False

        # Create CLI args dict for merging
        cli_dict = vars(cli_args)
        cli_dict["workspaces"] = workspace_filter
        cli_dict["resource_groups"] = rg_filter
        cli_dict["tfe_ssl_verify"] = ssl_verify

        # Merge configurations
        config = merge_configs(cli_dict, config_file_data)

        # Validate required arguments (can come from CLI or config file)
        if not config.tfe_org:
            parser.error(
                "--tfe-org is required. Provide it via:\n"
                "  1. Command line: --tfe-org <org-name>\n"
                "  2. Config file: --config <config.json> (with 'tfe_org' field)"
            )
        if not config.azure_subscription:
            parser.error(
                "--azure-subscription is required. Provide it via:\n"
                "  1. Command line: --azure-subscription <subscription-id>\n"
                "  2. Config file: --config <config.json> (with 'azure_subscription' field)"
            )

        # Setup logging
        setup_logging(config.debug, config.logfile_dir)
        log = logger.get_logger(__name__)

        log.info("Zephy starting")

        # Handle manual Azure mode
        if config.azcli_manually and not config.azure_input_file:
            handle_manual_azure_mode(config.azure_subscription)

        # Dry run mode
        if config.dry_run:
            print_dry_run_info(config)
            return 0

        # Get credentials
        log.info("Setting up authentication")

        # Azure credentials
        azure_cred = get_azure_credential(config.azure_creds_file)
        if config.azure_creds_file:
            load_azure_creds_from_file(config.azure_creds_file)

        # TFE token
        tfe_token = get_tfe_token(config.tfe_token, config.tfe_creds_file)

        # Load resources
        log.info("Loading resources")
        azure_resources = load_azure_resources(config, azure_cred)
        tfe_resources = load_tfe_resources(config, tfe_token)

        # Match resources
        log.info("Matching resources")
        report = match_resources(azure_resources, tfe_resources)

        # Generate reports
        log.info("Generating reports")
        generated_files = generate_all_reports(
            report, azure_resources, tfe_resources, config.output_dir
        )

        # Calculate counts
        resource_group_count = len(set(r.resource_group for r in azure_resources))
        workspace_count = len(set(r.workspace for r in tfe_resources))

        # Print summary
        print_summary_report(
            report,
            config.tfe_org,
            config.azure_subscription,
            generated_files,
            resource_group_count,
            workspace_count,
        )

        log.info("Zephy completed successfully")
        return 0

    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        logger.get_logger(__name__).exception("Unhandled exception")
        return 1


def print_dry_run_info(config) -> None:
    """Print dry run information."""
    print("=== DRY RUN MODE ===")
    print()
    print(
        "Configuration Source: CLI + config file"
        if config.config_file
        else "Configuration Source: CLI"
    )
    print()
    print("Configuration:")
    print(f"  TFE Organization: {config.tfe_org}")
    print(f"  Azure Subscription: {config.azure_subscription}")
    print(
        f"  Workspace Filter: {
            ', '.join(
                config.workspaces) if config.workspaces else 'ALL'}"
    )
    print(
        f"  Resource Group Filter: {
            ', '.join(
                config.resource_groups) if config.resource_groups else 'ALL'}"
    )
    print(f"  Resource Mode: {config.resource_mode}")
    print(f"  Parallel Requests: {config.parallel}")
    print()
    print("Authentication:")
    print("  TFE Token: ***redacted***")
    print(
        "  Azure Auth: DefaultAzureCredential (will try: env vars → CLI → managed identity)"
    )
    print()
    print("API Calls Plan:")
    print(
        "  [Azure] GET subscription resource groups → /subscriptions/{id}/resourcegroups"
    )
    print(
        "  [Azure] GET resources per RG → /subscriptions/{id}/resourceGroups/{rg}/resources (estimated)"
    )
    print("  [TFE] GET workspaces → /api/v2/organizations/{org}/workspaces (paginated)")
    print(
        "  [TFE] GET state versions → /api/v2/workspaces/{ws-id}/current-state-version"
    )
    print()
    print("Comparison Logic:")
    print("  1. Build Azure resource index by resource_id (lowercase)")
    print("  2. Build TFE resource index by resource attributes.id (lowercase)")
    print("  3. Perform N×M matching across all workspaces and resource groups")
    print("  4. Calculate match statistics")
    print()
    from .report_generator import generate_timestamp

    timestamp = generate_timestamp()
    output_dir = config.output_dir
    if not output_dir.endswith("/"):
        output_dir += "/"

    print("Output Files (would be generated):")
    print(f"  - {output_dir}resources_comparison_{timestamp}.csv")
    print(f"  - {output_dir}unmanaged_resources_{timestamp}.csv")
    print(f"  - {output_dir}multi_workspace_resources_{timestamp}.csv")
    print(f"  - {output_dir}tfe_resources_inventory_{timestamp}.csv")
    print(f"  - {output_dir}azure_resources_inventory_{timestamp}.csv")
    print()
    print("=== DRY RUN COMPLETE - No actions taken ===")


if __name__ == "__main__":
    sys.exit(main())
