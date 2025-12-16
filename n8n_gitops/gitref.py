"""Git ref snapshot reader for accessing files from working tree or git history."""

import subprocess
from pathlib import Path
from typing import Protocol

from n8n_gitops.exceptions import GitRefError


class Snapshot(Protocol):
    """Protocol for reading files from a snapshot (working tree or git ref)."""

    def read_text(self, rel_path: str) -> str:
        """Read file as text.

        Args:
            rel_path: Relative path from repo root

        Returns:
            File contents as string

        Raises:
            GitRefError: If file cannot be read
        """
        ...

    def read_bytes(self, rel_path: str) -> bytes:
        """Read file as bytes.

        Args:
            rel_path: Relative path from repo root

        Returns:
            File contents as bytes

        Raises:
            GitRefError: If file cannot be read
        """
        ...

    def exists(self, rel_path: str) -> bool:
        """Check if file exists.

        Args:
            rel_path: Relative path from repo root

        Returns:
            True if file exists, False otherwise
        """
        ...


class WorkingTreeSnapshot:
    """Snapshot that reads from the working tree."""

    def __init__(self, repo_root: Path) -> None:
        """Initialize working tree snapshot.

        Args:
            repo_root: Path to repository root
        """
        self.repo_root = repo_root

    def read_text(self, rel_path: str) -> str:
        """Read file as text from working tree.

        Args:
            rel_path: Relative path from repo root

        Returns:
            File contents as string

        Raises:
            GitRefError: If file cannot be read
        """
        try:
            file_path = self.repo_root / rel_path
            return file_path.read_text()
        except Exception as e:
            raise GitRefError(f"Failed to read {rel_path}: {e}")

    def read_bytes(self, rel_path: str) -> bytes:
        """Read file as bytes from working tree.

        Args:
            rel_path: Relative path from repo root

        Returns:
            File contents as bytes

        Raises:
            GitRefError: If file cannot be read
        """
        try:
            file_path = self.repo_root / rel_path
            return file_path.read_bytes()
        except Exception as e:
            raise GitRefError(f"Failed to read {rel_path}: {e}")

    def exists(self, rel_path: str) -> bool:
        """Check if file exists in working tree.

        Args:
            rel_path: Relative path from repo root

        Returns:
            True if file exists, False otherwise
        """
        file_path = self.repo_root / rel_path
        return file_path.exists() and file_path.is_file()


class GitRefSnapshot:
    """Snapshot that reads from a specific git ref using git show."""

    def __init__(self, repo_root: Path, git_ref: str) -> None:
        """Initialize git ref snapshot.

        Args:
            repo_root: Path to repository root
            git_ref: Git reference (tag, branch, commit hash)
        """
        self.repo_root = repo_root
        self.git_ref = git_ref

    def read_text(self, rel_path: str) -> str:
        """Read file as text from git ref.

        Args:
            rel_path: Relative path from repo root

        Returns:
            File contents as string

        Raises:
            GitRefError: If file cannot be read from git ref
        """
        return self.read_bytes(rel_path).decode("utf-8")

    def read_bytes(self, rel_path: str) -> bytes:
        """Read file as bytes from git ref using git show.

        Args:
            rel_path: Relative path from repo root

        Returns:
            File contents as bytes

        Raises:
            GitRefError: If file cannot be read from git ref
        """
        # Normalize path to use forward slashes for git
        git_path = rel_path.replace("\\", "/")
        git_object = f"{self.git_ref}:{git_path}"

        try:
            result = subprocess.run(
                ["git", "show", git_object],
                cwd=self.repo_root,
                capture_output=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode("utf-8", errors="replace").strip()
            raise GitRefError(
                f"Failed to read {rel_path} from git ref {self.git_ref}: {error_msg}"
            )
        except Exception as e:
            raise GitRefError(
                f"Failed to read {rel_path} from git ref {self.git_ref}: {e}"
            )

    def exists(self, rel_path: str) -> bool:
        """Check if file exists in git ref.

        Args:
            rel_path: Relative path from repo root

        Returns:
            True if file exists in the git ref, False otherwise
        """
        try:
            self.read_bytes(rel_path)
            return True
        except GitRefError:
            return False


def create_snapshot(repo_root: Path, git_ref: str | None = None) -> Snapshot:
    """Create a snapshot reader.

    Args:
        repo_root: Path to repository root
        git_ref: Optional git reference (tag, branch, commit)

    Returns:
        Snapshot reader (WorkingTreeSnapshot or GitRefSnapshot)
    """
    if git_ref:
        return GitRefSnapshot(repo_root, git_ref)
    else:
        return WorkingTreeSnapshot(repo_root)
