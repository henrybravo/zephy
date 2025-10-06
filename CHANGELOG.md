# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-10-06

### Added
- **Resource Group Tags**: Azure resource inventory now includes resource group tags (`rg_tags` column)
- **Workspace Tags**: TFE resource inventory now includes workspace tags (`ws_tags` column)
- **Enhanced CSV Reports**: All inventory CSV files now contain tag information for better resource categorization

### Changed
- Updated CSV output specifications to include tag columns
- Modified Azure client to fetch resource group tags during resource discovery
- Modified TFE client to fetch workspace tags during state processing

### Technical Details
- Added `rg_tags` field to `AzureResource` dataclass
- Added `ws_tags` field to `TFEResource` dataclass
- Updated report generation to include tag columns in CSV output
- Tags are formatted as pipe-separated key:value pairs (Azure) or pipe-separated tag names (TFE)

## [1.0.5] - 2025-10-03

### Initial Release
- First public release to PyPI
- Core functionality for comparing Azure resources with Terraform Enterprise workspaces
- Support for resource discovery, TFE integration, and coverage analysis
- CSV report generation with UTF-8 BOM encoding
- Caching support for improved performance
- Manual Azure CLI fallback mode
- Dry run capability

[1.0.5]: https://github.com/henrybravo/zephy/releases/tag/v1.0.5
