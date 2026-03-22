# Changelog

## [0.3.3] - 2026-03-22

### Changed

- **Upsert deploy strategy** — workflows are now updated in place via PUT instead of deleted and recreated
  - Preserves workflow IDs, webhook URLs, and execution history
  - Archived workflows are automatically detected and fall back to delete+recreate (n8n public API limitation)
  - Removed `--backup` flag (no longer needed with update-in-place)

## [0.3.2] - 2026-03-22

### Added

- **`configure` command** with named config profiles
  - Save multiple n8n instance connections to `.n8n-gitops.yaml`
  - Use `--config <name>` on export, deploy, and rollback commands
  - Supports `--insecure` flag per profile for self-signed certificates

- **`--insecure` flag** for SSL certificate verification
  - Added to export, deploy, and rollback commands
  - Supports n8n instances with self-signed certificates
  - Suppresses urllib3 InsecureRequestWarning when enabled

- **Credential inference** in `credentials.yaml`
  - Detects required credentials from node types and parameters
  - Inferred credentials appear under `_inferred` section
  - Helps users identify what credentials to set up before configuring them
  - Uses `parameters.nodeCredentialType` (primary) and node type (fallback)

### Fixed

- **n8n v2 API compatibility** for deploy command
  - Strip `activeVersion`, `activeVersionId`, `versionCounter`, `description` fields
  - Filter unknown settings fields (e.g., `binaryMode`) rejected by strict API validation
  - Strip `activeVersionId` and `versionCounter` during export

- **Fix `GitSnapshot` import** in validate command
  - Renamed to match `Snapshot` protocol class in `gitref.py`

### Changed

- **Removed `.n8n-auth` file support** in favor of config profiles
  - Authentication now via CLI flags, `--config` profiles, or environment variables
  - `.n8n-gitops.yaml` replaces `.n8n-auth` for persistent credentials
  - Updated project templates, documentation, and tests

- **Refactored CLI argument handling**
  - Shared `_add_api_args` helper for consistent `--config`, `--api-url`, `--api-key`, `--insecure`, `--repo-root` across commands
  - `insecure` flag now part of `AuthConfig` dataclass

## [0.3.1] - 2026-03-20

### Changed

- Migrated to `uv` for faster dependency management
- Added documentation update workflow
- Updated documentation links and restructured assets directory

## [0.3.0] - 2025-12-19

### Changed

#### Tag Management Improvements

- **BREAKING**: Tags in manifest now only support list format
  - Removed backward compatibility for dictionary-based tag format
  - Error message updated to reflect list-only requirement
  - Simplified tag parsing logic in `_parse_tags()`

#### Code Refactoring and Modularity

- **Refactored `deploy` command** for improved modularity and clarity
  - Split monolithic deploy logic into focused functions
  - Improved error handling and validation
  - Enhanced code maintainability

- **Refactored `render` and `validate`** for better separation of concerns
  - Clearer function boundaries
  - Improved testability
  - More consistent error handling

- **Centralized logging utility**
  - Added `logger.py` module for consistent logging across all commands
  - Integrated logger throughout CLI commands
  - Removed redundant logging configurations

#### Workflow and Tag Ordering

- **Deterministic export output**
  - Workflows are now sorted alphabetically in exported manifests
  - Tags are sorted alphabetically for consistent ordering
  - Ensures consistent Git diffs and reduces merge conflicts

#### Code Quality

- Removed unused imports across the codebase
- Improved log message consistency
- Enhanced code organization and readability

### Added

- **Tag management functionality** in manifest handling
- **Centralized logger utility** (`n8n_gitops/logger.py`)
- **Release process documentation** (`docs/release-process.md`)

### Documentation

- Added comprehensive release process guide
- Updated authentication documentation
- Improved code externalization documentation
- Enhanced deployment and command documentation
- Added GitOps principles documentation
- Added comparison with n8n Enterprise Git features
- Restructured documentation with sidebar metadata for better navigation
- Removed redundant documentation files for cleaner structure

### Fixed

- Test suite updated to reflect tag format changes
- Backward compatibility tests now correctly verify rejection of old dict format

