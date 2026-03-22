"""Configuration management for n8n-gitops."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from n8n_gitops.exceptions import ConfigError

CONFIG_FILENAME = ".n8n-gitops.yaml"


@dataclass
class AuthConfig:
    """Authentication configuration."""
    api_url: str
    api_key: str
    insecure: bool = False


def save_config_profile(
    repo_root: Path,
    name: str,
    api_url: str,
    api_key: str,
    insecure: bool = False,
) -> Path:
    """Save a named config profile to .n8n-gitops.yaml.

    Args:
        repo_root: Path to the repository root
        name: Profile name
        api_url: n8n API URL
        api_key: n8n API key
        insecure: Disable SSL verification

    Returns:
        Path to the config file
    """
    config_path = repo_root / CONFIG_FILENAME
    configs: dict[str, Any] = {}

    if config_path.exists():
        content = config_path.read_text()
        configs = yaml.safe_load(content) or {}

    configs[name] = {
        "api_url": api_url,
        "api_key": api_key,
        "insecure": insecure,
    }

    config_path.write_text(yaml.dump(configs, default_flow_style=False, sort_keys=False))
    return config_path


def load_config_profile(repo_root: Path, name: str) -> dict[str, Any]:
    """Load a named config profile from .n8n-gitops.yaml.

    Args:
        repo_root: Path to the repository root
        name: Profile name

    Returns:
        Profile dict with api_url, api_key, insecure

    Raises:
        ConfigError: If config file or profile not found
    """
    config_path = repo_root / CONFIG_FILENAME
    if not config_path.exists():
        raise ConfigError(
            f"{CONFIG_FILENAME} not found in {repo_root}. "
            f"Run: n8n-gitops configure --config {name} --api-url URL --api-key KEY"
        )

    configs = yaml.safe_load(config_path.read_text()) or {}
    if name not in configs:
        available = ", ".join(configs.keys()) if configs else "none"
        raise ConfigError(
            f"Config profile '{name}' not found in {CONFIG_FILENAME}. "
            f"Available profiles: {available}"
        )

    return configs[name]


def load_auth(repo_root: Path, args: Optional[object] = None) -> AuthConfig:
    """Load authentication configuration from multiple sources.

    Priority order:
    1. CLI flags (--api-url, --api-key)
    2. Config profile (--config name)
    3. Environment variables (N8N_API_URL, N8N_API_KEY)

    Args:
        repo_root: Path to the repository root
        args: CLI arguments namespace

    Returns:
        AuthConfig with api_url, api_key, and insecure

    Raises:
        ConfigError: If authentication credentials are incomplete
    """
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    insecure: bool = False

    # Priority 1: CLI flags
    if args and hasattr(args, "api_url") and args.api_url:
        api_url = args.api_url
    if args and hasattr(args, "api_key") and args.api_key:
        api_key = args.api_key
    if args and hasattr(args, "insecure") and args.insecure:
        insecure = True

    # Priority 2: Config profile
    config_name = getattr(args, "config", None) if args else None
    if config_name:
        profile = load_config_profile(repo_root, config_name)
        if not api_url and profile.get("api_url"):
            api_url = profile["api_url"]
        if not api_key and profile.get("api_key"):
            api_key = profile["api_key"]
        if not insecure and profile.get("insecure"):
            insecure = True

    # Priority 3: Environment variables
    if not api_url and os.getenv("N8N_API_URL"):
        api_url = os.getenv("N8N_API_URL")
    if not api_key and os.getenv("N8N_API_KEY"):
        api_key = os.getenv("N8N_API_KEY")

    # Validate that we have both required values
    if not api_url:
        raise ConfigError(
            "N8N_API_URL not found. Provide via --api-url, --config, "
            "or N8N_API_URL env var"
        )
    if not api_key:
        raise ConfigError(
            "N8N_API_KEY not found. Provide via --api-key, --config, "
            "or N8N_API_KEY env var"
        )

    return AuthConfig(api_url=api_url, api_key=api_key, insecure=insecure)
