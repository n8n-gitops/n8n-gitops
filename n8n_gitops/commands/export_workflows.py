"""Export command implementation."""

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from n8n_gitops.config import load_auth
from n8n_gitops.gitref import WorkingTreeSnapshot
from n8n_gitops.manifest import load_manifest
from n8n_gitops.n8n_client import N8nClient
from n8n_gitops.normalize import normalize_json, strip_volatile_fields
from n8n_gitops.render import CODE_FIELD_NAMES


def run_export(args: argparse.Namespace) -> None:
    """Export workflows from n8n instance.

    Args:
        args: CLI arguments

    Raises:
        SystemExit: If export fails
    """
    repo_root = Path(args.repo_root).resolve()
    n8n_root = repo_root / "n8n"
    workflows_dir = n8n_root / "workflows"
    manifests_dir = n8n_root / "manifests"
    scripts_dir = n8n_root / "scripts"
    manifest_file = manifests_dir / "workflows.yaml"

    # Ensure directories exist
    workflows_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    # Load manifest to get externalize_code setting
    # If manifest doesn't exist yet, use default (True)
    externalize_code = True
    try:
        snapshot = WorkingTreeSnapshot(repo_root)
        manifest = load_manifest(snapshot, "n8n")
        externalize_code = manifest.externalize_code
    except Exception:
        # If manifest doesn't exist or can't be loaded, use default
        externalize_code = True

    # Load auth config
    try:
        auth = load_auth(repo_root, args)
    except Exception as e:
        print(f"Error: {e}")
        raise SystemExit(1)

    print(f"Exporting workflows from {auth.api_url}")
    print(f"Target directory: {workflows_dir}")
    print()

    # Initialize client
    client = N8nClient(auth.api_url, auth.api_key)

    # Fetch all tags first
    print("Fetching tags...")
    tags_mapping: dict[str, str] = {}  # Maps tag ID to tag name
    try:
        remote_tags = client.list_tags()
        print(f"Found {len(remote_tags)} tag(s)")

        # Build tags mapping from all tags in n8n
        for tag in remote_tags:
            tag_id = tag.get("id")
            tag_name = tag.get("name")
            if tag_id and tag_name:
                tags_mapping[str(tag_id)] = str(tag_name)
    except Exception as e:
        print(f"Warning: Could not fetch tags: {e}")
        # Continue without tags

    # Fetch workflows
    print("Fetching workflows...")
    try:
        remote_workflows = client.list_workflows()
        print(f"Found {len(remote_workflows)} workflow(s)")
    except Exception as e:
        print(f"Error fetching workflows: {e}")
        raise SystemExit(1)

    if not remote_workflows:
        print("No workflows found to export")
        raise SystemExit(0)

    # Always export all workflows (mirror mode)
    workflows_to_export = remote_workflows

    print(f"\nExporting {len(workflows_to_export)} workflow(s) (mirror mode)...")
    if externalize_code:
        print("Code externalization: ENABLED (set in manifest)")
    else:
        print("Code externalization: DISABLED (set in manifest)")

    # Clean workflows directory - delete all JSON files for true mirror mode
    print("\nCleaning workflows directory...")
    if workflows_dir.exists():
        deleted_count = 0
        for workflow_file in workflows_dir.glob("*.json"):
            workflow_file.unlink()
            deleted_count += 1
        if deleted_count > 0:
            print(f"  🗑  Deleted {deleted_count} existing workflow file(s)")

    # Clean scripts directory - delete all script directories for fresh export
    print("Cleaning scripts directory...")
    if scripts_dir.exists():
        deleted_count = 0
        for script_dir in scripts_dir.iterdir():
            if script_dir.is_dir():
                shutil.rmtree(script_dir)
                deleted_count += 1
        if deleted_count > 0:
            print(f"  🗑  Deleted {deleted_count} existing script director{'y' if deleted_count == 1 else 'ies'}")

    # Export each workflow
    exported_specs: list[dict[str, Any]] = []
    total_externalized = 0

    # Track credentials: {type: {name: [workflow_names]}}
    credentials_map: dict[str, dict[str, list[str]]] = {}

    for wf_summary in workflows_to_export:
        wf_id = wf_summary.get("id")
        wf_name = wf_summary.get("name")

        if not wf_id or not wf_name:
            print(f"  ⚠ Skipping workflow with missing id or name")
            continue

        print(f"  Exporting: {wf_name}")

        # Fetch full workflow
        try:
            workflow = client.get_workflow(wf_id)
        except Exception as e:
            print(f"    ✗ Error fetching workflow: {e}")
            continue

        # Extract credentials from workflow
        workflow_credentials = _extract_credentials(workflow)
        for cred in workflow_credentials:
            cred_type = cred["type"]
            cred_name = cred["name"]

            # Initialize type dict if not exists
            if cred_type not in credentials_map:
                credentials_map[cred_type] = {}

            # Initialize name list if not exists
            if cred_name not in credentials_map[cred_type]:
                credentials_map[cred_type][cred_name] = []

            # Add workflow name if not already in list
            if wf_name not in credentials_map[cred_type][cred_name]:
                credentials_map[cred_type][cred_name].append(wf_name)

        # Strip volatile and n8n-managed fields to ensure clean exports
        # These fields are auto-generated by n8n and cause API validation errors
        # Note: 'active' is kept in the workflow JSON for reference,
        # but stripped during deployment (it's also in the manifest)
        workflow_cleaned = strip_volatile_fields(
            workflow,
            fields=[
                "id",
                "createdAt",
                "updatedAt",
                "versionId",
                "shared",
                "isArchived",
                "triggerCount",
            ],
        )

        # Externalize code based on manifest setting
        if externalize_code:
            workflow_cleaned, externalized_count = _externalize_workflow_code(
                workflow_cleaned,
                wf_name,
                scripts_dir,
            )
            total_externalized += externalized_count
            if externalized_count > 0:
                print(f"    ✓ Externalized {externalized_count} code block(s)")

        # Normalize JSON
        normalized_json = normalize_json(workflow_cleaned)

        # Determine filename (sanitize name)
        safe_name = _sanitize_filename(wf_name)
        filename = f"{safe_name}.json"
        filepath = workflows_dir / filename

        # Write file
        try:
            filepath.write_text(normalized_json)
            print(f"    ✓ Saved to: n8n/workflows/{filename}")
        except Exception as e:
            print(f"    ✗ Error writing file: {e}")
            continue

        # Extract tag IDs from workflow (tags are already in tags_mapping)
        workflow_tags = workflow.get("tags", [])
        tag_ids: list[str] = []

        for tag in workflow_tags:
            if isinstance(tag, dict):
                tag_id = tag.get("id")
                if tag_id:
                    tag_ids.append(str(tag_id))

        # Add to manifest
        exported_specs.append(
            {
                "name": wf_name,
                "active": workflow.get("active", False),
                "tags": tag_ids,
            }
        )

    # Write credentials.yaml
    if credentials_map:
        print("\nGenerating credentials documentation...")
        credentials_yaml_path = n8n_root / "credentials.yaml"

        # Transform credentials_map to desired YAML structure
        # Format: {type: [{name: str, workflows: [str]}]}
        credentials_output: dict[str, list[dict[str, Any]]] = {}

        for cred_type in sorted(credentials_map.keys()):
            credentials_output[cred_type] = []
            for cred_name in sorted(credentials_map[cred_type].keys()):
                workflows_list = sorted(credentials_map[cred_type][cred_name])
                credentials_output[cred_type].append({
                    "name": cred_name,
                    "workflows": workflows_list
                })

        # Write YAML file
        try:
            credentials_yaml_content = yaml.dump(
                credentials_output,
                default_flow_style=False,
                sort_keys=False,
            )
            credentials_yaml_path.write_text(credentials_yaml_content)
            total_creds = sum(len(creds) for creds in credentials_output.values())
            print(f"  ✓ Documented {total_creds} credential(s) in {credentials_yaml_path.relative_to(repo_root)}")
        except Exception as e:
            print(f"  ✗ Error writing credentials.yaml: {e}")

    # Update manifest (always in mirror mode)
    if exported_specs:
        print("\nUpdating manifest...")

        # Replace manifest completely with exported workflows (mirror mode)
        # This ensures deleted workflows are removed from manifest
        existing_specs = exported_specs

        # Write manifest (preserve externalize_code setting, include tags mapping)
        manifest_content = yaml.dump(
            {
                "externalize_code": externalize_code,
                "tags": tags_mapping,
                "workflows": existing_specs
            },
            default_flow_style=False,
            sort_keys=False,
        )
        try:
            manifest_file.write_text(manifest_content)
            print(f"  ✓ Updated manifest: {manifest_file.relative_to(repo_root)}")
        except Exception as e:
            print(f"  ✗ Error writing manifest: {e}")

    print(f"\n✓ Export complete! Exported {len(exported_specs)} workflow(s)")
    if total_externalized > 0:
        print(f"✓ Externalized {total_externalized} code block(s) to script files")
    print("\nNext steps:")
    print("  1. Review the exported workflows")
    if total_externalized > 0:
        print("  2. Review the externalized scripts in n8n/scripts/")
        print("  3. git add n8n/")
        print("  4. git commit -m 'Export workflows from n8n with externalized code'")
    else:
        print("  2. git add n8n/")
        print("  3. git commit -m 'Export workflows from n8n'")


