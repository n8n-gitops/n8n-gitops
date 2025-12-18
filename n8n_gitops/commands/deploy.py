"""Deploy command implementation."""

import argparse
import json
from pathlib import Path
from typing import Any

from datetime import datetime

from n8n_gitops import logger
from n8n_gitops.config import load_auth
from n8n_gitops.exceptions import ManifestError, RenderError
from n8n_gitops.gitref import create_snapshot
from n8n_gitops.manifest import load_manifest
from n8n_gitops.n8n_client import N8nClient
from n8n_gitops.render import RenderOptions, render_workflow_json


def _sync_tags(
    client: N8nClient,
    manifest_tags: dict[str, str],
) -> tuple[dict[str, str], bool]:
    """Synchronize tags between manifest and n8n instance.

    Args:
        client: N8n API client
        manifest_tags: Tag ID to name mapping from manifest

    Returns:
        Tuple of (updated_tags_mapping, tags_were_created)
        - updated_tags_mapping: Updated tag ID to name mapping (with new IDs for created tags)
        - tags_were_created: True if any tags were created (manifest needs updating)
    """
    logger.info("\nSynchronizing tags...")

    # Fetch existing tags from n8n
    try:
        remote_tags = client.list_tags()
        logger.info(f"Found {len(remote_tags)} remote tag(s)")
    except Exception as e:
        logger.warning(f"  ⚠ Warning: Could not fetch tags from n8n: {e}")
        return manifest_tags, False

    # Build remote tag mappings
    remote_tags_by_id: dict[str, str] = {}
    remote_tags_by_name: dict[str, str] = {}

    for tag in remote_tags:
        tag_id = tag.get("id")
        tag_name = tag.get("name")
        if tag_id and tag_name:
            remote_tags_by_id[str(tag_id)] = str(tag_name)
            remote_tags_by_name[str(tag_name)] = str(tag_id)

    # Track changes
    updated_tags = dict(manifest_tags)  # Copy manifest tags
    tags_were_created = False

    # Process each tag from manifest
    for tag_id, tag_name in manifest_tags.items():
        if tag_id in remote_tags_by_id:
            # Tag ID exists in n8n
            remote_name = remote_tags_by_id[tag_id]
            if remote_name != tag_name:
                # Name is different, update it
                logger.info(f"  🔄 Updating tag '{tag_id}': '{remote_name}' → '{tag_name}'")
                try:
                    client.update_tag(tag_id, tag_name)
                    logger.info("    ✓ Updated")
                except Exception as e:
                    logger.error(f"    ✗ Failed to update tag: {e}")
            else:
                # Name matches, nothing to do
                logger.info(f"  ✓ Tag '{tag_name}' (ID: {tag_id}) already up to date")
        else:
            # Tag ID doesn't exist in n8n, create new tag
            logger.info(f"  ➕ Creating tag '{tag_name}' (manifest ID '{tag_id}' not found in n8n)")
            try:
                created_tag = client.create_tag(tag_name)
                new_tag_id = created_tag.get("id")

                if new_tag_id:
                    logger.info(f"    ✓ Created with new ID: {new_tag_id}")
                    # Update the mapping with the new ID
                    updated_tags.pop(tag_id)  # Remove old ID
                    updated_tags[str(new_tag_id)] = tag_name
                    tags_were_created = True
                else:
                    logger.error("    ✗ Created tag but no ID returned")
            except Exception as e:
                logger.error(f"    ✗ Failed to create tag: {e}")

    return updated_tags, tags_were_created


