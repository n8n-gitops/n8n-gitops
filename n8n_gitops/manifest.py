"""Manifest parsing and validation."""

import logging
from dataclasses import dataclass, field
from typing import Any

import yaml

from n8n_gitops.exceptions import ManifestError
from n8n_gitops.gitref import Snapshot

logger = logging.getLogger(__name__)


@dataclass
class WorkflowSpec:
    """Workflow specification from manifest."""
    name: str
    active: bool = False
    tags: list[str] = field(default_factory=list)
    requires_credentials: list[str] = field(default_factory=list)
    requires_env: list[str] = field(default_factory=list)

    @property
    def file(self) -> str:
        """Auto-generate file path from workflow name."""
        from n8n_gitops.commands.export_workflows import _sanitize_filename
        safe_name = _sanitize_filename(self.name)
        return f"workflows/{safe_name}.json"


@dataclass
class Manifest:
    """Parsed manifest containing workflow specifications."""
    workflows: list[WorkflowSpec]
    externalize_code: bool = True
    tags: list[str] = field(default_factory=list)  # List of tag names


def _read_and_parse_yaml(snapshot: Snapshot, manifest_path: str) -> dict[str, Any]:
    """Read and parse manifest YAML file.

    Args:
        snapshot: Snapshot to read from
        manifest_path: Path to manifest file

    Returns:
        Parsed YAML data

    Raises:
        ManifestError: If file cannot be read or parsed
    """
    try:
        manifest_content = snapshot.read_text(manifest_path)
    except Exception as e:
        raise ManifestError(f"Failed to read manifest at {manifest_path}: {e}")

    try:
        data = yaml.safe_load(manifest_content)
    except yaml.YAMLError as e:
        raise ManifestError(f"Failed to parse manifest YAML: {e}")

    if not isinstance(data, dict):
        raise ManifestError("Manifest root must be a dictionary")

    return data


def _parse_externalize_code(data: dict[str, Any]) -> bool:
    """Parse externalize_code field from manifest data.

    Args:
        data: Manifest data dictionary

    Returns:
        externalize_code value (default True)

    Raises:
        ManifestError: If field is invalid
    """
    externalize_code = data.get("externalize_code", True)
    if not isinstance(externalize_code, bool):
        raise ManifestError("'externalize_code' must be a boolean")
    return externalize_code


def _parse_tags(data: dict[str, Any]) -> list[str]:
    """Parse tags field from manifest data.

    Args:
        data: Manifest data dictionary

    Returns:
        List of tag names

    Raises:
        ManifestError: If tags field is invalid
    """
    tags_data = data.get("tags", [])

    if isinstance(tags_data, list):
        if not all(isinstance(t, str) for t in tags_data):
            raise ManifestError("All tags must be strings")
        return tags_data

    raise ManifestError("'tags' must be a list or dictionary")


def _validate_workflow_field_list(
    field_name: str,
    field_value: Any,
    workflow_idx: int,
    workflow_name: str
) -> None:
    """Validate a list field in workflow entry.

    Args:
        field_name: Name of the field
        field_value: Value of the field
        workflow_idx: Index of workflow in list
        workflow_name: Name of workflow

    Raises:
        ManifestError: If field is invalid
    """
    if not isinstance(field_value, list):
        raise ManifestError(
            f"Workflow entry {workflow_idx} ('{workflow_name}'): '{field_name}' must be a list"
        )
    if not all(isinstance(item, str) for item in field_value):
        raise ManifestError(
            f"Workflow entry {workflow_idx} ('{workflow_name}'): all '{field_name}' must be strings"
        )


def _parse_workflow_spec(
    workflow_data: dict[str, Any],
    idx: int,
    seen_names: set[str]
) -> WorkflowSpec:
    """Parse a single workflow specification.

    Args:
        workflow_data: Workflow data dictionary
        idx: Index of workflow in list
        seen_names: Set of workflow names seen so far

    Returns:
        WorkflowSpec object

    Raises:
        ManifestError: If workflow data is invalid
    """
    # Validate name field
    if "name" not in workflow_data:
        raise ManifestError(f"Workflow entry {idx} missing required field 'name'")

    name = workflow_data["name"]
    if not isinstance(name, str) or not name:
        raise ManifestError(f"Workflow entry {idx}: 'name' must be a non-empty string")

    # Check for duplicates
    if name in seen_names:
        raise ManifestError(f"Duplicate workflow name '{name}' found in manifest")
    seen_names.add(name)

    # Parse active field
    active = workflow_data.get("active", False)
    if not isinstance(active, bool):
        raise ManifestError(f"Workflow entry {idx} ('{name}'): 'active' must be a boolean")

    # Parse tags field
    tags = workflow_data.get("tags", [])
    _validate_workflow_field_list("tags", tags, idx, name)

    # Parse requires_credentials field
    requires_credentials = workflow_data.get("requires_credentials", [])
    _validate_workflow_field_list("requires_credentials", requires_credentials, idx, name)

    # Parse requires_env field
    requires_env = workflow_data.get("requires_env", [])
    _validate_workflow_field_list("requires_env", requires_env, idx, name)

    return WorkflowSpec(
        name=name,
        active=active,
        tags=tags,
        requires_credentials=requires_credentials,
        requires_env=requires_env,
    )


def _parse_workflows(data: dict[str, Any]) -> list[WorkflowSpec]:
    """Parse workflows list from manifest data.

    Args:
        data: Manifest data dictionary

    Returns:
        List of WorkflowSpec objects

    Raises:
        ManifestError: If workflows data is invalid
    """
    if "workflows" not in data:
        raise ManifestError("Manifest missing required 'workflows' key")

    workflows_data = data["workflows"]
    if not isinstance(workflows_data, list):
        raise ManifestError("'workflows' must be a list")

    workflows: list[WorkflowSpec] = []
    seen_names: set[str] = set()

    for idx, workflow_data in enumerate(workflows_data):
        if not isinstance(workflow_data, dict):
            raise ManifestError(f"Workflow entry {idx} must be a dictionary")

        spec = _parse_workflow_spec(workflow_data, idx, seen_names)
        workflows.append(spec)

    return workflows


def _validate_workflow_tags(workflows: list[WorkflowSpec], manifest_tags: list[str]) -> None:
    """Validate that all workflow tags reference valid manifest tags.

    Args:
        workflows: List of workflow specs
        manifest_tags: List of valid tag names from manifest

    Raises:
        ManifestError: If a workflow references an undefined tag
    """
    manifest_tag_names = set(manifest_tags)
    for spec in workflows:
        for tag_name in spec.tags:
            if tag_name not in manifest_tag_names:
                raise ManifestError(
                    f"Workflow '{spec.name}' references undefined tag '{tag_name}'. "
                    f"Available tags: {sorted(manifest_tag_names)}"
                )


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

    # Read and parse YAML
    data = _read_and_parse_yaml(snapshot, manifest_path)

    # Parse manifest fields
    externalize_code = _parse_externalize_code(data)
    tags_list = _parse_tags(data)
    workflows = _parse_workflows(data)

    # Validate workflow tags
    _validate_workflow_tags(workflows, tags_list)

    return Manifest(workflows=workflows, externalize_code=externalize_code, tags=tags_list)
