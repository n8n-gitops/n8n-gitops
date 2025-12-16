"""JSON normalization for deterministic output."""

import json
from typing import Any


def normalize_obj(obj: Any) -> Any:
    """Recursively normalize an object for deterministic JSON output.

    Sorts dictionary keys recursively and ensures consistent structure.

    Args:
        obj: Object to normalize (dict, list, or primitive)

    Returns:
        Normalized object with sorted keys
    """
    if isinstance(obj, dict):
        # Sort dictionary keys and recursively normalize values
        return {k: normalize_obj(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        # Recursively normalize list items
        return [normalize_obj(item) for item in obj]
    else:
        # Return primitives as-is
        return obj


def normalize_json(obj: Any) -> str:
    """Convert object to normalized JSON string.

    Produces deterministic output with:
    - Stable key ordering (recursive)
    - 2-space indentation
    - Newline at EOF
    - LF line endings

    Args:
        obj: Object to serialize to JSON

    Returns:
        Normalized JSON string with trailing newline
    """
    normalized = normalize_obj(obj)
    # Use indent=2 for readability, sort_keys is handled by normalize_obj
    # ensure_ascii=False to preserve unicode characters
    json_str = json.dumps(normalized, indent=2, ensure_ascii=False)
    # Ensure newline at EOF
    if not json_str.endswith("\n"):
        json_str += "\n"
    return json_str


def strip_volatile_fields(obj: dict[str, Any], fields: list[str] | None = None) -> dict[str, Any]:
    """Strip volatile fields from workflow JSON.

    This is configurable via the fields parameter. By default, no fields are stripped
    unless explicitly specified.

    Args:
        obj: Workflow object to strip fields from
        fields: List of field paths to remove (e.g., ["id", "createdAt", "updatedAt"])

    Returns:
        New dictionary with specified fields removed
    """
    if fields is None:
        fields = []

    # Create a deep copy to avoid modifying the original
    import copy
    result = copy.deepcopy(obj)

    # Remove top-level fields
    for field in fields:
        if field in result:
            del result[field]

    return result
