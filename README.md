# n8n-gitops

GitOps CLI for n8n Community Edition - Manage your n8n workflows as code with Git version control.

## Features

- 🔄 **Mirror Mode Export**: Always keeps local repository in perfect sync with n8n
- 📦 **Code Externalization**: Store Python/JavaScript code in separate files
- 🔑 **Credential Documentation**: Auto-generate documentation of workflow credential dependencies
- 🏷️ **Git-Based Deployment**: Deploy specific tags/branches/commits
- ✅ **Validation**: Validate workflows and manifests before deployment
- 🔌 **Active State Management**: Control workflow activation via API endpoints
- 🧹 **Clean Deployments**: Replace workflows with clean state

![Logo](n8n-gitops-256.png)

## Quick Start

```bash
# Install
pip install -e .

# Create project
n8n-gitops create-project my-n8n-project
cd my-n8n-project

# Configure authentication
cp .n8n-auth.example .n8n-auth
# Edit .n8n-auth with your credentials

# Export workflows
n8n-gitops export

# Commit to Git
git init
git add .
git commit -m "Initial export"
git tag v1.0.0

# Deploy
n8n-gitops deploy --git-ref v1.0.0
```

## Documentation

📚 **[Full Documentation](docs/)**

### Core Guides

- **[Getting Started](docs/getting-started.md)** - Installation and quick start
- **[Authentication](docs/authentication.md)** - Configure API credentials
- **[Export](docs/export.md)** - Mirror workflows from n8n
- **[Deployment](docs/deployment.md)** - Deploy workflows to n8n
- **[Code Externalization](docs/code-externalization.md)** - Store code in separate files
- **[Manifest File](docs/manifest.md)** - Workflow configuration format
- **[n8n Enterprise Git Comparison](docs/vs-n8n-enterprise-git.md)** - Decide between n8n-gitops and Enterprise Git
- **[Commands Reference](docs/commands.md)** - All CLI commands
- **[GitOps Principles](docs/gitops.md)** - How n8n-gitops aligns with GitOps principles

## Key Concepts

### Mirror Mode

Export always mirrors your n8n instance:

```bash
n8n-gitops export
```

- ✅ Exports ALL workflows
- 🗑️ Deletes local workflows not in n8n
- 🗑️ Deletes orphaned script files
- 📝 Updates manifest to match remote

### Code Externalization

Store code in separate files instead of inline JSON (controlled by `externalize_code` in `n8n/manifests/workflows.yaml`, default: `true`):

**Workflow JSON:**
```json
{
  "parameters": {
    "pythonCode": "@@n8n-gitops:include scripts/my-workflow/process.py"
  }
}
```

**Script File:**
```python
def process(data):
    return data.upper()

result = process(input)
```

### Git-Based Deployment

Deploy from any Git reference:

```bash
# Deploy from tag
n8n-gitops deploy --git-ref v1.0.0

# Deploy from branch
n8n-gitops deploy --git-ref main

# Deploy from commit
n8n-gitops deploy --git-ref abc123
```

## Commands

```bash
# Create project structure
n8n-gitops create-project <path>

# Export workflows (mirror mode)
n8n-gitops export

# Validate workflows
n8n-gitops validate [--strict]

# Deploy workflows
n8n-gitops deploy [--git-ref REF] [--dry-run] [--backup] [--prune]

# Rollback to previous version
n8n-gitops rollback --git-ref <ref>
```

See [Commands Reference](docs/commands.md) for complete documentation.

## Example Workflow

```bash
# 1. Export from n8n
n8n-gitops export

# 2. Edit scripts
vim n8n/scripts/payment-processing/validate.py

# 3. Validate changes
n8n-gitops validate --strict

# 4. Commit to Git
git add .
git commit -m "Improve payment validation"
git tag v1.1.0

# 5. Deploy
n8n-gitops deploy --git-ref v1.1.0
```

## Project Structure

```
my-n8n-project/
├── n8n/
│   ├── workflows/           # Workflow JSON files
│   ├── scripts/             # Externalized code
│   │   └── my-workflow/
│   │       ├── process.py
│   │       └── transform.js
│   ├── credentials.yaml     # Credential documentation (auto-generated)
│   └── manifests/
│       ├── workflows.yaml   # Workflow manifest
│       └── env.schema.json  # Environment schema
├── .gitignore
└── .n8n-auth.example        # Auth config template
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
source venv/bin/activate
pytest -v
```

## Requirements

- Python 3.8+
- Git
- n8n instance with API access

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
