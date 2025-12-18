"""Rollback command implementation."""

import argparse

from n8n_gitops import logger
from n8n_gitops.commands.deploy import run_deploy


def run_rollback(args: argparse.Namespace) -> None:
    """Rollback to a previous version.

    This is an alias for deploy --git-ref <ref>.

    Args:
        args: CLI arguments with git_ref required

    Raises:
        SystemExit: If rollback fails
    """
    # Rollback is just deploy with a required git-ref
    if not args.git_ref:
        logger.critical("Error: --git-ref is required for rollback")

    logger.info(f"Rolling back to git ref: {args.git_ref}")
    logger.info("")

    # Delegate to deploy
    run_deploy(args)