def _sanitize_filename(name: str) -> str:
    """Sanitize workflow name for use as filename.

    Args:
        name: Workflow name

    Returns:
        Sanitized filename (without extension)
    """
    # Replace spaces and special characters with underscores
    safe = re.sub(r"[^\w\-.]", "_", name)
    # Remove multiple underscores
    safe = re.sub(r"_+", "_", safe)
    # Remove leading/trailing underscores
    safe = safe.strip("_")
    return safe or "workflow"


def _extract_credentials(workflow: dict[str, Any]) -> list[dict[str, str]]:
    """Extract credential references from workflow.

    Args:
        workflow: Workflow JSON object

    Returns:
        List of dicts with 'type' and 'name' keys
    """
    credentials = []
    for node in workflow.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_creds = node.get("credentials", {})
        if not isinstance(node_creds, dict):
            continue
        for cred_type, cred_data in node_creds.items():
            if isinstance(cred_data, dict) and "name" in cred_data:
                credentials.append({
                    "type": cred_type,
                    "name": cred_data["name"]
                })
    return credentials


def _get_file_extension(field_name: str) -> str:
    """Get appropriate file extension for code field.

    Args:
        field_name: Name of the code field

    Returns:
        File extension (e.g., ".py", ".js")
    """
    if field_name == "pythonCode":
        return ".py"
    elif field_name in ("jsCode", "code", "functionCode"):
        return ".js"
    else:
        return ".txt"


