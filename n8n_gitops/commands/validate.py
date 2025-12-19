"""Validate command implementation."""

import argparse
import json
from pathlib import Path
from typing import Any

from n8n_gitops import logger
from n8n_gitops.envschema import validate_env_schema
from n8n_gitops.exceptions import ManifestError, RenderError, ValidationError
from n8n_gitops.gitref import GitSnapshot, create_snapshot
from n8n_gitops.manifest import Manifest, load_manifest
from n8n_gitops.normalize import normalize_json
from n8n_gitops.render import RenderOptions, RenderReport, render_workflow_json

# Fields that should not be in workflow files (n8n-managed)
N8N_MANAGED_FIELDS = [
    "id", "createdAt", "updatedAt", "versionId",
    "shared", "isArchived", "triggerCount",
]

# Fields that should be removed if null/empty
NULLABLE_FIELDS = ["meta", "pinData", "staticData"]


def _load_manifest_safe(
    snapshot: GitSnapshot,
    n8n_root: str,
    errors: list[str]
) -> Manifest | None:
    """Load manifest with error handling.

    Args:
        snapshot: Git snapshot
        n8n_root: n8n directory path
        errors: List to append errors to

    Returns:
        Manifest object or None if failed
    """
    try:
        manifest = load_manifest(snapshot, n8n_root)
        logger.info(f"✓ Manifest loaded: {len(manifest.workflows)} workflow(s)")
        return manifest
    except ManifestError as e:
        errors.append(f"Manifest error: {e}")
        return None


def _load_workflow_file(
    snapshot: GitSnapshot,
    workflow_path: str,
    errors: list[str]
) -> dict[str, Any] | None:
    """Load and parse workflow JSON file.

    Args:
        snapshot: Git snapshot
        workflow_path: Path to workflow file
        errors: List to append errors to

    Returns:
        Workflow dict or None if failed
    """
    if not snapshot.exists(workflow_path):
        errors.append(f"Workflow file not found: {workflow_path}")
        return None

    try:
        workflow_json = snapshot.read_text(workflow_path)
        return json.loads(workflow_json)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON in {workflow_path}: {e}")
        return None
    except Exception as e:
        errors.append(f"Failed to read {workflow_path}: {e}")
        return None


def _process_render_report(
    report: RenderReport,
    args: argparse.Namespace,
    warnings: list[str],
    errors: list[str]
) -> None:
    """Process a single render report.

    Args:
        report: Render report
        args: CLI arguments
        warnings: List to append warnings to
        errors: List to append errors to
    """
    if report.status == "included":
        logger.info(f"  ✓ Included: {report.include_path} in {report.node_name}")
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


def _render_and_validate_workflow(
    workflow: dict[str, Any],
    snapshot: GitSnapshot,
    n8n_root: str,
    args: argparse.Namespace,
    spec_name: str,
    warnings: list[str],
    errors: list[str]
) -> bool:
    """Render workflow and validate includes.

    Args:
        workflow: Workflow dict
        snapshot: Git snapshot
        n8n_root: n8n directory path
        args: CLI arguments
        spec_name: Workflow name
        warnings: List to append warnings to
        errors: List to append errors to

    Returns:
        True if successful, False otherwise
    """
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
        for report in reports:
            _process_render_report(report, args, warnings, errors)
        return True
    except RenderError as e:
        errors.append(f"Render error in {spec_name}: {e}")
        return False


def _validate_normalization(
    workflow: dict[str, Any],
    workflow_json: str,
    spec_name: str,
    args: argparse.Namespace,
    warnings: list[str],
    errors: list[str]
) -> None:
    """Validate workflow normalization.

    Args:
        workflow: Workflow dict
        workflow_json: Original workflow JSON string
        spec_name: Workflow name
        args: CLI arguments
        warnings: List to append warnings to
        errors: List to append errors to
    """
    try:
        normalized = normalize_json(workflow)
        if workflow_json.strip() != normalized.strip():
            msg = f"Workflow {spec_name} is not normalized (run through normalize_json)"
            if args.strict:
                errors.append(msg)
            else:
                warnings.append(msg)
    except Exception as e:
        warnings.append(f"Failed to check normalization for {spec_name}: {e}")


