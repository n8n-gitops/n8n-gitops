"""Install git hooks command implementation."""

import argparse
import getpass
import subprocess
import stat
from pathlib import Path

from n8n_gitops import logger
from n8n_gitops.config import CONFIG_FILENAME, save_config_profile

_PRE_COMMIT_TEMPLATE = """\
#!/bin/sh
# n8n-gitops: export workflows from n8n before commit
REPO_ROOT=$(git rev-parse --show-toplevel)

n8n-gitops export --config {config} --repo-root "$REPO_ROOT" || exit 1

# Check for new or modified files in n8n/ that are not yet staged
UNSTAGED=$(git -C "$REPO_ROOT" diff --name-only -- n8n/ && git -C "$REPO_ROOT" ls-files --others --exclude-standard -- n8n/)
if [ -n "$UNSTAGED" ]; then
    echo ""
    echo "n8n-gitops: workflows were exported and have unstaged changes."
    echo "Stage them and commit again:"
    echo ""
    echo "  git add n8n/"
    echo "  git commit"
    echo ""
    exit 1
fi
"""

_POST_MERGE_TEMPLATE = """\
#!/bin/sh
# n8n-gitops: deploy workflows to n8n after pull/merge
REPO_ROOT=$(git rev-parse --show-toplevel)
n8n-gitops deploy --config {config} --repo-root "$REPO_ROOT"
"""


def _prompt(prompt_text: str, default: str | None = None, secret: bool = False) -> str:
    label = f"{prompt_text} [{default}]: " if default else f"{prompt_text}: "
    if secret:
        value = getpass.getpass(label)
    else:
        value = input(label)
    if not value and default:
        return default
    if not value:
        raise ValueError(f"{prompt_text} is required")
    return value


def _find_git_dir(repo_root: Path) -> Path:
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        raise ValueError(f"No .git directory found at {repo_root}. Is this a git repository?")
    if git_dir.is_file():
        # Worktree: .git is a file pointing to the real git dir
        content = git_dir.read_text().strip()
        if content.startswith("gitdir: "):
            return Path(content[len("gitdir: "):])
        raise ValueError(f"Unexpected .git file content: {content}")
    return git_dir


def _ensure_gitignore(repo_root: Path) -> None:
    """Add CONFIG_FILENAME to .gitignore if not already present, then stage it."""
    gitignore_path = repo_root / ".gitignore"
    entry = CONFIG_FILENAME

    if gitignore_path.exists():
        lines = gitignore_path.read_text().splitlines()
        if any(line.strip() == entry for line in lines):
            return
        gitignore_path.write_text(gitignore_path.read_text().rstrip("\n") + f"\n{entry}\n")
    else:
        gitignore_path.write_text(f"{entry}\n")

    logger.info(f"✓ Added '{entry}' to {gitignore_path}")
    subprocess.run(["git", "-C", str(repo_root), "add", ".gitignore"], check=False)


def _write_hook(hooks_dir: Path, hook_name: str, content: str, force: bool) -> None:
    hook_path = hooks_dir / hook_name
    if hook_path.exists() and not force:
        logger.warning(
            f"Hook {hook_path} already exists. Use --force to overwrite."
        )
        return
    hook_path.write_text(content)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    logger.info(f"✓ Installed {hook_name} hook at {hook_path}")


def run_install_hooks(args: argparse.Namespace) -> None:
    """Install git hooks for n8n-gitops export and deploy.

    Prompts interactively for any values not supplied via CLI flags.

    Args:
        args: CLI arguments
    """
    repo_root = Path(args.repo_root).resolve()

    # Collect config values, prompting for any that are missing
    config_name: str = args.config or _prompt("Config profile name (e.g. dev, staging, prod)")
    api_url: str = args.api_url or _prompt("n8n API URL")
    api_key: str = args.api_key or _prompt("n8n API key", secret=True)
    insecure: bool = args.insecure

    # Save config profile
    config_path = save_config_profile(
        repo_root=repo_root,
        name=config_name,
        api_url=api_url,
        api_key=api_key,
        insecure=insecure,
    )
    logger.info(f"✓ Saved config profile '{config_name}' to {config_path}")

    # Protect the config file (contains API key)
    _ensure_gitignore(repo_root)

    # Locate hooks directory
    git_dir = _find_git_dir(repo_root)
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    force: bool = args.force

    _write_hook(
        hooks_dir,
        "pre-commit",
        _PRE_COMMIT_TEMPLATE.format(config=config_name),
        force,
    )
    _write_hook(
        hooks_dir,
        "post-merge",
        _POST_MERGE_TEMPLATE.format(config=config_name),
        force,
    )

    logger.info("")
    logger.info("Git hooks installed. Workflow:")
    logger.info("  git commit  →  exports workflows from n8n  (pre-commit)")
    logger.info("  git pull    →  deploys workflows to n8n    (post-merge)")

    # Initial deploy if n8n/ directory already exists
    if (repo_root / "n8n").is_dir():
        logger.info("")
        logger.info("Deploying existing workflows to n8n...")
        try:
            from n8n_gitops.commands.deploy import run_deploy
            deploy_args = argparse.Namespace(
                config=config_name,
                api_url=None,
                api_key=None,
                repo_root=str(repo_root),
                insecure=insecure,
                git_ref=None,
                dry_run=False,
                prune=True,
                silent=args.silent,
                break_on_error=args.break_on_error,
            )
            run_deploy(deploy_args)
        except (Exception, SystemExit):
            logger.warning("  ⚠ Initial deploy failed.")
            logger.warning("  Run 'n8n-gitops deploy --prune' manually when ready.")