"""Rollback command implementation."""

import argparse

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
        print("Error: --git-ref is required for rollback")
        raise SystemExit(1)

    print(f"Rolling back to git ref: {args.git_ref}")
    print()

    # Delegate to deploy
    run_deploy(args)
