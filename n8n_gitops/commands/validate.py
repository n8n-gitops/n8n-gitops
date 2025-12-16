"""Validate command implementation."""

import argparse
import json
from pathlib import Path

from n8n_gitops.envschema import validate_env_schema
from n8n_gitops.exceptions import ManifestError, RenderError, ValidationError
from n8n_gitops.gitref import create_snapshot
from n8n_gitops.manifest import load_manifest
from n8n_gitops.normalize import normalize_json
from n8n_gitops.render import RenderOptions, render_workflow_json


def run_validate(args: argparse.Namespace) -> None:
    """Run validation on workflows and manifests.

    Args:
        args: CLI arguments

    Raises:
        SystemExit: If validation fails
    """
    repo_root = Path(args.repo_root).resolve()
    n8n_root = "n8n"

    # Create snapshot
    snapshot = create_snapshot(repo_root, args.git_ref)

    warnings: list[str] = []
    errors: list[str] = []

    print(f"Validating n8n-gitops project at {repo_root}")
    if args.git_ref:
        print(f"Using git ref: {args.git_ref}")
    print()

    # Load manifest
    try:
        manifest = load_manifest(snapshot, n8n_root)
        print(f"✓ Manifest loaded: {len(manifest.workflows)} workflow(s)")
    except ManifestError as e:
        errors.append(f"Manifest error: {e}")
        _print_results(warnings, errors, args.strict)
        raise SystemExit(1)

    # Validate each workflow
    for spec in manifest.workflows:
        workflow_path = f"{n8n_root}/{spec.file}"
        print(f"\nValidating workflow: {spec.name}")
        print(f"  File: {workflow_path}")

        # Check if file exists
        if not snapshot.exists(workflow_path):
            errors.append(f"Workflow file not found: {workflow_path}")
            continue

        # Load and parse JSON
        try:
            workflow_json = snapshot.read_text(workflow_path)
            workflow = json.loads(workflow_json)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in {workflow_path}: {e}")
            continue
        except Exception as e:
            errors.append(f"Failed to read {workflow_path}: {e}")
            continue

        # Render workflow with includes
        render_options = RenderOptions(
            enforce_no_inline_code=args.enforce_no_inline_code,
            enforce_checksum=args.enforce_checksum,
            require_checksum=args.require_checksum,
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

            # Process reports
            for report in reports:
                if report.status == "included":
                    print(f"  ✓ Included: {report.include_path} in {report.node_name}")
                elif report.status == "inline_code":
                    msg = f"Inline code in node '{report.node_name}' field '{report.field}'"
                    if args.enforce_no_inline_code:
                        errors.append(msg)
                    else:
                        warnings.append(msg)
                elif report.status == "checksum_mismatch":
                    msg = (
                        f"Checksum mismatch in node '{report.node_name}': "
                        f"{report.include_path} "
                        f"(expected: {report.sha256_expected}, got: {report.sha256_actual})"
                    )
                    if args.enforce_checksum:
                        errors.append(msg)
                    else:
                        warnings.append(msg)
                elif report.status == "missing_file":
                    errors.append(
                        f"Include file not found: {report.include_path} "
                        f"(node '{report.node_name}')"
                    )

        except RenderError as e:
            errors.append(f"Render error in {spec.name}: {e}")
            continue

        # Validate normalization
        try:
            normalized = normalize_json(workflow)
            if workflow_json.strip() != normalized.strip():
                msg = f"Workflow {spec.name} is not normalized (run through normalize_json)"
                if args.strict:
                    errors.append(msg)
                else:
                    warnings.append(msg)
        except Exception as e:
            warnings.append(f"Failed to check normalization for {spec.name}: {e}")

        print(f"  ✓ Workflow validation passed: {spec.name}")

    # Validate environment schema
    print("\nValidating environment schema...")
    try:
        env_issues = validate_env_schema(snapshot, n8n_root)
        if env_issues:
            for issue in env_issues:
                if args.strict:
                    errors.append(issue)
                else:
                    warnings.append(issue)
        else:
            print("  ✓ Environment schema validation passed")
    except ValidationError as e:
        errors.append(f"Environment schema error: {e}")

    # Print results
    print()
    _print_results(warnings, errors, args.strict)

    # Exit with appropriate code
    if errors or (args.strict and warnings):
        raise SystemExit(1)
    else:
        print("\n✓ Validation successful!")
        raise SystemExit(0)


def _print_results(warnings: list[str], errors: list[str], strict: bool) -> None:
    """Print validation results.

    Args:
        warnings: List of warnings
        errors: List of errors
        strict: Whether strict mode is enabled
    """
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"  ⚠ {warning}")
        if strict:
            print("\n(Warnings treated as errors in strict mode)")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"  ✗ {error}")