def _update_tag_ids_in_manifest(
    manifest: Any,
    updated_tags: dict[str, str],
) -> None:
    """Update tag IDs in manifest after tag creation.

    Args:
        manifest: Manifest object
        updated_tags: Updated tag mapping with new IDs
    """
    # Build old_id -> new_id mapping
    old_ids = set(manifest.tags.keys())
    new_ids = set(updated_tags.keys())

    # Find which IDs changed
    id_mapping: dict[str, str] = {}
    for old_id in old_ids:
        if old_id not in new_ids:
            # This old ID was replaced, find the new one
            old_name = manifest.tags[old_id]
            for new_id, new_name in updated_tags.items():
                if new_name == old_name and new_id not in old_ids:
                    id_mapping[old_id] = new_id
                    break

    # Update tag IDs in workflow specs
    if id_mapping:
        logger.info(f"\n  Updating tag references in {len(manifest.workflows)} workflow(s)...")
        for spec in manifest.workflows:
            updated_tag_ids = []
            for tag_id in spec.tags:
                # Use new ID if it was mapped, otherwise keep old ID
                new_tag_id = id_mapping.get(tag_id, tag_id)
                updated_tag_ids.append(new_tag_id)
            spec.tags = updated_tag_ids

    # Update manifest tags mapping
    manifest.tags = updated_tags

    logger.warning("\n⚠ Tags were created with new IDs - manifest needs updating")
    logger.warning("  Run 'n8n-gitops export' to update the manifest with new tag IDs")


def _build_deployment_plan(
    manifest: Any,
    snapshot: Any,
    n8n_root: str,
    name_to_id: dict[str, str],
    git_ref: str | None,
) -> list[dict[str, Any]]:
    """Build deployment plan for workflows.

    Args:
        manifest: Manifest object
        snapshot: Git snapshot
        n8n_root: Root directory for n8n files
        name_to_id: Mapping of workflow names to IDs
        git_ref: Git reference for deployment

    Returns:
        List of deployment plan items
    """
    plan: list[dict[str, Any]] = []

    for spec in manifest.workflows:
        workflow_path = f"{n8n_root}/{spec.file}"

        # Load workflow
        try:
            workflow_json = snapshot.read_text(workflow_path)
            workflow = json.loads(workflow_json)
        except Exception as e:
            logger.critical(f"Error loading workflow {spec.name}: {e}")

        # Render with includes
        render_options = RenderOptions(
            enforce_no_inline_code=False,
            enforce_checksum=False,
            require_checksum=False,
            add_generated_header=False,
        )

        try:
            rendered, reports = render_workflow_json(
                workflow,
                snapshot,
                n8n_root=n8n_root,
                git_ref=git_ref,
                options=render_options,
            )
        except RenderError as e:
            logger.critical(f"Error rendering workflow {spec.name}: {e}")

        # Ensure name matches manifest
        rendered["name"] = spec.name

        # Determine action (default is replace: delete old + create new)
        if spec.name in name_to_id:
            action = "replace"  # Delete old workflow and create new one
            workflow_id = name_to_id[spec.name]
        else:
            action = "create"
            workflow_id = None

        plan.append(
            {
                "spec": spec,
                "workflow": rendered,
                "action": action,
                "workflow_id": workflow_id,
                "reports": reports,
            }
        )

    return plan


def _print_deployment_plan(
    plan: list[dict[str, Any]],
    workflows_to_prune: list[dict[str, Any]],
    backup: bool,
) -> None:
    """Print deployment plan to user.

    Args:
        plan: Deployment plan items
        workflows_to_prune: Workflows to delete
        backup: Whether backup mode is enabled
    """
    logger.info("\nDeployment plan:")
    for item in plan:
        spec = item["spec"]
        action = item["action"]
        if action == "create":
            logger.info(f"  + CREATE: {spec.name}")
        elif action == "replace":
            if backup:
                logger.info(f"  ⟳ REPLACE (with backup): {spec.name}")
            else:
                logger.info(f"  ⟳ REPLACE: {spec.name}")

        for report in item["reports"]:
            if report.status == "included":
                logger.info(f"      ✓ Include: {report.include_path}")

    if workflows_to_prune:
        logger.info(f"\n  🗑  PRUNE: {len(workflows_to_prune)} workflow(s) not in manifest:")
        for wf in workflows_to_prune:
            logger.info(f"      - {wf.get('name')}")


