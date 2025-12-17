# Commands Reference

Complete reference for all n8n-gitops CLI commands.

## create-project

Create a new n8n-gitops project structure.

### Usage

```bash
n8n-gitops create-project <path>
```

### Arguments

- `<path>` - Path where the project should be created

### Example

```bash
n8n-gitops create-project my-n8n-project
cd my-n8n-project
```

### Output Structure

```
my-n8n-project/
├── n8n/
│   ├── workflows/
│   ├── manifests/
│   │   ├── workflows.yaml
│   │   └── env.schema.json
│   └── scripts/
├── .gitignore
└── .n8n-auth.example
```

See [Getting Started](getting-started.md) for more details.

---

## export

Export all workflows from n8n instance (mirror mode).

### Usage

```bash
n8n-gitops export [--externalize-code] [--api-url URL] [--api-key KEY]
```

### Options

- `--externalize-code` - Extract inline code to separate script files
- `--api-url URL` - n8n API URL (overrides env and .n8n-auth)
- `--api-key KEY` - n8n API key (overrides env and .n8n-auth)
- `--repo-root PATH` - Repository root path (default: current directory)

### Examples

```bash
# Export with inline code
n8n-gitops export

# Export with externalized code
n8n-gitops export --externalize-code

# Export with custom credentials
n8n-gitops export --api-url https://n8n.example.com --api-key abc123
```

### Mirror Mode

The export command always:
- Exports ALL workflows from n8n
- Deletes local workflows not in n8n
- Deletes script files when switching from externalized to inline
- Updates manifest to match remote state

See [Export](export.md) for detailed documentation.

---

## deploy

Deploy workflows to n8n instance.

### Usage

```bash
n8n-gitops deploy [options]
```

### Options

- `--git-ref REF` - Git ref to deploy from (tag, branch, commit)
- `--dry-run` - Show what would be deployed without making changes
- `--backup` - Backup old workflow by renaming before replacing
- `--prune` - Delete workflows in n8n that are not in the manifest
- `--api-url URL` - n8n API URL (overrides env and .n8n-auth)
- `--api-key KEY` - n8n API key (overrides env and .n8n-auth)
- `--repo-root PATH` - Repository root path (default: current directory)

### Examples

```bash
# Deploy from working tree
n8n-gitops deploy

# Deploy from git tag
n8n-gitops deploy --git-ref v1.0.0

# Dry run
n8n-gitops deploy --dry-run

# Deploy with backup
n8n-gitops deploy --backup

# Deploy and prune
n8n-gitops deploy --prune

# Deploy from branch with custom credentials
n8n-gitops deploy --git-ref main \
  --api-url https://n8n.example.com \
  --api-key abc123
```

See [Deployment](deployment.md) for detailed documentation.

---

## rollback

Rollback to a previous version (alias for `deploy --git-ref`).

### Usage

```bash
n8n-gitops rollback --git-ref <ref> [options]
```

### Options

- `--git-ref REF` - Git ref to rollback to (required)
- `--dry-run` - Show what would be deployed without making changes
- `--api-url URL` - n8n API URL (overrides env and .n8n-auth)
- `--api-key KEY` - n8n API key (overrides env and .n8n-auth)
- `--repo-root PATH` - Repository root path (default: current directory)

### Examples

```bash
# Rollback to previous tag
n8n-gitops rollback --git-ref v0.9.0

# Rollback with dry run
n8n-gitops rollback --git-ref v0.9.0 --dry-run
```

### Note

These commands are equivalent:
```bash
n8n-gitops rollback --git-ref v0.9.0
n8n-gitops deploy --git-ref v0.9.0
```

See [Deployment](deployment.md) for more details.

---

## validate

Validate workflows and manifests.

### Usage

```bash
n8n-gitops validate [options]
```

### Options

- `--strict` - Turn warnings into failures
- `--enforce-no-inline-code` - Fail if inline code is found in workflow nodes
- `--enforce-checksum` - Fail on checksum mismatch
- `--require-checksum` - Require checksums in all include directives
- `--git-ref REF` - Git ref to validate from (tag, branch, commit)
- `--repo-root PATH` - Repository root path (default: current directory)