---

## [0.2.0] - 2025-12-16

### Added

#### Code Externalization Feature

- **NEW**: `--externalize-code` flag for `export` command
  - Automatically extracts inline code from workflow nodes to separate script files
  - Supports `pythonCode`, `jsCode`, `code`, and `functionCode` fields
  - Generates unique filenames based on workflow and node names
  - Uses appropriate file extensions (.py for Python, .js for JavaScript)
  - Replaces inline code with `@@n8n-gitops:include` directives
  - Automatically generates SHA256 checksums for code integrity verification

#### Features

- **Automatic Code Detection**: Scans workflow nodes for code-bearing parameters
- **Smart File Organization**: Creates workflow-specific directories under `n8n/scripts/`
- **Checksum Generation**: Includes SHA256 checksums in include directives
- **Duplicate Handling**: Automatically resolves filename conflicts with counters
- **Seamless Round-Trip**: Export with externalization → Deploy with include rendering

#### Example Usage

```bash
# Export workflows with code externalization
n8n-gitops export

# Result:
# - Inline code extracted to n8n/scripts/<workflow-name>/<node-name>_<field>.ext
# - Workflow JSON contains @@n8n-gitops:include directives with checksums
# - Deploy command automatically renders includes back to inline code
```

#### Files Modified

- `n8n_gitops/cli.py`: Added `--externalize-code` flag to export command
- `n8n_gitops/commands/export_workflows.py`: Implemented code externalization logic
  - `_externalize_workflow_code()`: Main externalization function
  - `_get_file_extension()`: Determines file extension based on code field type
  - Updated export workflow to conditionally externalize code

#### Documentation

- `README.md`: Updated with code externalization documentation
- `EXTERNALIZATION_GUIDE.md`: Comprehensive guide for code externalization feature
  - Quick start guide
  - Example transformations
  - Best practices
  - Troubleshooting tips
  - Migration guide

### How It Works

1. **Export**: When `--externalize-code` is used:
   ```python
   # Before (inline code in JSON)
   "parameters": {
     "jsCode": "console.log('hello');"
   }

   # After (include directive)
   "parameters": {
     "jsCode": "@@n8n-gitops:include scripts/MyWorkflow/Node.js"
   }
   ```

2. **Script Files Created**:
   ```
   n8n/scripts/
   └── MyWorkflow/
       └── Node.js  # Contains: console.log('hello');
   ```

3. **Deploy**: Existing render engine automatically handles includes:
   - Reads script files from `n8n/scripts/`
   - Verifies checksums (if `--enforce-checksum`)
   - Replaces directives with file contents
   - Deploys to n8n with code inline

### Benefits

- ✅ **Better Version Control**: Code changes visible in Git diffs
- ✅ **IDE Support**: Use syntax highlighting, linting, autocomplete
- ✅ **Code Organization**: Separate code from workflow structure
- ✅ **Code Reuse**: Share code between workflows
- ✅ **Testing**: Test code independently
- ✅ **Collaboration**: Review code in pull requests
- ✅ **Integrity**: SHA256 checksums verify code hasn't been tampered with

### Testing

- All 40 existing unit tests pass
- Manual testing confirms round-trip works correctly:
  - Export with `--externalize-code`
  - Code extracted to separate files
  - Deploy renders includes correctly
  - Deployed code matches original inline code

---

## [0.1.0] - 2025-12-16

### Added

Initial release with complete implementation of n8n-gitops according to plan.md:

- CLI with argparse-based command structure
- `create-project` command for scaffolding new projects
- `export` command for exporting workflows from n8n
- `validate` command for workflow and manifest validation
- `deploy` command for deploying workflows to n8n
- `rollback` command for rolling back to previous versions
- Authentication via CLI flags, environment variables, or `.n8n-auth` file
- Git ref snapshot reader for deploying from Git history
- Manifest parsing and validation
- JSON normalization for deterministic output
- Code include directive support (`@@n8n-gitops:include`)
- n8n API client with retry logic
- Environment schema validation
- Comprehensive test suite (40 tests)
- Documentation and examples
