# Getting Started

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

This creates the following structure:

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

See [Authentication](authentication.md) for more details.

### 3. Export existing workflows

```bash
# Export workflows with inline code
n8n-gitops export

# Export workflows and externalize code to separate files
n8n-gitops export --externalize-code
```

This creates:
- JSON files in `n8n/workflows/`
- Manifest entries in `n8n/manifests/workflows.yaml`
- When using `--externalize-code`: Script files in `n8n/scripts/` with include directives

See [Export](export.md) for more details.

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

See [Deployment](deployment.md) for more details.

## Recommended Workflow

1. **Export** existing workflows: `n8n-gitops export --externalize-code`
2. **Commit** to Git: `git add . && git commit -m "Initial export"`
3. **Validate**: `n8n-gitops validate --strict`
4. **Tag** release: `git tag v1.0.0`
5. **Deploy**: `n8n-gitops deploy --git-ref v1.0.0`

## Next Steps

- Learn about [Code Externalization](code-externalization.md)
- Understand the [Manifest File](manifest.md)
- Review all [Commands](commands.md)
- Configure [Authentication](authentication.md)
