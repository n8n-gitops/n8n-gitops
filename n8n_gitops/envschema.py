"""Environment schema validation."""

import json
import os
from typing import Any

from n8n_gitops.exceptions import ValidationError
from n8n_gitops.gitref import Snapshot


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
    if not snapshot.exists(schema_path):
        # No schema file, skip validation
        return []

    try:
        schema_content = snapshot.read_text(schema_path)
        schema = json.loads(schema_content)
    except Exception as e:
        raise ValidationError(f"Failed to load env schema from {schema_path}: {e}")

    if not isinstance(schema, dict):
        raise ValidationError("env.schema.json must be a JSON object")

    # Get required variables
    required_vars = schema.get("required", [])
    if not isinstance(required_vars, list):
        raise ValidationError("'required' in env.schema.json must be a list")

    # Get variable definitions
    vars_schema = schema.get("vars", {})
    if not isinstance(vars_schema, dict):
        raise ValidationError("'vars' in env.schema.json must be an object")

    # Collect environment variables from process env
    env_vars = dict(os.environ)

    # Optionally load from .env file if provided
    if env_file:
        from n8n_gitops.config import load_dotenv_file
        from pathlib import Path
        load_dotenv_file(Path(env_file))
        env_vars = dict(os.environ)

    issues: list[str] = []

    # Check required variables
    for var_name in required_vars:
        if not isinstance(var_name, str):
            raise ValidationError(f"Required variable name must be string: {var_name}")
        if var_name not in env_vars or not env_vars[var_name]:
            issues.append(f"Required environment variable '{var_name}' is not set")

    # Validate variable types/patterns if defined
    for var_name, var_spec in vars_schema.items():
        if not isinstance(var_spec, dict):
            continue

        value = env_vars.get(var_name)
        if value is None:
            continue

        # Check pattern if specified
        if "pattern" in var_spec:
            import re
            pattern = var_spec["pattern"]
            if not re.match(pattern, value):
                issues.append(
                    f"Environment variable '{var_name}' does not match pattern: {pattern}"
                )

        # Check type if specified
        if "type" in var_spec:
            var_type = var_spec["type"]
            if var_type == "integer":
                try:
                    int(value)
                except ValueError:
                    issues.append(f"Environment variable '{var_name}' must be an integer")
            elif var_type == "boolean":
                if value.lower() not in ("true", "false", "1", "0", "yes", "no"):
                    issues.append(
                        f"Environment variable '{var_name}' must be a boolean "
                        "(true/false, 1/0, yes/no)"
                    )

    return issues