def _check_problematic_fields(
    workflow: dict[str, Any],
    spec_name: str,
    warnings: list[str]
) -> None:
    """Check for n8n-managed and problematic fields.

    Args:
        workflow: Workflow dict
        spec_name: Workflow name
        warnings: List to append warnings to
    """
    problematic_fields = []

    for field in N8N_MANAGED_FIELDS:
        if field in workflow:
            problematic_fields.append(field)

    for field in NULLABLE_FIELDS:
        if field in workflow:
            value = workflow.get(field)
            if value is None or value == {}:
                problematic_fields.append(f"{field} (null/empty)")

    if problematic_fields:
        msg = (
            f"Workflow {spec_name} contains n8n-managed fields that will cause "
            f"deployment errors: {', '.join(problematic_fields)}. "
            f"These fields are automatically stripped during deployment, but you should "
            f"remove them from the workflow file. "
            f"Re-export with: n8n-gitops export --names \"{spec_name}\" [--externalize-code]"
        )
        warnings.append(msg)


def _validate_single_workflow(
    spec: Any,
    snapshot: GitSnapshot,
    n8n_root: str,
    args: argparse.Namespace,
    warnings: list[str],
    errors: list[str]
) -> None:
    """Validate a single workflow.

    Args:
        spec: Workflow spec from manifest
        snapshot: Git snapshot
        n8n_root: n8n directory path
        args: CLI arguments
        warnings: List to append warnings to
        errors: List to append errors to
    """
    workflow_path = f"{n8n_root}/{spec.file}"
    logger.info(f"\nValidating workflow: {spec.name}")
    logger.info(f"  File: {workflow_path}")

    # Load workflow file
    workflow = _load_workflow_file(snapshot, workflow_path, errors)
    if not workflow:
        return

    workflow_json = snapshot.read_text(workflow_path)

    # Render and validate
    if not _render_and_validate_workflow(
        workflow, snapshot, n8n_root, args, spec.name, warnings, errors
    ):
        return

    # Validate normalization
    _validate_normalization(workflow, workflow_json, spec.name, args, warnings, errors)

    # Check for problematic fields
    _check_problematic_fields(workflow, spec.name, warnings)

    logger.info(f"  ✓ Workflow validation passed: {spec.name}")


def _validate_env_schema(
    snapshot: GitSnapshot,
    n8n_root: str,
    args: argparse.Namespace,
    warnings: list[str],
    errors: list[str]
) -> None:
    """Validate environment schema.

    Args:
        snapshot: Git snapshot
        n8n_root: n8n directory path
        args: CLI arguments
        warnings: List to append warnings to
        errors: List to append errors to
    """
    logger.info("\nValidating environment schema...")
    try:
        env_issues = validate_env_schema(snapshot, n8n_root)
        if env_issues:
            for issue in env_issues:
                if args.strict:
                    errors.append(issue)
                else:
                    warnings.append(issue)
        else:
            logger.info("  ✓ Environment schema validation passed")
    except ValidationError as e:
        errors.append(f"Environment schema error: {e}")


def run_validate(args: argparse.Namespace) -> None:
    """Run validation on workflows and manifests.

    Args:
        args: CLI arguments

    Raises:
        SystemExit: If validation fails
    """
    # Setup
    repo_root = Path(args.repo_root).resolve()
    n8n_root = "n8n"
    snapshot = create_snapshot(repo_root, args.git_ref)
    warnings: list[str] = []
    errors: list[str] = []

    # Log start
    logger.info(f"Validating n8n-gitops project at {repo_root}")
    if args.git_ref:
        logger.info(f"Using git ref: {args.git_ref}")
    logger.info("")

    # Load manifest
    manifest = _load_manifest_safe(snapshot, n8n_root, errors)
    if not manifest:
        _print_results(warnings, errors, args.strict)
        raise SystemExit(1)

    # Validate each workflow
    for spec in manifest.workflows:
        _validate_single_workflow(spec, snapshot, n8n_root, args, warnings, errors)

    # Validate environment schema
    _validate_env_schema(snapshot, n8n_root, args, warnings, errors)

    # Print results
    logger.info("")
    _print_results(warnings, errors, args.strict)

    # Exit with appropriate code
    if errors or (args.strict and warnings):
        raise SystemExit(1)

    logger.info("\n✓ Validation successful!")
    raise SystemExit(0)


def _print_results(warnings: list[str], errors: list[str], strict: bool) -> None:
    """Print validation results.

    Args:
        warnings: List of warnings
        errors: List of errors
        strict: Whether strict mode is enabled
    """
    if warnings:
        logger.warning("Warnings:")
        for warning in warnings:
            logger.warning(f"  ⚠ {warning}")
        if strict:
            logger.warning("\n(Warnings treated as errors in strict mode)")

    if errors:
        logger.error("\nErrors:")
        for error in errors:
            logger.error(f"  ✗ {error}")