def _externalize_workflow_code(
    workflow: dict[str, Any],
    workflow_name: str,
    scripts_dir: Path,
) -> tuple[dict[str, Any], int]:
    """Externalize inline code from workflow nodes.

    Args:
        workflow: Workflow JSON object
        workflow_name: Name of the workflow
        scripts_dir: Directory to save script files

    Returns:
        Tuple of (modified_workflow, count_of_externalized_code_blocks)
    """
    import copy
    modified = copy.deepcopy(workflow)
    externalized_count = 0

    # Create workflow-specific scripts directory
    safe_workflow_name = _sanitize_filename(workflow_name)
    workflow_scripts_dir = scripts_dir / safe_workflow_name
    workflow_scripts_dir.mkdir(parents=True, exist_ok=True)

    nodes = modified.get("nodes", [])
    if not isinstance(nodes, list):
        return modified, 0

    for node in nodes:
        if not isinstance(node, dict):
            continue

        node_name = node.get("name", "unnamed")
        node_id = node.get("id", "no-id")
        parameters = node.get("parameters", {})

        if not isinstance(parameters, dict):
            continue

        # Check each code field
        for field_name in CODE_FIELD_NAMES:
            if field_name not in parameters:
                continue

            code_value = parameters[field_name]
            if not isinstance(code_value, str) or not code_value.strip():
                continue

            # Check if it's already an include directive
            if code_value.strip().startswith("@@n8n-gitops:include"):
                continue

            # Externalize this code
            safe_node_name = _sanitize_filename(node_name)
            extension = _get_file_extension(field_name)

            # Create filename: node-name.ext
            # Overwrite if it already exists (no counter)
            base_filename = f"{safe_node_name}{extension}"
            script_path = workflow_scripts_dir / base_filename

            # Write code to file (overwrite if exists)
            script_path.write_text(code_value)

            # Create include directive
            # Path relative to n8n/ directory
            relative_path = f"scripts/{safe_workflow_name}/{base_filename}"
            include_directive = f"@@n8n-gitops:include {relative_path}"

            # Replace inline code with directive
            parameters[field_name] = include_directive
            externalized_count += 1

            print(f"      → Externalized {field_name} from node '{node_name}' to {relative_path}")

    return modified, externalized_count
