"""CLI entrypoint for n8n-gitops."""

import argparse
import sys
from pathlib import Path
from typing import Any

from n8n_gitops import __version__


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="n8n-gitops",
        description="GitOps CLI for n8n Community Edition",
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

    # export command
    export_parser = subparsers.add_parser(
        "export",
        help="Export workflows from n8n instance",
    )
    export_parser.add_argument(
        "--all",
        action="store_true",
        help="Export all workflows",
    )
    export_parser.add_argument(
        "--names",
        type=str,
        help="Comma-separated list of workflow names to export",
    )
    export_parser.add_argument(
        "--from-manifest",
        action="store_true",
        help="Export only workflows listed in manifest",
    )
    export_parser.add_argument(
        "--externalize-code",
        action="store_true",
        help="Extract inline code to separate script files with include directives",
    )
    export_parser.add_argument(
        "--api-url",
        type=str,
        help="n8n API URL (overrides env and .n8n-auth)",
    )
    export_parser.add_argument(
        "--api-key",
        type=str,
        help="n8n API key (overrides env and .n8n-auth)",
    )
    export_parser.add_argument(
        "--repo-root",
        type=str,
        default=".",
        help="Repository root path (default: current directory)",
    )

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
        "--backup",
        action="store_true",
        help="Backup old workflow by renaming it with [BKP timestamp] before replacing",
    )
    deploy_parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete workflows in n8n that are not in the manifest",
    )
    deploy_parser.add_argument(
        "--api-url",
        type=str,
        help="n8n API URL (overrides env and .n8n-auth)",
    )
    deploy_parser.add_argument(
        "--api-key",
        type=str,
        help="n8n API key (overrides env and .n8n-auth)",
    )
    deploy_parser.add_argument(
        "--repo-root",
        type=str,
        default=".",
        help="Repository root path (default: current directory)",
    )

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
    rollback_parser.add_argument(
        "--api-url",
        type=str,
        help="n8n API URL (overrides env and .n8n-auth)",
    )
    rollback_parser.add_argument(
        "--api-key",
        type=str,
        help="n8n API key (overrides env and .n8n-auth)",
    )
    rollback_parser.add_argument(
        "--repo-root",
        type=str,
        default=".",
        help="Repository root path (default: current directory)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "create-project":
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
