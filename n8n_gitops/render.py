"""Workflow rendering with code include support."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from n8n_gitops.exceptions import RenderError
from n8n_gitops.gitref import Snapshot

# Regex for include directive
# Format: @@n8n-gitops:include <path> [sha256=<hex>]
INCLUDE_DIRECTIVE_PATTERN = re.compile(
    r"^@@n8n-gitops:include\s+([^\s]+)(?:\s+sha256=([a-fA-F0-9]{64}))?\s*$"
)

# Code field names to check (in order)
CODE_FIELD_NAMES = [
    "pythonCode",
    "jsCode",
    "code",
    "functionCode",
]


@dataclass
class RenderOptions:
    """Options for rendering workflows."""
    enforce_no_inline_code: bool = False
    enforce_checksum: bool = False
    require_checksum: bool = False
    add_generated_header: bool = True


@dataclass
class RenderReport:
    """Report for a single code include operation."""
    node_name: str
    node_id: str
    field: str
    include_path: str | None = None
    sha256_expected: str | None = None
    sha256_actual: str | None = None
    status: str = "ok"  # "included", "checksum_mismatch", "inline_code", "missing_file"


def parse_include_directive(text: str) -> tuple[str, str | None] | None:
    """Parse include directive from text.

    Args:
        text: Text that may contain include directive

    Returns:
        Tuple of (path, sha256) if directive found, None otherwise
        sha256 may be None if not specified
    """
    if not text or not isinstance(text, str):
        return None

    text = text.strip()
    match = INCLUDE_DIRECTIVE_PATTERN.match(text)
    if not match:
        return None

    path = match.group(1)
    sha256 = match.group(2)  # May be None

    return (path, sha256)


def validate_include_path(path: str, n8n_root: str = "n8n") -> None:
    """Validate that include path is safe and under n8n/scripts/.

    Args:
        path: Relative path from include directive
        n8n_root: n8n root directory

    Raises:
        RenderError: If path is invalid or unsafe
    """
    # Check for absolute paths
    if Path(path).is_absolute():
        raise RenderError(f"Include path cannot be absolute: {path}")

    # Check for .. (path traversal)
    if ".." in Path(path).parts:
        raise RenderError(f"Include path cannot contain '..': {path}")

    # Ensure path starts with scripts/
    expected_prefix = "scripts/"
    if not path.startswith(expected_prefix):
        raise RenderError(
            f"Include path must be under scripts/: {path} "
            f"(expected to start with '{expected_prefix}')"
        )


def compute_sha256(content: bytes) -> str:
    """Compute SHA256 hash of content.

    Args:
        content: Raw file bytes

    Returns:
        Lowercase hexadecimal SHA256 hash
    """
    return hashlib.sha256(content).hexdigest()


def _handle_inline_code(
    node_name: str,
    node_id: str,
    field_name: str,
    options: RenderOptions
) -> RenderReport:
    """Handle inline code (not an include directive).

    Args:
        node_name: Name of the node
        node_id: ID of the node
        field_name: Name of the code field
        options: Render options

    Returns:
        RenderReport for inline code

    Raises:
        RenderError: If enforce_no_inline_code is enabled
    """
    if options.enforce_no_inline_code:
        raise RenderError(
            f"Inline code found in node '{node_name}' field '{field_name}' "
            f"(enforce_no_inline_code is enabled)"
        )
    return RenderReport(
        node_name=node_name,
        node_id=node_id,
        field=field_name,
        status="inline_code",
    )


def _read_include_file(
    full_path: str,
    snapshot: Snapshot,
    node_name: str,
    field_name: str
) -> tuple[bytes, str]:
    """Read and decode include file.

    Args:
        full_path: Full path to include file
        snapshot: Snapshot to read from
        node_name: Name of the node (for error messages)
        field_name: Name of the code field (for error messages)

    Returns:
        Tuple of (file_bytes, file_content)

    Raises:
        RenderError: If file not found or cannot be read
    """
    if not snapshot.exists(full_path):
        raise RenderError(
            f"Include file not found: {full_path} "
            f"(referenced in node '{node_name}' field '{field_name}')"
        )

    try:
        file_bytes = snapshot.read_bytes(full_path)
        file_content = file_bytes.decode("utf-8")
        return file_bytes, file_content
    except Exception as e:
        raise RenderError(f"Failed to read include file {full_path}: {e}")


def _validate_checksum(
    node_name: str,
    node_id: str,
    field_name: str,
    include_path: str,
    expected_sha256: str | None,
    actual_sha256: str,
    options: RenderOptions
) -> RenderReport | None:
    """Validate checksum and create report if mismatch.

    Args:
        node_name: Name of the node
        node_id: ID of the node
        field_name: Name of the code field
        include_path: Path to include file
        expected_sha256: Expected SHA256 hash (may be None)
        actual_sha256: Actual SHA256 hash
        options: Render options

    Returns:
        RenderReport if checksum mismatch, None otherwise

    Raises:
        RenderError: If checksum validation fails and enforce_checksum is enabled
        RenderError: If checksum required but not provided
    """
    if expected_sha256:
        if actual_sha256 != expected_sha256:
            if options.enforce_checksum:
                raise RenderError(
                    f"Checksum mismatch for {include_path} in node '{node_name}': "
                    f"expected {expected_sha256}, got {actual_sha256}"
                )
            return RenderReport(
                node_name=node_name,
                node_id=node_id,
                field=field_name,
                include_path=include_path,
                sha256_expected=expected_sha256,
                sha256_actual=actual_sha256,
                status="checksum_mismatch",
            )
    else:
        if options.require_checksum:
            raise RenderError(
                f"Checksum required but not provided for {include_path} "
                f"in node '{node_name}' (require_checksum is enabled)"
            )
    return None


def _process_include_directive(
    node_name: str,
    node_id: str,
    field_name: str,
    include_path: str,
    expected_sha256: str | None,
    snapshot: Snapshot,
    n8n_root: str,
    options: RenderOptions
) -> tuple[str, list[RenderReport]]:
    """Process include directive and return replacement content.

    Args:
        node_name: Name of the node
        node_id: ID of the node
        field_name: Name of the code field
        include_path: Path to include file
        expected_sha256: Expected SHA256 hash (may be None)
        snapshot: Snapshot to read from
        n8n_root: Path to n8n directory
        options: Render options

    Returns:
        Tuple of (file_content, reports)

    Raises:
        RenderError: If include processing fails
    """
    # Validate path
    validate_include_path(include_path, n8n_root)

    # Build full path
    full_path = f"{n8n_root}/{include_path}"

    # Read file
    file_bytes, file_content = _read_include_file(full_path, snapshot, node_name, field_name)

    # Compute actual hash
    actual_sha256 = compute_sha256(file_bytes)

    # Validate checksum
    reports: list[RenderReport] = []
    checksum_report = _validate_checksum(
        node_name, node_id, field_name, include_path,
        expected_sha256, actual_sha256, options
    )
    if checksum_report:
        reports.append(checksum_report)

    # Add success report
    reports.append(
        RenderReport(
            node_name=node_name,
            node_id=node_id,
            field=field_name,
            include_path=include_path,
            sha256_expected=expected_sha256,
            sha256_actual=actual_sha256,
            status="included",
        )
    )

    return file_content, reports


def _process_code_field(
    node: dict[str, Any],
    node_name: str,
    node_id: str,
    field_name: str,
    snapshot: Snapshot,
    n8n_root: str,
    options: RenderOptions
) -> list[RenderReport]:
    """Process a single code field (either inline or include directive).

    Args:
        node: Node dictionary
        node_name: Name of the node
        node_id: ID of the node
        field_name: Name of the code field
        snapshot: Snapshot to read from
        n8n_root: Path to n8n directory
        options: Render options

    Returns:
        List of render reports

    Raises:
        RenderError: If processing fails
    """
    parameters = node.get("parameters", {})
    if not isinstance(parameters, dict):
        return []

    if field_name not in parameters:
        return []

    field_value = parameters[field_name]
    if not isinstance(field_value, str):
        return []

    # Try to parse as include directive
    parsed = parse_include_directive(field_value)

    if parsed is None:
        # Not an include directive - this is inline code
        report = _handle_inline_code(node_name, node_id, field_name, options)
        return [report]

    # Process include directive
    include_path, expected_sha256 = parsed
    file_content, reports = _process_include_directive(
        node_name, node_id, field_name, include_path, expected_sha256,
        snapshot, n8n_root, options
    )

    # Replace directive with file content
    parameters[field_name] = file_content

    return reports


def _process_node(
    node: dict[str, Any],
    snapshot: Snapshot,
    n8n_root: str,
    options: RenderOptions
) -> list[RenderReport]:
    """Process all code fields in a node.

    Args:
        node: Node dictionary
        snapshot: Snapshot to read from
        n8n_root: Path to n8n directory
        options: Render options

    Returns:
        List of render reports

    Raises:
        RenderError: If processing fails
    """
    if not isinstance(node, dict):
        return []

    node_name = node.get("name", "<unnamed>")
    node_id = node.get("id", "<no-id>")

    reports: list[RenderReport] = []
    for field_name in CODE_FIELD_NAMES:
        field_reports = _process_code_field(
            node, node_name, node_id, field_name,
            snapshot, n8n_root, options
        )
        reports.extend(field_reports)

    return reports


def render_workflow_json(
    workflow: dict[str, Any],
    snapshot: Snapshot,
    *,
    n8n_root: str = "n8n",
    git_ref: str | None = None,
    options: RenderOptions | None = None,
) -> tuple[dict[str, Any], list[RenderReport]]:
    """Render workflow JSON by processing include directives.

    Args:
        workflow: Workflow JSON object
        snapshot: Snapshot to read includes from
        n8n_root: Path to n8n directory
        git_ref: Git ref being rendered (for error messages)
        options: Render options

    Returns:
        Tuple of (rendered_workflow, reports)

    Raises:
        RenderError: If rendering fails due to validation errors
    """
    if options is None:
        options = RenderOptions()

    # Create deep copy to avoid modifying original
    import copy
    rendered = copy.deepcopy(workflow)

    # Process nodes
    nodes = rendered.get("nodes", [])
    if not isinstance(nodes, list):
        return rendered, []

    reports: list[RenderReport] = []
    for node in nodes:
        node_reports = _process_node(node, snapshot, n8n_root, options)
        reports.extend(node_reports)

    return rendered, reports
