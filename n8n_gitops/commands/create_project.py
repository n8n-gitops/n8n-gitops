"""Create project structure command."""

import argparse
from pathlib import Path

from n8n_gitops import logger


def run_create_project(args: argparse.Namespace) -> None:
    """Create a new n8n-gitops project structure.

    Args:
        args: CLI arguments containing the path
    """
    project_path = Path(args.path).resolve()

    if project_path.exists() and any(project_path.iterdir()):
        raise ValueError(f"Directory {project_path} already exists and is not empty")

    # Create directory structure
    project_path.mkdir(parents=True, exist_ok=True)
    n8n_dir = project_path / "n8n"
    workflows_dir = n8n_dir / "workflows"
    manifests_dir = n8n_dir / "manifests"
    scripts_dir = n8n_dir / "scripts"

    workflows_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    # Create .gitignore
    gitignore_content = """.n8n-gitops.yaml
.env
__pycache__/
*.pyc
"""
    (project_path / ".gitignore").write_text(gitignore_content)

    # Create n8n/manifests/workflows.yaml
    workflows_yaml_content = """# Code externalization setting
# When true, code is extracted to separate files in n8n/scripts/
# When false, code remains inline in workflow JSON
externalize_code: true

# Tag ID to name mapping
tags: {}

workflows: []
"""
    (manifests_dir / "workflows.yaml").write_text(workflows_yaml_content)

    # Create n8n/manifests/env.schema.json
    env_schema_content = """{
  "required": ["N8N_API_URL", "N8N_API_KEY"],
  "vars": {}
}
"""
    (manifests_dir / "env.schema.json").write_text(env_schema_content)

    # Create README.md
    readme_content = """# n8n-gitops Project

This project uses [n8n-gitops](https://github.com/n8n-gitops/n8n-gitops) to manage n8n workflows as code.

## Getting Started

1. Configure your n8n API credentials:
   ```bash
   n8n-gitops configure --config dev --api-url https://your-n8n.example.com --api-key YOUR_KEY
   ```

2. Export your existing workflows from n8n:
   ```bash
   n8n-gitops export
   ```

3. Commit your workflows to git:
   ```bash
   git add .
   git commit -m "Initial workflow export"
   ```

4. Deploy workflows from git:
   ```bash
   n8n-gitops deploy
   ```

## Project Structure

```
.
├── n8n/
│   ├── workflows/       # Workflow JSON files
│   ├── manifests/       # Workflow metadata and environment schema
│   │   ├── workflows.yaml
│   │   └── env.schema.json
│   └── scripts/         # External code for workflow nodes
├── .gitignore
└── README.md
```

## Authentication

You can provide n8n API credentials in three ways (in order of priority):

1. CLI flags: `--api-url` and `--api-key`
2. Config profiles: `--config <name>` (saved via `n8n-gitops configure`)
3. Environment variables: `N8N_API_URL` and `N8N_API_KEY`

## Commands

- `n8n-gitops create-project <path>` - Create a new project structure
- `n8n-gitops export` - Export workflows from n8n
- `n8n-gitops validate` - Validate workflows and manifests
- `n8n-gitops deploy` - Deploy workflows to n8n
- `n8n-gitops rollback --git-ref <ref>` - Rollback to a specific git ref

## Code Externalization

You can externalize code from Code nodes using include directives:

```
@@n8n-gitops:include scripts/payments/retry.py sha256=<64-hex>
```

This directive will be replaced with the contents of the file during deployment.
"""
    (project_path / "README.md").write_text(readme_content)

    logger.info(f"Created n8n-gitops project at {project_path}")
    logger.info("\nNext steps:")
    logger.info(f"  1. cd {project_path}")
    logger.info("  2. n8n-gitops configure --config dev --api-url URL --api-key KEY")
    logger.info("  3. n8n-gitops export --config dev")
