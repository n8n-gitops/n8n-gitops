"""Export command implementation."""

import argparse
from pathlib import Path
from typing import Any

import yaml

from n8n_gitops.config import load_auth
from n8n_gitops.gitref import WorkingTreeSnapshot
from n8n_gitops.manifest import load_manifest
from n8n_gitops.n8n_client import N8nClient
from n8n_gitops.normalize import normalize_json, strip_volatile_fields


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
    manifest_file = manifests_dir / "workflows.yaml"

    # Ensure directories exist
    workflows_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

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

    # Determine which workflows to export
    workflows_to_export: list[dict[str, Any]] = []

    if args.all:
        workflows_to_export = remote_workflows
    elif args.names:
        # Parse comma-separated names
        requested_names = [n.strip() for n in args.names.split(",")]
        for wf in remote_workflows:
            if wf.get("name") in requested_names:
                workflows_to_export.append(wf)
        # Check for missing workflows
        found_names = {wf.get("name") for wf in workflows_to_export}
        missing = set(requested_names) - found_names
        if missing:
            print(f"Warning: Workflows not found: {', '.join(missing)}")
    elif args.from_manifest:
        # Load manifest and export only those workflows
        snapshot = WorkingTreeSnapshot(repo_root)
        try:
            manifest = load_manifest(snapshot, "n8n")
            manifest_names = {spec.name for spec in manifest.workflows}
            for wf in remote_workflows:
                if wf.get("name") in manifest_names:
                    workflows_to_export.append(wf)
        except Exception as e:
            print(f"Error loading manifest: {e}")
            raise SystemExit(1)
    else:
        print("Error: Must specify --all, --names, or --from-manifest")
        raise SystemExit(1)

    if not workflows_to_export:
        print("No workflows selected for export")
        raise SystemExit(0)

    print(f"\nExporting {len(workflows_to_export)} workflow(s)...")

    # Export each workflow
    exported_specs: list[dict[str, Any]] = []

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

        # Strip volatile fields (id, createdAt, updatedAt, etc.)
        # For v1, we keep these fields to preserve full workflow state
        # Users can configure stripping later if needed
        workflow_cleaned = strip_volatile_fields(
            workflow,
            fields=["id", "createdAt", "updatedAt"],
        )

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

        # Add to manifest
        exported_specs.append(
            {
                "name": wf_name,
                "file": f"workflows/{filename}",
                "active": workflow.get("active", False),
                "tags": workflow.get("tags", []),
            }
        )

    # Update manifest if --all mode
    if args.all and exported_specs:
        print("\nUpdating manifest...")

        # Load existing manifest if it exists
        existing_specs: list[dict[str, Any]] = []
        if manifest_file.exists():
            try:
                manifest_data = yaml.safe_load(manifest_file.read_text())
                if isinstance(manifest_data, dict) and "workflows" in manifest_data:
                    existing_specs = manifest_data["workflows"]
            except Exception as e:
                print(f"  ⚠ Warning: Could not load existing manifest: {e}")

        # Merge: update existing entries or add new ones
        existing_names = {spec.get("name"): idx for idx, spec in enumerate(existing_specs)}

        for new_spec in exported_specs:
            name = new_spec["name"]
            if name in existing_names:
                # Update existing entry
                existing_specs[existing_names[name]] = new_spec
            else:
                # Add new entry
                existing_specs.append(new_spec)

        # Write manifest
        manifest_content = yaml.dump(
            {"workflows": existing_specs},
            default_flow_style=False,
            sort_keys=False,
        )
        try:
            manifest_file.write_text(manifest_content)
            print(f"  ✓ Updated manifest: {manifest_file.relative_to(repo_root)}")
        except Exception as e:
            print(f"  ✗ Error writing manifest: {e}")

    print(f"\n✓ Export complete! Exported {len(exported_specs)} workflow(s)")
    print("\nNext steps:")
    print("  1. Review the exported workflows")
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
    import re
    safe = re.sub(r"[^\w\-.]", "_", name)
    # Remove multiple underscores
    safe = re.sub(r"_+", "_", safe)
    # Remove leading/trailing underscores
    safe = safe.strip("_")
    return safe or "workflow"