### Examples

```bash
# Basic validation
n8n-gitops validate

# Strict mode
n8n-gitops validate --strict

# Enforce no inline code
n8n-gitops validate --enforce-no-inline-code

# Validate from git tag
n8n-gitops validate --git-ref v1.0.0

# Full validation
n8n-gitops validate --strict --enforce-no-inline-code
```

### What Gets Validated

1. **Manifest**:
   - Valid YAML format
   - Required fields present
   - No duplicate workflow names
   - Referenced files exist

2. **Workflows**:
   - Valid JSON format
   - No problematic fields
   - Include directives are valid
   - Referenced script files exist

3. **Include Directives**:
   - Paths are valid
   - Files exist
   - No path traversal
   - Paths are under `scripts/`
   - Checksums match (if enforced)

4. **Code**:
   - No inline code (if enforced)

### Exit Codes

- `0` - Validation passed
- `1` - Validation failed

### Example Output

```
Validating workflows from /path/to/project
Using git ref: v1.0.0

Loaded manifest: 2 workflow(s)

Validating workflows...
  ✓ Payment Processing
      ✓ Include: scripts/Payment_Processing/validate.py
  ✓ Data Sync

✓ Validation successful!
```

---

## Global Options

These options work with all commands:

### `--repo-root PATH`

Specify the repository root path.

```bash
n8n-gitops export --repo-root /path/to/project
```

Default: current directory (`.`)

### `--version`

Show version and exit.

```bash
n8n-gitops --version
```

### `--help`

Show help message and exit.

```bash
n8n-gitops --help
n8n-gitops export --help
n8n-gitops deploy --help
```

---

## Common Workflows

### Initial Setup

```bash
# 1. Create project
n8n-gitops create-project my-project
cd my-project

# 2. Configure auth
cp .n8n-auth.example .n8n-auth
# Edit .n8n-auth with your credentials

# 3. Export workflows
n8n-gitops export --externalize-code

# 4. Commit to git
git init
git add .
git commit -m "Initial export"
git tag v1.0.0
```

### Making Changes

```bash
# 1. Export latest from n8n
n8n-gitops export --externalize-code

# 2. Make changes to scripts or workflows
vim n8n/scripts/my-workflow/process.py

# 3. Validate changes
n8n-gitops validate --strict

# 4. Commit changes
git add .
git commit -m "Update process logic"
git tag v1.1.0

# 5. Deploy
n8n-gitops deploy --git-ref v1.1.0
```

### Deploying to Production

```bash
# 1. Test in staging first
n8n-gitops deploy --git-ref v1.2.0 --dry-run

# 2. Deploy to production
n8n-gitops deploy --git-ref v1.2.0

# 3. Verify deployment
# Check n8n UI
```

### Rolling Back

```bash
# 1. Check previous tags
git tag

# 2. Rollback to previous version
n8n-gitops rollback --git-ref v1.1.0

# 3. Verify rollback
# Check n8n UI
```

### Syncing with Remote

```bash
# Mirror remote n8n to local
n8n-gitops export --externalize-code

# Review changes
git status
git diff

# Commit if needed
git add .
git commit -m "Sync with remote n8n"
```

---

## Environment Variables

### Authentication

- `N8N_API_URL` - n8n instance URL
- `N8N_API_KEY` - n8n API key

### Example

```bash
export N8N_API_URL=https://n8n.example.com
export N8N_API_KEY=your-api-key

n8n-gitops export
```

See [Authentication](authentication.md) for more details.

---

## Exit Codes

All commands use these exit codes:

- `0` - Success
- `1` - Error
- `130` - Interrupted by user (Ctrl+C)

---

## See Also

- [Getting Started](getting-started.md) - Quick start guide
- [Export](export.md) - Export command details
- [Deployment](deployment.md) - Deploy command details
- [Code Externalization](code-externalization.md) - Include directives
- [Manifest File](manifest.md) - Manifest format
- [Authentication](authentication.md) - Authentication setup
