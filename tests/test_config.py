"""Tests for configuration and auth loading."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from n8n_gitops.config import _parse_n8n_auth, load_auth
from n8n_gitops.exceptions import ConfigError


class TestParseN8nAuth:
    """Test .n8n-auth file parsing."""

    def test_parse_basic_auth(self):
        """Test parsing basic KEY=VALUE format."""
        with TemporaryDirectory() as tmpdir:
            auth_file = Path(tmpdir) / ".n8n-auth"
            auth_file.write_text(
                "N8N_API_URL=https://example.com\n"
                "N8N_API_KEY=secret123\n"
            )
            result = _parse_n8n_auth(auth_file)
            assert result["N8N_API_URL"] == "https://example.com"
            assert result["N8N_API_KEY"] == "secret123"

    def test_parse_with_quotes(self):
        """Test parsing values with quotes."""
        with TemporaryDirectory() as tmpdir:
            auth_file = Path(tmpdir) / ".n8n-auth"
            auth_file.write_text(
                'N8N_API_URL="https://example.com"\n'
                "N8N_API_KEY='secret123'\n"
            )
            result = _parse_n8n_auth(auth_file)
            assert result["N8N_API_URL"] == "https://example.com"
            assert result["N8N_API_KEY"] == "secret123"

    def test_parse_with_comments(self):
        """Test that comments are ignored."""
        with TemporaryDirectory() as tmpdir:
            auth_file = Path(tmpdir) / ".n8n-auth"
            auth_file.write_text(
                "# This is a comment\n"
                "N8N_API_URL=https://example.com\n"
                "# Another comment\n"
                "N8N_API_KEY=secret123\n"
            )
            result = _parse_n8n_auth(auth_file)
            assert len(result) == 2
            assert result["N8N_API_URL"] == "https://example.com"

    def test_parse_empty_lines(self):
        """Test that empty lines are ignored."""
        with TemporaryDirectory() as tmpdir:
            auth_file = Path(tmpdir) / ".n8n-auth"
            auth_file.write_text(
                "N8N_API_URL=https://example.com\n"
                "\n"
                "N8N_API_KEY=secret123\n"
            )
            result = _parse_n8n_auth(auth_file)
            assert len(result) == 2


class TestLoadAuth:
    """Test auth loading with priority."""

    def test_load_from_env(self):
        """Test loading auth from environment variables."""
        with TemporaryDirectory() as tmpdir:
            os.environ["N8N_API_URL"] = "https://env.example.com"
            os.environ["N8N_API_KEY"] = "env-secret"

            try:
                auth = load_auth(Path(tmpdir))
                assert auth.api_url == "https://env.example.com"
                assert auth.api_key == "env-secret"
            finally:
                del os.environ["N8N_API_URL"]
                del os.environ["N8N_API_KEY"]

    def test_load_from_file(self):
        """Test loading auth from .n8n-auth file."""
        with TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            auth_file = repo_root / ".n8n-auth"
            auth_file.write_text(
                "N8N_API_URL=https://file.example.com\n"
                "N8N_API_KEY=file-secret\n"
            )

            # Clear any existing env vars
            old_url = os.environ.pop("N8N_API_URL", None)
            old_key = os.environ.pop("N8N_API_KEY", None)

            try:
                auth = load_auth(repo_root)
                assert auth.api_url == "https://file.example.com"
                assert auth.api_key == "file-secret"
            finally:
                if old_url:
                    os.environ["N8N_API_URL"] = old_url
                if old_key:
                    os.environ["N8N_API_KEY"] = old_key

    def test_priority_cli_over_env(self):
        """Test that CLI args take priority over environment."""
        with TemporaryDirectory() as tmpdir:
            os.environ["N8N_API_URL"] = "https://env.example.com"
            os.environ["N8N_API_KEY"] = "env-secret"

            class Args:
                api_url = "https://cli.example.com"
                api_key = "cli-secret"

            try:
                auth = load_auth(Path(tmpdir), Args())
                assert auth.api_url == "https://cli.example.com"
                assert auth.api_key == "cli-secret"
            finally:
                del os.environ["N8N_API_URL"]
                del os.environ["N8N_API_KEY"]

    def test_missing_credentials(self):
        """Test that missing credentials raise error."""
        with TemporaryDirectory() as tmpdir:
            # Clear any existing env vars
            old_url = os.environ.pop("N8N_API_URL", None)
            old_key = os.environ.pop("N8N_API_KEY", None)

            try:
                with pytest.raises(ConfigError, match="N8N_API_URL not found"):
                    load_auth(Path(tmpdir))
            finally:
                if old_url:
                    os.environ["N8N_API_URL"] = old_url
                if old_key:
                    os.environ["N8N_API_KEY"] = old_key
