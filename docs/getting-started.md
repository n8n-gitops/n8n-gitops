---
sidebar_position: 1
title: Getting Started
---

# Getting Started

## Installation

### With uv (recommended)

[uv](https://github.com/astral-sh/uv) is the recommended way to install CLI tools — it creates an isolated environment automatically and makes the command available globally for your user without requiring sudo:

```bash
uv tool install n8n-gitops
```

### With pip (user install, no sudo)

```bash
pip install --user n8n-gitops
```

This installs to `~/.local/` and does not require sudo. Make sure `~/.local/bin` is in your `PATH`.

> **Note:** Running `pip install n8n-gitops` without `--user` installs into the system Python and typically requires `sudo`. Prefer `--user` or a virtual environment to avoid that.

### In a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install n8n-gitops
```

### From source

```bash
git clone https://github.com/n8n-gitops/n8n-gitops.git
cd n8n-gitops
pip install -e .
```

For development (includes test and lint tools):

```bash
pip install -e ".[dev]"
# or with uv
uv sync --dev
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
└── README.md
```

### 2. Configure authentication

Save a config profile with your n8n API credentials:

```bash
n8n-gitops configure --config dev \
  --api-url https://your-n8n-instance.com \
  --api-key your-api-key-here
```

Alternatively, use environment variables:
```bash
export N8N_API_URL=https://your-n8n-instance.com
export N8N_API_KEY=your-api-key-here
```

See [Authentication](authentication.md) for more details.

### 3. Export existing workflows

```bash
# Export workflows (uses externalize_code from manifest, default: true)
n8n-gitops export
```

This creates:
- JSON files in `n8n/workflows/`
- Manifest entries in `n8n/manifests/workflows.yaml`
- When `externalize_code` is `true` in `n8n/manifests/workflows.yaml` (default): Script files in `n8n/scripts/` with include directives

To keep code inline, set `externalize_code: false` in `n8n/manifests/workflows.yaml` before running `n8n-gitops export`.

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

1. **Export** existing workflows: `n8n-gitops export`
2. **Commit** to Git: `git add . && git commit -m "Initial export"`
3. **Validate**: `n8n-gitops validate --strict`
4. **Tag** release: `git tag v1.0.0`
5. **Deploy**: `n8n-gitops deploy --git-ref v1.0.0`

## Next Steps

- Learn about [Code Externalization](code-externalization.md)
- Understand the [Manifest File](manifest.md)
- Review all [Commands](commands.md)
- Configure [Authentication](authentication.md)
