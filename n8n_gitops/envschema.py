"""Environment schema validation."""

import json
import os
from typing import Any

from n8n_gitops.exceptions import ValidationError
from n8n_gitops.gitref import Snapshot


def _load_env_schema(snapshot: Snapshot, schema_path: str) -> dict[str, Any] | None:
    """Load environment schema from file.

    Args:
        snapshot: Snapshot to read from
        schema_path: Path to schema file

    Returns:
        Parsed schema or None if file doesn't exist

    Raises:
        ValidationError: If schema is invalid
    """
    if not snapshot.exists(schema_path):
        return None

    try:
        schema_content = snapshot.read_text(schema_path)
        schema = json.loads(schema_content)
    except Exception as e:
        raise ValidationError(f"Failed to load env schema from {schema_path}: {e}")

    if not isinstance(schema, dict):
        raise ValidationError("env.schema.json must be a JSON object")

    return schema


def _validate_schema_structure(schema: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    """Validate schema structure and extract required vars and vars definitions.

    Args:
        schema: Parsed schema dictionary

    Returns:
        Tuple of (required_vars, vars_schema)

    Raises:
        ValidationError: If schema structure is invalid
    """
    required_vars = schema.get("required", [])
    if not isinstance(required_vars, list):
        raise ValidationError("'required' in env.schema.json must be a list")

    vars_schema = schema.get("vars", {})
    if not isinstance(vars_schema, dict):
        raise ValidationError("'vars' in env.schema.json must be an object")

    return required_vars, vars_schema


def _get_environment_variables(env_file: str | None) -> dict[str, str]:
    """Get environment variables from process env and optionally from .env file.

    Args:
        env_file: Optional path to .env file

    Returns:
        Dictionary of environment variables
    """
    env_vars = dict(os.environ)

    if env_file:
        from pathlib import Path
        from n8n_gitops.config import load_dotenv_file
        load_dotenv_file(Path(env_file))
        env_vars = dict(os.environ)

    return env_vars


def _check_required_variables(
    required_vars: list[str],
    env_vars: dict[str, str]
) -> list[str]:
    """Check that all required variables are set.

    Args:
        required_vars: List of required variable names
        env_vars: Dictionary of environment variables

    Returns:
        List of issues found

    Raises:
        ValidationError: If required variable name is not a string
    """
    issues: list[str] = []
    for var_name in required_vars:
        if not isinstance(var_name, str):
            raise ValidationError(f"Required variable name must be string: {var_name}")
        if var_name not in env_vars or not env_vars[var_name]:
            issues.append(f"Required environment variable '{var_name}' is not set")
    return issues


def _validate_variable_pattern(var_name: str, value: str, pattern: str) -> str | None:
    """Validate variable value against pattern.

    Args:
        var_name: Variable name
        value: Variable value
        pattern: Regex pattern to match

    Returns:
        Error message if validation fails, None otherwise
    """
    import re
    if not re.match(pattern, value):
        return f"Environment variable '{var_name}' does not match pattern: {pattern}"
    return None


def _validate_variable_type(var_name: str, value: str, var_type: str) -> str | None:
    """Validate variable value type.

    Args:
        var_name: Variable name
        value: Variable value
        var_type: Expected type (integer or boolean)

    Returns:
        Error message if validation fails, None otherwise
    """
    if var_type == "integer":
        try:
            int(value)
        except ValueError:
            return f"Environment variable '{var_name}' must be an integer"
    elif var_type == "boolean":
        if value.lower() not in ("true", "false", "1", "0", "yes", "no"):
            return (
                f"Environment variable '{var_name}' must be a boolean "
                "(true/false, 1/0, yes/no)"
            )
    return None


def _validate_variable(
    var_name: str,
    var_spec: dict[str, Any],
    env_vars: dict[str, str]
) -> list[str]:
    """Validate a single variable against its specification.

    Args:
        var_name: Variable name
        var_spec: Variable specification
        env_vars: Dictionary of environment variables

    Returns:
        List of issues found
    """
    if not isinstance(var_spec, dict):
        return []

    value = env_vars.get(var_name)
    if value is None:
        return []

    issues: list[str] = []

    # Check pattern
    if "pattern" in var_spec:
        error = _validate_variable_pattern(var_name, value, var_spec["pattern"])
        if error:
            issues.append(error)

    # Check type
    if "type" in var_spec:
        error = _validate_variable_type(var_name, value, var_spec["type"])
        if error:
            issues.append(error)

    return issues


def _validate_variables(
    vars_schema: dict[str, Any],
    env_vars: dict[str, str]
) -> list[str]:
    """Validate all variables against their specifications.

    Args:
        vars_schema: Variable specifications
        env_vars: Dictionary of environment variables

    Returns:
        List of issues found
    """
    issues: list[str] = []
    for var_name, var_spec in vars_schema.items():
        issues.extend(_validate_variable(var_name, var_spec, env_vars))
    return issues


def validate_env_schema(
    snapshot: Snapshot,
    n8n_root: str = "n8n",
    env_file: str | None = None,
) -> list[str]:
    """Validate environment variables against schema.

    Args:
        snapshot: Snapshot to read schema from
        n8n_root: Path to n8n directory
        env_file: Optional path to .env file

    Returns:
        List of validation warnings/errors

    Raises:
        ValidationError: If schema is invalid or required vars are missing
    """
    schema_path = f"{n8n_root}/manifests/env.schema.json"

    # Load schema
    schema = _load_env_schema(snapshot, schema_path)
    if schema is None:
        return []

    # Validate schema structure
    required_vars, vars_schema = _validate_schema_structure(schema)

    # Get environment variables
    env_vars = _get_environment_variables(env_file)

    # Validate
    issues: list[str] = []
    issues.extend(_check_required_variables(required_vars, env_vars))
    issues.extend(_validate_variables(vars_schema, env_vars))

    return issues
