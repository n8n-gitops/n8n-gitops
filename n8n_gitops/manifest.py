"""Manifest parsing and validation."""

from dataclasses import dataclass, field
from typing import Any

import yaml

from n8n_gitops.exceptions import ManifestError
from n8n_gitops.gitref import Snapshot


@dataclass
class WorkflowSpec:
    """Workflow specification from manifest."""
    name: str
    file: str
    active: bool = False
    tags: list[str] = field(default_factory=list)
    requires_credentials: list[str] = field(default_factory=list)
    requires_env: list[str] = field(default_factory=list)


@dataclass
class Manifest:
    """Parsed manifest containing workflow specifications."""
    workflows: list[WorkflowSpec]
    externalize_code: bool = True


def load_manifest(snapshot: Snapshot, n8n_root: str = "n8n") -> Manifest:
    """Load and validate manifest from snapshot.

    Args:
        snapshot: Snapshot to read from
        n8n_root: Path to n8n directory (default: "n8n")

    Returns:
        Parsed and validated Manifest

    Raises:
        ManifestError: If manifest is invalid or cannot be loaded
    """
    manifest_path = f"{n8n_root}/manifests/workflows.yaml"

    # Read manifest file
    try:
        manifest_content = snapshot.read_text(manifest_path)
    except Exception as e:
        raise ManifestError(f"Failed to read manifest at {manifest_path}: {e}")

    # Parse YAML
    try:
        data = yaml.safe_load(manifest_content)
    except yaml.YAMLError as e:
        raise ManifestError(f"Failed to parse manifest YAML: {e}")

    if not isinstance(data, dict):
        raise ManifestError("Manifest root must be a dictionary")

    # Parse externalize_code (optional, default True)
    externalize_code = data.get("externalize_code", True)
    if not isinstance(externalize_code, bool):
        raise ManifestError("'externalize_code' must be a boolean")

    # Check for workflows key
    if "workflows" not in data:
        raise ManifestError("Manifest missing required 'workflows' key")

    workflows_data = data["workflows"]
    if not isinstance(workflows_data, list):
        raise ManifestError("'workflows' must be a list")

    # Parse workflow specs
    workflows: list[WorkflowSpec] = []
    seen_names: set[str] = set()

    for idx, workflow_data in enumerate(workflows_data):
        if not isinstance(workflow_data, dict):
            raise ManifestError(f"Workflow entry {idx} must be a dictionary")

        # Validate required fields
        if "name" not in workflow_data:
            raise ManifestError(f"Workflow entry {idx} missing required field 'name'")
        if "file" not in workflow_data:
            raise ManifestError(f"Workflow entry {idx} missing required field 'file'")

        name = workflow_data["name"]
        file_path = workflow_data["file"]

        if not isinstance(name, str) or not name:
            raise ManifestError(f"Workflow entry {idx}: 'name' must be a non-empty string")
        if not isinstance(file_path, str) or not file_path:
            raise ManifestError(f"Workflow entry {idx}: 'file' must be a non-empty string")

        # Check for duplicate names
        if name in seen_names:
            raise ManifestError(f"Duplicate workflow name '{name}' found in manifest")
        seen_names.add(name)

        # Parse optional fields
        active = workflow_data.get("active", False)
        if not isinstance(active, bool):
            raise ManifestError(
                f"Workflow entry {idx} ('{name}'): 'active' must be a boolean"
            )

        tags = workflow_data.get("tags", [])
        if not isinstance(tags, list):
            raise ManifestError(
                f"Workflow entry {idx} ('{name}'): 'tags' must be a list"
            )
        if not all(isinstance(t, str) for t in tags):
            raise ManifestError(
                f"Workflow entry {idx} ('{name}'): all 'tags' must be strings"
            )

        requires_credentials = workflow_data.get("requires_credentials", [])
        if not isinstance(requires_credentials, list):
            raise ManifestError(
                f"Workflow entry {idx} ('{name}'): 'requires_credentials' must be a list"
            )
        if not all(isinstance(c, str) for c in requires_credentials):
            raise ManifestError(
                f"Workflow entry {idx} ('{name}'): all 'requires_credentials' must be strings"
            )

        requires_env = workflow_data.get("requires_env", [])
        if not isinstance(requires_env, list):
            raise ManifestError(
                f"Workflow entry {idx} ('{name}'): 'requires_env' must be a list"
            )
        if not all(isinstance(e, str) for e in requires_env):
            raise ManifestError(
                f"Workflow entry {idx} ('{name}'): all 'requires_env' must be strings"
            )

        workflows.append(
            WorkflowSpec(
                name=name,
                file=file_path,
                active=active,
                tags=tags,
                requires_credentials=requires_credentials,
                requires_env=requires_env,
            )
        )

    return Manifest(workflows=workflows, externalize_code=externalize_code)
