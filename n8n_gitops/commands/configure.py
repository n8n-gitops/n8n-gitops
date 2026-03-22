"""Configure command implementation."""

import argparse
from pathlib import Path

from n8n_gitops import logger
from n8n_gitops.config import save_config_profile


def run_configure(args: argparse.Namespace) -> None:
    """Save a named config profile.

    Args:
        args: CLI arguments with config, api_url, api_key, insecure
    """
    repo_root = Path(args.repo_root).resolve()
    config_path = save_config_profile(
        repo_root=repo_root,
        name=args.config,
        api_url=args.api_url,
        api_key=args.api_key,
        insecure=args.insecure,
    )
    logger.info(f"✓ Saved config profile '{args.config}' to {config_path}")
