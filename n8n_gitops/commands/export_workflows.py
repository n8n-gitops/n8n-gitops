"""Export command implementation."""

import argparse
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from n8n_gitops import logger
from n8n_gitops.config import load_auth
from n8n_gitops.gitref import WorkingTreeSnapshot
from n8n_gitops.manifest import load_manifest
from n8n_gitops.n8n_client import N8nClient
from n8n_gitops.normalize import normalize_json, strip_volatile_fields
from n8n_gitops.render import CODE_FIELD_NAMES


def _load_externalize_code_setting(repo_root: Path) -> bool:
    """Load externalize_code setting from manifest.

    Args:
        repo_root: Repository root path

    Returns:
        True if code should be externalized, False otherwise
    """
    try:
        snapshot = WorkingTreeSnapshot(repo_root)
        manifest = load_manifest(snapshot, "n8n")
        return manifest.externalize_code
    except Exception:
        return True


def _fetch_tags_mapping(client: N8nClient) -> dict[str, str]:
    """Fetch tags from n8n and build ID to name mapping.

    Args:
        client: N8n API client

    Returns:
        Dictionary mapping tag IDs to tag names
    """
    logger.info("Fetching tags...")
    tags_mapping: dict[str, str] = {}
    try:
        remote_tags = client.list_tags()
        logger.info(f"Found {len(remote_tags)} tag(s)")
        for tag in remote_tags:
            tag_id = tag.get("id")
            tag_name = tag.get("name")
            if tag_id and tag_name:
                tags_mapping[str(tag_id)] = str(tag_name)
    except Exception as e:
        logger.warning(f"Warning: Could not fetch tags: {e}")
    return tags_mapping


def _fetch_workflows(client: N8nClient) -> list[dict[str, Any]]:
    """Fetch workflows from n8n.

    Args:
        client: N8n API client

    Returns:
        List of workflow summaries

    Raises:
        SystemExit: If no workflows found or error fetching
    """
    logger.info("Fetching workflows...")
    try:
        remote_workflows = client.list_workflows()
        logger.info(f"Found {len(remote_workflows)} workflow(s)")
    except Exception as e:
        logger.critical(f"Error fetching workflows: {e}")

    if not remote_workflows:
        logger.info("No workflows found to export")
        raise SystemExit(0)
    return remote_workflows


def _clean_workflows_directory(workflows_dir: Path) -> None:
    """Clean workflows directory by deleting all JSON files.

    Args:
        workflows_dir: Directory containing workflow JSON files
    """
    logger.info("\nCleaning workflows directory...")
    if not workflows_dir.exists():
        return
    deleted_count = sum(1 for f in workflows_dir.glob("*.json") if (f.unlink(), True)[1])
    if deleted_count > 0:
        logger.info(f"  🗑  Deleted {deleted_count} existing workflow file(s)")


def _clean_scripts_directory(scripts_dir: Path) -> None:
    """Clean scripts directory by deleting all subdirectories.

    Args:
        scripts_dir: Directory containing script subdirectories
    """
    logger.info("Cleaning scripts directory...")
    if not scripts_dir.exists():
        return
    deleted_count = 0
    for script_dir in scripts_dir.iterdir():
        if script_dir.is_dir():
            shutil.rmtree(script_dir)
            deleted_count += 1
    if deleted_count > 0:
        plural = "y" if deleted_count == 1 else "ies"
        logger.info(f"  🗑  Deleted {deleted_count} existing script director{plural}")


def _update_credentials_map(
    credentials_map: dict[str, dict[str, list[str]]],
    workflow_name: str,
    credentials: list[dict[str, str]]
) -> None:
    """Update credentials map with workflow credentials.

    Args:
        credentials_map: Map of credential types to names to workflow lists
        workflow_name: Name of the workflow
        credentials: List of credential dicts with 'type' and 'name'
    """
    for cred in credentials:
        cred_type = cred["type"]
        cred_name = cred["name"]

        if cred_type not in credentials_map:
            credentials_map[cred_type] = {}
        if cred_name not in credentials_map[cred_type]:
            credentials_map[cred_type][cred_name] = []
        if workflow_name not in credentials_map[cred_type][cred_name]:
            credentials_map[cred_type][cred_name].append(workflow_name)


