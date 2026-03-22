"""Deploy command implementation."""

import argparse
import json
from pathlib import Path
from typing import Any


from n8n_gitops import logger
from n8n_gitops.config import load_auth
from n8n_gitops.exceptions import ManifestError, RenderError
from n8n_gitops.gitref import create_snapshot
from n8n_gitops.manifest import load_manifest
from n8n_gitops.n8n_client import N8nClient
from n8n_gitops.render import RenderOptions, render_workflow_json


def _sync_tags(
    client: N8nClient,
    manifest_tags: list[str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Synchronize tags between manifest and n8n instance.

    Args:
        client: N8n API client
        manifest_tags: List of tag names from manifest

    Returns:
        Tuple of (tag_name_to_id, remote_tags_by_name)
        - tag_name_to_id: Mapping from tag name to tag ID for deployment
        - remote_tags_by_name: All remote tags (name → ID) for pruning
    """
    logger.info("\nSynchronizing tags...")

    # Fetch existing tags from n8n
    try:
        remote_tags = client.list_tags()
        logger.info(f"Found {len(remote_tags)} remote tag(s)")
    except Exception as e:
        logger.warning(f"  ⚠ Warning: Could not fetch tags from n8n: {e}")
        return {}, {}

    # Build remote tag name→ID mapping
    remote_tags_by_name: dict[str, str] = {}
    for tag in remote_tags:
        tag_id = tag.get("id")
        tag_name = tag.get("name")
        if tag_id and tag_name:
            remote_tags_by_name[str(tag_name)] = str(tag_id)

    # Build name→ID mapping for manifest tags
    tag_name_to_id: dict[str, str] = {}

    for tag_name in manifest_tags:
        if tag_name in remote_tags_by_name:
            # Tag exists, use existing ID
            tag_id = remote_tags_by_name[tag_name]
            tag_name_to_id[tag_name] = tag_id
            logger.info(f"  ✓ Tag '{tag_name}' exists (ID: {tag_id})")
        else:
            # Tag doesn't exist, create it
            logger.info(f"  ➕ Creating tag '{tag_name}'")
            try:
                created_tag = client.create_tag(tag_name)
                new_tag_id = created_tag.get("id")

                if new_tag_id:
                    logger.info(f"    ✓ Created with ID: {new_tag_id}")
                    tag_name_to_id[tag_name] = str(new_tag_id)
                    # Add to remote mapping for pruning
                    remote_tags_by_name[tag_name] = str(new_tag_id)
                else:
                    logger.error("    ✗ Created tag but no ID returned")
            except Exception as e:
                logger.error(f"    ✗ Failed to create tag: {e}")

    return tag_name_to_id, remote_tags_by_name


def _prune_tags(
    client: N8nClient,
    manifest_tags: list[str],
    remote_tags_by_name: dict[str, str],
) -> None:
    """Delete tags from n8n that aren't in manifest.

    Args:
        client: N8n API client
        manifest_tags: List of tag names from manifest
        remote_tags_by_name: Remote tags (name → ID mapping)
    """
    # Find tags to delete
    tags_to_delete = [
        (name, tag_id)
        for name, tag_id in remote_tags_by_name.items()
        if name not in manifest_tags
    ]

    if not tags_to_delete:
        logger.info("\nNo tags to prune")
        return

    logger.info(f"\nPruning {len(tags_to_delete)} unused tag(s)...")
    for tag_name, tag_id in tags_to_delete:
        try:
            logger.info(f"  Deleting tag: {tag_name}")
            client.delete_tag(tag_id)
            logger.info("    ✓ Deleted")
        except Exception as e:
            logger.error(f"    ✗ Failed: {e}")


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

        # Determine action (upsert: update if exists, create if not)
        if spec.name in name_to_id:
            action = "update"
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
) -> None:
    """Print deployment plan to user.

    Args:
        plan: Deployment plan items
        workflows_to_prune: Workflows to delete
    """
    logger.info("\nDeployment plan:")
    for item in plan:
        spec = item["spec"]
        action = item["action"]
        if action == "create":
            logger.info(f"  + CREATE: {spec.name}")
        elif action == "update":
            logger.info(f"  ⟳ UPDATE: {spec.name}")

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


def _deploy_workflow_update(
    client: N8nClient,
    spec: Any,
    api_workflow: dict[str, Any],
    workflow_id: str,
) -> str:
    """Update an existing workflow in place.

    Preserves the workflow ID, webhook URLs, and execution history.

    Args:
        client: N8n API client
        spec: Workflow spec
        api_workflow: Workflow data for API
        workflow_id: ID of workflow to update

    Returns:
        Workflow ID (unchanged)
    """
    logger.info(f"  Updating: {spec.name}...")
    client.update_workflow(workflow_id, api_workflow)
    logger.info(f"    ✓ Updated (ID: {workflow_id})")
    return workflow_id


def _set_workflow_state(
    client: N8nClient,
    spec: Any,
    workflow_id: str,
    tag_name_to_id: dict[str, str],
) -> None:
    """Set workflow active state and tags.

    Args:
        client: N8n API client
        spec: Workflow spec
        workflow_id: Workflow ID
        tag_name_to_id: Mapping from tag name to tag ID
    """
    if spec.active:
        logger.info("    Activating workflow...")
        client.activate_workflow(workflow_id)
        logger.info("    ✓ Activated")
    else:
        logger.info("    Deactivating workflow...")
        client.deactivate_workflow(workflow_id)
        logger.info("    ✓ Deactivated")

    # Update workflow tags (convert names to IDs)
    if spec.tags:
        logger.info(f"    Updating tags ({len(spec.tags)} tag(s))...")
        # Convert tag names to IDs for API call
        tag_ids = [tag_name_to_id[tag_name] for tag_name in spec.tags if tag_name in tag_name_to_id]
        if tag_ids:
            client.update_workflow_tags(workflow_id, tag_ids)
            logger.info("    ✓ Tags updated")
        else:
            logger.warning("    ⚠ No valid tag IDs found")


def _execute_workflow_deployment(
    client: N8nClient,
    plan_item: dict[str, Any],
    tag_name_to_id: dict[str, str],
) -> None:
    """Execute deployment of a single workflow.

    Args:
        client: N8n API client
        plan_item: Deployment plan item
        tag_name_to_id: Mapping from tag name to tag ID

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
        elif action == "update":
            workflow_id = _deploy_workflow_update(client, spec, api_workflow, workflow_id)

        # Set active state based on manifest
        if workflow_id:
            _set_workflow_state(client, spec, workflow_id, tag_name_to_id)

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
    tag_name_to_id: dict[str, str],
) -> None:
    """Execute deployment of all workflows in plan.

    Args:
        client: N8n API client
        plan: List of deployment plan items
        tag_name_to_id: Mapping from tag name to tag ID
    """
    logger.info("\nExecuting deployment...")
    for item in plan:
        _execute_workflow_deployment(client, item, tag_name_to_id)


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
        "activeVersion",     # Active version (read-only in n8n v2)
        "activeVersionId",  # Active version ID (n8n v2)
        "versionCounter",   # Version counter (n8n v2)
        "description",      # Description (not accepted in POST)
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

    # Clean settings: remove fields not accepted by the API
    _ALLOWED_SETTINGS = {
        "saveExecutionProgress", "saveManualExecutions",
        "saveDataErrorExecution", "saveDataSuccessExecution",
        "executionTimeout", "errorWorkflow", "timezone",
        "executionOrder", "callerPolicy", "callerIds",
        "timeSavedPerExecution", "availableInMCP",
    }
    if "settings" in cleaned and isinstance(cleaned["settings"], dict):
        cleaned["settings"] = {
            k: v for k, v in cleaned["settings"].items()
            if k in _ALLOWED_SETTINGS
        }

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
    client = N8nClient(auth.api_url, auth.api_key, insecure=auth.insecure)

    # Synchronize tags (create missing tags, get name→ID mapping)
    tag_name_to_id, remote_tags_by_name = _sync_tags(client, manifest.tags)

    # Prune tags not in manifest
    _prune_tags(client, manifest.tags, remote_tags_by_name)

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
    _print_deployment_plan(plan, workflows_to_prune)

    # Dry run check
    if args.dry_run:
        logger.info("\n[DRY RUN] No changes made")
        raise SystemExit(0)

    # Execute deployment and prune
    _execute_deployments(client, plan, tag_name_to_id)
    _execute_prune(client, workflows_to_prune)

    logger.info("\n✓ Deployment successful!")
