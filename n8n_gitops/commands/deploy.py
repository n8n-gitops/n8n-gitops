"""Deploy command implementation."""

import argparse
import json
from pathlib import Path
from typing import Any

from n8n_gitops.config import load_auth
from n8n_gitops.exceptions import ManifestError, RenderError
from n8n_gitops.gitref import create_snapshot
from n8n_gitops.manifest import load_manifest
from n8n_gitops.n8n_client import N8nClient
from n8n_gitops.normalize import normalize_json
from n8n_gitops.render import RenderOptions, render_workflow_json


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
        print(f"Error: {e}")
        raise SystemExit(1)

    # Create snapshot
    snapshot = create_snapshot(repo_root, args.git_ref)

    print(f"Deploying workflows from {repo_root}")
    if args.git_ref:
        print(f"Using git ref: {args.git_ref}")
    print(f"Target: {auth.api_url}")
    print()

    # Load manifest
    try:
        manifest = load_manifest(snapshot, n8n_root)
        print(f"Loaded manifest: {len(manifest.workflows)} workflow(s)")
    except ManifestError as e:
        print(f"Error loading manifest: {e}")
        raise SystemExit(1)

    # Initialize client
    client = N8nClient(auth.api_url, auth.api_key)

    # Fetch remote workflows
    print("\nFetching remote workflows...")
    try:
        remote_workflows = client.list_workflows()
        print(f"Found {len(remote_workflows)} remote workflow(s)")
    except Exception as e:
        print(f"Error fetching remote workflows: {e}")
        raise SystemExit(1)

    # Create name -> id mapping
    name_to_id: dict[str, str] = {}
    for wf in remote_workflows:
        name = wf.get("name")
        wf_id = wf.get("id")
        if name and wf_id:
            name_to_id[name] = wf_id

    # Plan deployment
    plan: list[dict[str, Any]] = []

    for spec in manifest.workflows:
        workflow_path = f"{n8n_root}/{spec.file}"

        # Load workflow
        try:
            workflow_json = snapshot.read_text(workflow_path)
            workflow = json.loads(workflow_json)
        except Exception as e:
            print(f"Error loading workflow {spec.name}: {e}")
            raise SystemExit(1)

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
                git_ref=args.git_ref,
                options=render_options,
            )
        except RenderError as e:
            print(f"Error rendering workflow {spec.name}: {e}")
            raise SystemExit(1)

        # Ensure name matches manifest
        rendered["name"] = spec.name

        # Determine action (create or update)
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

    # Print plan
    print("\nDeployment plan:")
    for item in plan:
        spec = item["spec"]
        action = item["action"]
        if action == "create":
            print(f"  + CREATE: {spec.name} (active: {spec.active})")
        else:
            print(f"  ~ UPDATE: {spec.name} (active: {spec.active})")

        for report in item["reports"]:
            if report.status == "included":
                print(f"      ✓ Include: {report.include_path}")

    # Dry run check
    if args.dry_run:
        print("\n[DRY RUN] No changes made")
        raise SystemExit(0)

    # Execute deployment
    print("\nExecuting deployment...")
    for item in plan:
        spec = item["spec"]
        workflow = item["workflow"]
        action = item["action"]
        workflow_id = item["workflow_id"]

        try:
            if action == "create":
                print(f"  Creating: {spec.name}...")
                result = client.create_workflow(workflow)
                workflow_id = result.get("id")
                print(f"    ✓ Created with ID: {workflow_id}")
            else:
                print(f"  Updating: {spec.name}...")
                client.update_workflow(workflow_id, workflow)
                print(f"    ✓ Updated")

            # Set active state
            if workflow_id:
                if spec.active:
                    print(f"    Activating...")
                    client.activate_workflow(workflow_id)
                    print(f"    ✓ Activated")
                else:
                    print(f"    Deactivating...")
                    client.deactivate_workflow(workflow_id)
                    print(f"    ✓ Deactivated")

        except Exception as e:
            print(f"    ✗ Error: {e}")
            raise SystemExit(1)

    print("\n✓ Deployment successful!")