def _extract_tag_names(workflow: dict[str, Any]) -> list[str]:
    """Extract tag names from workflow.

    Args:
        workflow: Workflow JSON object

    Returns:
        List of tag names
    """
    tag_names: list[str] = []
    for tag in workflow.get("tags", []):
        if isinstance(tag, dict):
            tag_name = tag.get("name")
            if tag_name:
                tag_names.append(str(tag_name))
    return tag_names


def _export_single_workflow(
    client: N8nClient,
    wf_summary: dict[str, Any],
    workflows_dir: Path,
    scripts_dir: Path,
    externalize_code: bool,
    credentials_map: dict[str, dict[str, list[str]]],
) -> tuple[dict[str, Any] | None, int]:
    """Export a single workflow.

    Args:
        client: N8n API client
        wf_summary: Workflow summary from list
        workflows_dir: Directory to save workflow JSON
        scripts_dir: Directory to save script files
        externalize_code: Whether to externalize code blocks
        credentials_map: Map to update with workflow credentials

    Returns:
        Tuple of (workflow spec for manifest, externalized count) or (None, 0) if failed
    """
    wf_id = wf_summary.get("id")
    wf_name = wf_summary.get("name")

    if not wf_id or not wf_name:
        logger.warning("  ⚠ Skipping workflow with missing id or name")
        return None, 0

    logger.info(f"  Exporting: {wf_name}")

    try:
        workflow = client.get_workflow(wf_id)
    except Exception as e:
        logger.error(f"    ✗ Error fetching workflow: {e}")
        return None, 0

    # Update credentials map
    workflow_credentials = _extract_credentials(workflow)
    _update_credentials_map(credentials_map, wf_name, workflow_credentials)

    # Clean workflow
    workflow_cleaned = strip_volatile_fields(
        workflow,
        fields=["id", "createdAt", "updatedAt", "versionId", "shared", "isArchived", "triggerCount"],
    )

    # Externalize code if enabled
    externalized_count = 0
    if externalize_code:
        workflow_cleaned, externalized_count = _externalize_workflow_code(
            workflow_cleaned, wf_name, scripts_dir
        )
        if externalized_count > 0:
            logger.info(f"    ✓ Externalized {externalized_count} code block(s)")

    # Write workflow file
    normalized_json = normalize_json(workflow_cleaned)
    safe_name = _sanitize_filename(wf_name)
    filename = f"{safe_name}.json"
    filepath = workflows_dir / filename

    try:
        filepath.write_text(normalized_json)
        logger.info(f"    ✓ Saved to: n8n/workflows/{filename}")
    except Exception as e:
        logger.error(f"    ✗ Error writing file: {e}")
        return None, 0

    # Build manifest spec
    tag_names = _extract_tag_names(workflow)
    spec = {
        "name": wf_name,
        "active": workflow.get("active", False),
        "tags": tag_names,
    }

    return spec, externalized_count


def _write_credentials_yaml(
    credentials_map: dict[str, dict[str, list[str]]],
    n8n_root: Path,
    repo_root: Path
) -> None:
    """Write credentials.yaml documentation file.

    Args:
        credentials_map: Map of credential types to names to workflow lists
        n8n_root: n8n directory path
        repo_root: Repository root path
    """
    if not credentials_map:
        return

    logger.info("\nGenerating credentials documentation...")
    credentials_yaml_path = n8n_root / "credentials.yaml"

    # Transform to desired YAML structure
    credentials_output: dict[str, list[dict[str, Any]]] = {}
    for cred_type in sorted(credentials_map.keys()):
        credentials_output[cred_type] = []
        for cred_name in sorted(credentials_map[cred_type].keys()):
            workflows_list = sorted(credentials_map[cred_type][cred_name])
            credentials_output[cred_type].append({
                "name": cred_name,
                "workflows": workflows_list
            })

    try:
        credentials_yaml_content = yaml.dump(
            credentials_output,
            default_flow_style=False,
            sort_keys=False,
        )
        credentials_yaml_path.write_text(credentials_yaml_content)
        total_creds = sum(len(creds) for creds in credentials_output.values())
        logger.info(f"  ✓ Documented {total_creds} credential(s) in {credentials_yaml_path.relative_to(repo_root)}")
    except Exception as e:
        logger.error(f"  ✗ Error writing credentials.yaml: {e}")


