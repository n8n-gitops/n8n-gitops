# n8n-gitops

GitOps CLI for n8n Community Edition - Manage your n8n workflows as code with Git version control.

## Features

- **GitOps Workflow**: Manage n8n workflows in Git repositories
- **Code Externalization**: Store Python/JavaScript code in separate files with include directives
- **Version Control**: Deploy specific Git tags/branches/commits
- **Validation**: Validate workflows and manifests before deployment
- **Checksum Verification**: Optional SHA256 checksums for included code files
- **Dry Run**: Preview deployments without making changes
- **Workflow Export**: Bootstrap your GitOps workflow by exporting existing workflows

## Installation

```bash
pip install -e .
```

Or for development:

```bash
pip install -e ".[dev]"
```

## Quick Start

### 1. Create a new project

```bash
n8n-gitops create-project my-n8n-project
cd my-n8n-project
```

### 2. Configure authentication

Copy the example auth file and add your n8n API credentials:

```bash
cp .n8n-auth.example .n8n-auth
```

Edit `.n8n-auth`:
```
N8N_API_URL=https://your-n8n-instance.com
N8N_API_KEY=your-api-key-here
```

Alternatively, use environment variables:
```bash
export N8N_API_URL=https://your-n8n-instance.com
export N8N_API_KEY=your-api-key-here
```

### 3. Export existing workflows

```bash
n8n-gitops export --all
```

This creates:
- JSON files in `n8n/workflows/`
- Manifest entries in `n8n/manifests/workflows.yaml`

### 4. Commit to Git

```bash
git init
git add .
git commit -m "Initial workflow export"
git tag v1.0.0
```

### 5. Deploy workflows

Deploy from working tree:
```bash
n8n-gitops deploy
```

Deploy from a specific Git tag:
```bash
n8n-gitops deploy --git-ref v1.0.0
```

Dry run to preview changes:
```bash
n8n-gitops deploy --dry-run
```

## Commands

### create-project

Create a new n8n-gitops project structure:

```bash
n8n-gitops create-project <path>
```

### export

Export workflows from your n8n instance:

```bash
# Export all workflows
n8n-gitops export --all

# Export specific workflows
n8n-gitops export --names "Workflow A,Workflow B"

# Export workflows listed in manifest
n8n-gitops export --from-manifest
```

### validate

Validate workflows and manifests:

```bash
# Basic validation
n8n-gitops validate

# Strict mode (warnings become errors)
n8n-gitops validate --strict

# Enforce no inline code (all code must use includes)
n8n-gitops validate --enforce-no-inline-code

# Require checksums for all includes
n8n-gitops validate --require-checksum

# Validate from a git ref
n8n-gitops validate --git-ref v1.0.0
```

### deploy

Deploy workflows to your n8n instance:

```bash
# Deploy from working tree
n8n-gitops deploy

# Deploy from git tag
n8n-gitops deploy --git-ref v1.0.0

# Dry run (preview without changes)
n8n-gitops deploy --dry-run
```

### rollback

Rollback to a previous version:

```bash
n8n-gitops rollback --git-ref v0.9.0
```

This is equivalent to `deploy --git-ref v0.9.0`.

## Code Externalization

Store Python/JavaScript code in separate files instead of inline in workflow JSON.

### Directory Structure

```
my-n8n-project/
├── n8n/
│   ├── workflows/
│   │   └── my-workflow.json
│   ├── manifests/
│   │   ├── workflows.yaml
│   │   └── env.schema.json
│   └── scripts/
│       ├── payments/
│       │   └── retry.py
│       └── utilities/
│           └── format.js
```

### Include Directive Syntax

In your workflow JSON, replace code with an include directive:

**Basic include:**
```
@@n8n-gitops:include scripts/payments/retry.py
```

**Include with checksum:**
```
@@n8n-gitops:include scripts/payments/retry.py sha256=a1b2c3d4e5f6...
```

### Example Workflow Node

In `n8n/workflows/my-workflow.json`:

```json
{
  "nodes": [
    {
      "name": "Process Payment",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "pythonCode": "@@n8n-gitops:include scripts/payments/retry.py sha256=abc123..."
      }
    }
  ]
}
```

In `n8n/scripts/payments/retry.py`:

```python
def retry_payment(transaction_id):
    # Your payment retry logic here
    return {"status": "retried", "id": transaction_id}

# Main execution
result = retry_payment(items[0].json.transaction_id)
return result
```

### Generating Checksums

```bash
sha256sum n8n/scripts/payments/retry.py | cut -d' ' -f1
```

## Manifest File

The manifest file `n8n/manifests/workflows.yaml` defines which workflows to deploy:

```yaml
workflows:
  - name: "Payment Processing"
    file: "workflows/payment-processing.json"
    active: true
    tags:
      - production
      - payments
    requires_credentials:
      - stripe-api
    requires_env:
      - STRIPE_WEBHOOK_SECRET

  - name: "Data Sync"
    file: "workflows/data-sync.json"
    active: false
```

## Authentication

Authentication credentials are resolved in this priority order:

1. **CLI flags**: `--api-url` and `--api-key`
2. **Environment variables**: `N8N_API_URL` and `N8N_API_KEY`
3. **`.n8n-auth` file** in repository root

## Git Ref Deployment

Deploy workflows from any Git reference without checking it out:

```bash
# Deploy from a tag
n8n-gitops deploy --git-ref v1.0.0

# Deploy from a branch
n8n-gitops deploy --git-ref main

# Deploy from a commit
n8n-gitops deploy --git-ref abc123def
```

This reads workflow files, scripts, and manifests directly from Git history using `git show`.

## Recommended Workflow

1. **Export** existing workflows: `n8n-gitops export --all`
2. **Commit** to Git: `git add . && git commit -m "Initial export"`
3. **Externalize** code (optional): Replace inline code with include directives
4. **Validate**: `n8n-gitops validate --strict`
5. **Tag** release: `git tag v1.0.0`
6. **Deploy**: `n8n-gitops deploy --git-ref v1.0.0`

## Development

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

## Project Structure

```
n8n-gitops/
├── n8n_gitops/
│   ├── __init__.py
│   ├── cli.py              # CLI entrypoint
│   ├── config.py           # Configuration and auth
│   ├── gitref.py           # Git ref snapshot reader
│   ├── manifest.py         # Manifest parsing
│   ├── normalize.py        # JSON normalization
│   ├── render.py           # Code include rendering
│   ├── n8n_client.py       # n8n API client
│   ├── envschema.py        # Environment validation
│   ├── exceptions.py       # Custom exceptions
│   └── commands/
│       ├── create_project.py
│       ├── export_workflows.py
│       ├── validate.py
│       ├── deploy.py
│       └── rollback.py
├── pyproject.toml
└── README.md
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