def _deploy_workflow_create(
    client: N8nClient,
    spec: Any,
    api_workflow: dict[str, Any],
) -> str | None:
    """Create a new workflow.

    Args:
        client: N8n API client
        spec: Workflow spec
        api_workflow: Workflow data for API

    Returns:
        Workflow ID or None
    """
    logger.info(f"  Creating: {spec.name}...")
    result = client.create_workflow(api_workflow)
    workflow_id = result.get("id")
    logger.info(f"    ✓ Created with ID: {workflow_id}")
    return workflow_id


def _deploy_workflow_replace_with_backup(
    client: N8nClient,
    spec: Any,
    api_workflow: dict[str, Any],
    workflow_id: str,
) -> str | None:
    """Replace workflow with backup of old version.

    Args:
        client: N8n API client
        spec: Workflow spec
        api_workflow: Workflow data for API
        workflow_id: ID of workflow to replace

    Returns:
        New workflow ID or None
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    backup_name = f"[BKP {timestamp}] {spec.name}"
    logger.info(f"    Backing up old workflow as: {backup_name}")

    # Rename old workflow
    old_workflow = client.get_workflow(workflow_id)
    old_workflow["name"] = backup_name
    old_workflow_cleaned = _prepare_workflow_for_api(old_workflow)
    client.update_workflow(workflow_id, old_workflow_cleaned)
    logger.info("    ✓ Backup created")

    # Now create new workflow with original name
    logger.info("    Creating new workflow...")
    result = client.create_workflow(api_workflow)
    new_workflow_id = result.get("id")
    logger.info(f"    ✓ Created with ID: {new_workflow_id}")
    return new_workflow_id


def _deploy_workflow_replace(
    client: N8nClient,
    api_workflow: dict[str, Any],
    workflow_id: str,
) -> str | None:
    """Replace workflow by deleting old and creating new.

    Args:
        client: N8n API client
        api_workflow: Workflow data for API
        workflow_id: ID of workflow to replace

    Returns:
        New workflow ID or None
    """
    # Delete old workflow and create new one
    logger.info("    Deleting old workflow...")
    try:
        client.delete_workflow(workflow_id)
        logger.info("    ✓ Old workflow deleted")
    except Exception as e:
        logger.warning(f"    ⚠ Could not delete old workflow: {e}")
        logger.warning("    → Creating new workflow anyway...")

    logger.info("    Creating new workflow...")
    result = client.create_workflow(api_workflow)
    new_workflow_id = result.get("id")
    logger.info(f"    ✓ Created with ID: {new_workflow_id}")
    return new_workflow_id


def _set_workflow_state(
    client: N8nClient,
    spec: Any,
    workflow_id: str,
) -> None:
    """Set workflow active state and tags.

    Args:
        client: N8n API client
        spec: Workflow spec
        workflow_id: Workflow ID
    """
    if spec.active:
        logger.info("    Activating workflow...")
        client.activate_workflow(workflow_id)
        logger.info("    ✓ Activated")
    else:
        logger.info("    Deactivating workflow...")
        client.deactivate_workflow(workflow_id)
        logger.info("    ✓ Deactivated")

    # Update workflow tags
    if spec.tags:
        logger.info(f"    Updating tags ({len(spec.tags)} tag(s))...")
        client.update_workflow_tags(workflow_id, spec.tags)
        logger.info("    ✓ Tags updated")


def _execute_workflow_deployment(
    client: N8nClient,
    plan_item: dict[str, Any],
    backup: bool,
) -> None:
    """Execute deployment of a single workflow.

    Args:
        client: N8n API client
        plan_item: Deployment plan item
        backup: Whether to backup on replace

    Raises:
        SystemExit: If deployment fails
    """
    spec = plan_item["spec"]
    workflow = plan_item["workflow"]
    action = plan_item["action"]
    workflow_id = plan_item["workflow_id"]

    try:
        # Prepare workflow for API (remove fields that cause validation errors)
        api_workflow = _prepare_workflow_for_api(workflow)

        if action == "create":
            workflow_id = _deploy_workflow_create(client, spec, api_workflow)
        elif action == "replace":
            logger.info(f"  Replacing: {spec.name}...")
            if backup:
                workflow_id = _deploy_workflow_replace_with_backup(
                    client, spec, api_workflow, workflow_id
                )
            else:
                workflow_id = _deploy_workflow_replace(client, api_workflow, workflow_id)

        # Set active state based on manifest
        if workflow_id:
            _set_workflow_state(client, spec, workflow_id)

    except Exception as e:
        logger.error(f"    ✗ Error: {e}")

        # Provide helpful suggestions for common errors
        error_str = str(e).lower()
        if "additional properties" in error_str or "validation" in error_str:
            logger.error("\n    💡 Tip: The workflow file may contain n8n-managed fields.")
            logger.error("    Run 'n8n-gitops validate' to check for problematic fields.")
            logger.error("    Re-export the workflow to get a clean version:")
            logger.error(f"      n8n-gitops export --names \"{spec.name}\" --externalize-code")

        raise SystemExit(1)


def _build_name_to_id_mapping(remote_workflows: list[dict[str, Any]]) -> dict[str, str]:
    """Build mapping of workflow names to IDs.

    Args:
        remote_workflows: List of remote workflows

    Returns:
        Dictionary mapping workflow names to IDs
    """
    name_to_id: dict[str, str] = {}
    for wf in remote_workflows:
        name = wf.get("name")
        wf_id = wf.get("id")
        if name and wf_id:
            name_to_id[name] = wf_id
    return name_to_id


def _find_workflows_to_prune(
    remote_workflows: list[dict[str, Any]],
    manifest: Any,
) -> list[dict[str, Any]]:
    """Find workflows to prune that are not in manifest.

    Args:
        remote_workflows: List of remote workflows
        manifest: Manifest object

    Returns:
        List of workflows to delete
    """
    manifest_names = {spec.name for spec in manifest.workflows}
    workflows_to_prune = []
    for wf in remote_workflows:
        wf_name = wf.get("name")
        if wf_name and wf_name not in manifest_names:
            workflows_to_prune.append(wf)
    return workflows_to_prune


def _fetch_remote_workflows(client: N8nClient) -> list[dict[str, Any]]:
    """Fetch remote workflows from n8n instance.

    Args:
        client: N8n API client

    Returns:
        List of remote workflows

    Raises:
        SystemExit: If fetching fails
    """
    logger.info("\nFetching remote workflows...")
    try:
        remote_workflows = client.list_workflows()
        logger.info(f"Found {len(remote_workflows)} remote workflow(s)")
        return remote_workflows
    except Exception as e:
        logger.critical(f"Error fetching remote workflows: {e}")


def _execute_deployments(
    client: N8nClient,
    plan: list[dict[str, Any]],
    backup: bool,
) -> None:
    """Execute deployment of all workflows in plan.

    Args:
        client: N8n API client
        plan: List of deployment plan items
        backup: Whether to backup on replace
    """
    logger.info("\nExecuting deployment...")
    for item in plan:
        _execute_workflow_deployment(client, item, backup)


def _execute_prune(
    client: N8nClient,
    workflows_to_prune: list[dict[str, Any]],
) -> None:
    """Execute pruning of workflows not in manifest.

    Args:
        client: N8n API client
        workflows_to_prune: List of workflows to delete
    """
    if not workflows_to_prune:
        return

    logger.info("\nPruning workflows not in manifest...")
    for wf in workflows_to_prune:
        wf_id = wf.get("id")
        wf_name = wf.get("name")
        try:
            logger.info(f"  Deleting: {wf_name}...")
            client.delete_workflow(wf_id)
            logger.info("    ✓ Deleted")
        except Exception as e:
            logger.error(f"    ✗ Error deleting {wf_name}: {e}")


def _prepare_workflow_for_api(workflow: dict[str, Any]) -> dict[str, Any]:
    """Prepare workflow for n8n API by removing fields that cause validation errors.

    Args:
        workflow: Workflow object

    Returns:
        Cleaned workflow ready for API submission
    """
    import copy
    cleaned = copy.deepcopy(workflow)

    # Remove fields that n8n API doesn't accept or are auto-generated
    # These are readonly fields managed by n8n
    fields_to_remove = [
        "id",           # Auto-generated by n8n
        "createdAt",    # Auto-generated timestamp
        "updatedAt",    # Auto-generated timestamp
        "versionId",    # Version control field
        "shared",       # Sharing/permissions data
        "isArchived",   # Archive status (managed separately)
        "active",       # Active state (set via separate PATCH request)
        "tags",         # Tags (read-only in PUT, managed separately)
        "meta",         # Metadata (if null, causes issues)
        "pinData",      # Pinned test data (if empty, causes issues)
        "staticData",   # Static data (if null, causes issues)
        "triggerCount",  # Trigger counter
    ]

    for field in fields_to_remove:
        cleaned.pop(field, None)

    # Also remove null/empty fields that can cause issues
    # pinData, meta, staticData if they're null or empty
    if cleaned.get("meta") is None:
        cleaned.pop("meta", None)
    if cleaned.get("pinData") == {}:
        cleaned.pop("pinData", None)
    if cleaned.get("staticData") is None:
        cleaned.pop("staticData", None)

    return cleaned


def run_deploy(args: argparse.Namespace) -> None:
    """Deploy workflows to n8n instance.

    Args:
        args: CLI arguments

    Raises:
        SystemExit: If deployment fails
    """
    repo_root = Path(args.repo_root).resolve()
    n8n_root = "n8n"

    # Load auth config
    try:
        auth = load_auth(repo_root, args)
    except Exception as e:
        logger.critical(f"Error: {e}")

    # Create snapshot
    snapshot = create_snapshot(repo_root, args.git_ref)

    logger.info(f"Deploying workflows from {repo_root}")
    if args.git_ref:
        logger.info(f"Using git ref: {args.git_ref}")
    logger.info(f"Target: {auth.api_url}")
    logger.info("")

    # Load manifest
    try:
        manifest = load_manifest(snapshot, n8n_root)
        logger.info(f"Loaded manifest: {len(manifest.workflows)} workflow(s)")
    except ManifestError as e:
        logger.critical(f"Error loading manifest: {e}")

    # Initialize client
    client = N8nClient(auth.api_url, auth.api_key)

    # Synchronize tags (update names, create missing tags)
    updated_tags, tags_were_created = _sync_tags(client, manifest.tags)
    if tags_were_created:
        _update_tag_ids_in_manifest(manifest, updated_tags)

    # Fetch remote workflows and build mappings
    remote_workflows = _fetch_remote_workflows(client)
    name_to_id = _build_name_to_id_mapping(remote_workflows)

    # Build deployment plan
    plan = _build_deployment_plan(manifest, snapshot, n8n_root, name_to_id, args.git_ref)

    # Find workflows to prune if requested
    workflows_to_prune = []
    if args.prune:
        workflows_to_prune = _find_workflows_to_prune(remote_workflows, manifest)

    # Print deployment plan
    _print_deployment_plan(plan, workflows_to_prune, args.backup)

    # Dry run check
    if args.dry_run:
        logger.info("\n[DRY RUN] No changes made")
        raise SystemExit(0)

    # Execute deployment and prune
    _execute_deployments(client, plan, args.backup)
    _execute_prune(client, workflows_to_prune)

    logger.info("\n✓ Deployment successful!")