def _write_manifest_file(
    exported_specs: list[dict[str, Any]],
    tags_mapping: dict[str, str],
    externalize_code: bool,
    manifest_file: Path,
    repo_root: Path
) -> None:
    """Write workflows manifest file.

    Args:
        exported_specs: List of workflow specs
        tags_mapping: Map of tag IDs to names
        externalize_code: Whether code externalization is enabled
        manifest_file: Path to manifest file
        repo_root: Repository root path
    """
    if not exported_specs:
        return

    logger.info("\nUpdating manifest...")

    # Sort workflows by name
    sorted_specs = sorted(exported_specs, key=lambda w: w["name"])

    # Get all tag names
    all_tag_names = sorted(set(tags_mapping.values()))

    # Write manifest
    manifest_content = yaml.dump(
        {
            "externalize_code": externalize_code,
            "tags": all_tag_names,
            "workflows": sorted_specs
        },
        default_flow_style=False,
        sort_keys=False,
    )

    try:
        manifest_file.write_text(manifest_content)
        logger.info(f"  ✓ Updated manifest: {manifest_file.relative_to(repo_root)}")
    except Exception as e:
        logger.error(f"  ✗ Error writing manifest: {e}")


def _log_export_summary(exported_count: int, total_externalized: int) -> None:
    """Log export completion summary.

    Args:
        exported_count: Number of workflows exported
        total_externalized: Total number of code blocks externalized
    """
    logger.info(f"\n✓ Export complete! Exported {exported_count} workflow(s)")
    if total_externalized > 0:
        logger.info(f"✓ Externalized {total_externalized} code block(s) to script files")
    logger.info("\nNext steps:")
    logger.info("  1. Review the exported workflows")
    if total_externalized > 0:
        logger.info("  2. Review the externalized scripts in n8n/scripts/")
        logger.info("  3. git add n8n/")
        logger.info("  4. git commit -m 'Export workflows from n8n with externalized code'")
    else:
        logger.info("  2. git add n8n/")
        logger.info("  3. git commit -m 'Export workflows from n8n'")


def run_export(args: argparse.Namespace) -> None:
    """Export workflows from n8n instance.

    Args:
        args: CLI arguments

    Raises:
        SystemExit: If export fails
    """
    # Setup paths
    repo_root = Path(args.repo_root).resolve()
    n8n_root = repo_root / "n8n"
    workflows_dir = n8n_root / "workflows"
    manifests_dir = n8n_root / "manifests"
    scripts_dir = n8n_root / "scripts"
    manifest_file = manifests_dir / "workflows.yaml"

    # Create directories
    workflows_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    # Load configuration
    externalize_code = _load_externalize_code_setting(repo_root)
    try:
        auth = load_auth(repo_root, args)
    except Exception as e:
        logger.critical(f"Error: {e}")

    # Initialize
    logger.info(f"Exporting workflows from {auth.api_url}")
    logger.info(f"Target directory: {workflows_dir}")
    logger.info("")

    client = N8nClient(auth.api_url, auth.api_key)

    # Fetch data
    tags_mapping = _fetch_tags_mapping(client)
    workflows_to_export = _fetch_workflows(client)

    # Log export mode
    logger.info(f"\nExporting {len(workflows_to_export)} workflow(s) (mirror mode)...")
    mode = "ENABLED" if externalize_code else "DISABLED"
    logger.info(f"Code externalization: {mode} (set in manifest)")

    # Clean directories
    _clean_workflows_directory(workflows_dir)
    _clean_scripts_directory(scripts_dir)

    # Export workflows
    exported_specs: list[dict[str, Any]] = []
    total_externalized = 0
    credentials_map: dict[str, dict[str, list[str]]] = {}

    for wf_summary in workflows_to_export:
        spec, externalized_count = _export_single_workflow(
            client, wf_summary, workflows_dir, scripts_dir,
            externalize_code, credentials_map
        )
        if spec:
            exported_specs.append(spec)
            total_externalized += externalized_count

    # Write output files
    _write_credentials_yaml(credentials_map, n8n_root, repo_root)
    _write_manifest_file(exported_specs, tags_mapping, externalize_code, manifest_file, repo_root)

    # Summary
    _log_export_summary(len(exported_specs), total_externalized)


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

            logger.info(f"      → Externalized {field_name} from node '{node_name}' to {relative_path}")

    return modified, externalized_count
