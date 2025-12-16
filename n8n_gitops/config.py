"""Configuration management for n8n-gitops."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from n8n_gitops.exceptions import ConfigError


@dataclass
class AuthConfig:
    """Authentication configuration."""
    api_url: str
    api_key: str


def load_auth(repo_root: Path, args: Optional[object] = None) -> AuthConfig:
    """Load authentication configuration from multiple sources.

    Priority order:
    1. CLI flags (--api-url, --api-key)
    2. Environment variables (N8N_API_URL, N8N_API_KEY)
    3. .n8n-auth file in repo root

    Args:
        repo_root: Path to the repository root
        args: CLI arguments namespace

    Returns:
        AuthConfig with api_url and api_key

    Raises:
        ConfigError: If authentication credentials are incomplete
    """
    api_url: Optional[str] = None
    api_key: Optional[str] = None

    # Priority 1: CLI flags
    if args and hasattr(args, "api_url") and args.api_url:
        api_url = args.api_url
    if args and hasattr(args, "api_key") and args.api_key:
        api_key = args.api_key

    # Priority 2: Environment variables
    if not api_url and os.getenv("N8N_API_URL"):
        api_url = os.getenv("N8N_API_URL")
    if not api_key and os.getenv("N8N_API_KEY"):
        api_key = os.getenv("N8N_API_KEY")

    # Priority 3: .n8n-auth file
    n8n_auth_path = repo_root / ".n8n-auth"
    if n8n_auth_path.exists():
        auth_data = _parse_n8n_auth(n8n_auth_path)
        if not api_url and "N8N_API_URL" in auth_data:
            api_url = auth_data["N8N_API_URL"]
        if not api_key and "N8N_API_KEY" in auth_data:
            api_key = auth_data["N8N_API_KEY"]

    # Validate that we have both required values
    if not api_url:
        raise ConfigError(
            "N8N_API_URL not found. Provide via --api-url, N8N_API_URL env var, "
            "or .n8n-auth file"
        )
    if not api_key:
        raise ConfigError(
            "N8N_API_KEY not found. Provide via --api-key, N8N_API_KEY env var, "
            "or .n8n-auth file"
        )

    return AuthConfig(api_url=api_url, api_key=api_key)


def _parse_n8n_auth(path: Path) -> dict[str, str]:
    """Parse .n8n-auth file.

    Supports simple KEY=VALUE format (dotenv style).

    Args:
        path: Path to .n8n-auth file

    Returns:
        Dictionary of key-value pairs
    """
    result: dict[str, str] = {}
    content = path.read_text()

    for line in content.splitlines():
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Parse KEY=VALUE
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Remove quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            if key and value:
                result[key] = value

    return result


def load_dotenv_file(env_file: Path) -> None:
    """Load environment variables from a .env file.

    Args:
        env_file: Path to .env file
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        # python-dotenv is optional
        pass
