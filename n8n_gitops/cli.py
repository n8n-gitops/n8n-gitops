"""CLI entrypoint for n8n-gitops."""

import argparse
import sys

from n8n_gitops import __version__
from n8n_gitops import logger


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add common arguments to a parser.

    Args:
        parser: The argument parser to add arguments to
    """
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Suppress info messages, only show warnings and errors",
    )
    parser.add_argument(
        "--break-on-error",
        action="store_true",
        help="Stop execution immediately on first error",
    )


def _add_api_args(parser: argparse.ArgumentParser) -> None:
    """Add API connection arguments to a parser.

    Args:
        parser: The argument parser to add arguments to
    """
    parser.add_argument(
        "--config",
        type=str,
        help="Named config profile from .n8n-gitops.yaml",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        help="n8n API URL (overrides config profile and env)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="n8n API key (overrides config profile and env)",
    )
    parser.add_argument(
        "--repo-root",
        type=str,
        default=".",
        help="Repository root path (default: current directory)",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable SSL certificate verification (for self-signed certificates)",
    )


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="n8n-gitops",
        description=f"GitOps CLI for n8n Community Edition v{__version__}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # create-project command
    create_parser = subparsers.add_parser(
        "create-project",
        help="Create a new n8n-gitops project structure",
    )
    create_parser.add_argument(
        "path",
        type=str,
        help="Path where the project should be created",
    )
    _add_common_args(create_parser)

    # validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate workflows and manifests",
    )
    validate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Turn warnings into failures",
    )
    validate_parser.add_argument(
        "--enforce-no-inline-code",
        action="store_true",
        help="Fail if inline code is found in workflow nodes",
    )
    validate_parser.add_argument(
        "--enforce-checksum",
        action="store_true",
        help="Fail on checksum mismatch",
    )
    validate_parser.add_argument(
        "--require-checksum",
        action="store_true",
        help="Require checksums in all include directives",
    )
    validate_parser.add_argument(
        "--git-ref",
        type=str,
        help="Git ref to validate from (tag, branch, commit)",
    )
    validate_parser.add_argument(
        "--repo-root",
        type=str,
        default=".",
        help="Repository root path (default: current directory)",
    )
    _add_common_args(validate_parser)

    # configure command
    configure_parser = subparsers.add_parser(
        "configure",
        help="Save a named config profile to .n8n-gitops.yaml",
    )
    configure_parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Profile name (e.g., dev, staging, prod)",
    )
    configure_parser.add_argument(
        "--api-url",
        type=str,
        required=True,
        help="n8n API URL",
    )
    configure_parser.add_argument(
        "--api-key",
        type=str,
        required=True,
        help="n8n API key",
    )
    configure_parser.add_argument(
        "--repo-root",
        type=str,
        default=".",
        help="Repository root path (default: current directory)",
    )
    configure_parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable SSL certificate verification (for self-signed certificates)",
    )
    _add_common_args(configure_parser)

    # export command
    export_parser = subparsers.add_parser(
        "export",
        help="Export all workflows from n8n instance (mirror mode)",
    )
    _add_api_args(export_parser)
    _add_common_args(export_parser)

    # deploy command
    deploy_parser = subparsers.add_parser(
        "deploy",
        help="Deploy workflows to n8n instance",
    )
    deploy_parser.add_argument(
        "--git-ref",
        type=str,
        help="Git ref to deploy from (tag, branch, commit)",
    )
    deploy_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deployed without making changes",
    )
    deploy_parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete workflows in n8n that are not in the manifest",
    )
    _add_api_args(deploy_parser)
    _add_common_args(deploy_parser)

    # rollback command
    rollback_parser = subparsers.add_parser(
        "rollback",
        help="Rollback to a previous version (alias for deploy --git-ref)",
    )
    rollback_parser.add_argument(
        "--git-ref",
        type=str,
        required=True,
        help="Git ref to rollback to (tag, branch, commit)",
    )
    rollback_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deployed without making changes",
    )
    _add_api_args(rollback_parser)
    _add_common_args(rollback_parser)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Configure logger with CLI flags
    logger.configure(silent=args.silent, break_on_error=args.break_on_error)

    try:
        if args.command == "configure":
            from n8n_gitops.commands.configure import run_configure
            run_configure(args)
        elif args.command == "create-project":
            from n8n_gitops.commands.create_project import run_create_project
            run_create_project(args)
        elif args.command == "validate":
            from n8n_gitops.commands.validate import run_validate
            run_validate(args)
        elif args.command == "export":
            from n8n_gitops.commands.export_workflows import run_export
            run_export(args)
        elif args.command == "deploy":
            from n8n_gitops.commands.deploy import run_deploy
            run_deploy(args)
        elif args.command == "rollback":
            from n8n_gitops.commands.rollback import run_rollback
            run_rollback(args)
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
