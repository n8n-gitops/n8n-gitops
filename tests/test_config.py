"""Tests for configuration and auth loading."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from n8n_gitops.config import (
    load_auth,
    load_config_profile,
    resolve_skip_archived,
    save_config_profile,
)
from n8n_gitops.exceptions import ConfigError


class TestConfigProfile:
    """Test config profile save/load."""

    def test_save_and_load_profile(self):
        """Test saving and loading a config profile."""
        with TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            save_config_profile(repo_root, "dev", "https://dev.example.com", "dev-key", True)

            profile = load_config_profile(repo_root, "dev")
            assert profile["api_url"] == "https://dev.example.com"
            assert profile["api_key"] == "dev-key"
            assert profile["insecure"] is True

    def test_save_multiple_profiles(self):
        """Test saving multiple profiles to the same file."""
        with TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            save_config_profile(repo_root, "dev", "https://dev.example.com", "dev-key")
            save_config_profile(repo_root, "prod", "https://prod.example.com", "prod-key")

            dev = load_config_profile(repo_root, "dev")
            prod = load_config_profile(repo_root, "prod")
            assert dev["api_url"] == "https://dev.example.com"
            assert prod["api_url"] == "https://prod.example.com"

    def test_update_existing_profile(self):
        """Test that saving an existing profile overwrites it."""
        with TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            save_config_profile(repo_root, "dev", "https://old.example.com", "old-key")
            save_config_profile(repo_root, "dev", "https://new.example.com", "new-key")

            profile = load_config_profile(repo_root, "dev")
            assert profile["api_url"] == "https://new.example.com"
            assert profile["api_key"] == "new-key"

    def test_load_missing_file(self):
        """Test that loading from missing file raises error."""
        with TemporaryDirectory() as tmpdir:
            with pytest.raises(ConfigError, match="not found"):
                load_config_profile(Path(tmpdir), "dev")

    def test_load_missing_profile(self):
        """Test that loading missing profile raises error."""
        with TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            save_config_profile(repo_root, "dev", "https://dev.example.com", "key")

            with pytest.raises(ConfigError, match="prod"):
                load_config_profile(repo_root, "prod")


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

    def test_load_from_config_profile(self):
        """Test loading auth from config profile."""
        with TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            save_config_profile(repo_root, "dev", "https://dev.example.com", "dev-key", True)

            old_url = os.environ.pop("N8N_API_URL", None)
            old_key = os.environ.pop("N8N_API_KEY", None)

            class Args:
                api_url = None
                api_key = None
                insecure = False
                config = "dev"

            try:
                auth = load_auth(repo_root, Args())
                assert auth.api_url == "https://dev.example.com"
                assert auth.api_key == "dev-key"
                assert auth.insecure is True
            finally:
                if old_url:
                    os.environ["N8N_API_URL"] = old_url
                if old_key:
                    os.environ["N8N_API_KEY"] = old_key

    def test_priority_cli_over_config(self):
        """Test that CLI args take priority over config profile."""
        with TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            save_config_profile(repo_root, "dev", "https://dev.example.com", "dev-key")

            class Args:
                api_url = "https://cli.example.com"
                api_key = "cli-secret"
                insecure = False
                config = "dev"

            auth = load_auth(repo_root, Args())
            assert auth.api_url == "https://cli.example.com"
            assert auth.api_key == "cli-secret"

    def test_priority_cli_over_env(self):
        """Test that CLI args take priority over environment."""
        with TemporaryDirectory() as tmpdir:
            os.environ["N8N_API_URL"] = "https://env.example.com"
            os.environ["N8N_API_KEY"] = "env-secret"

            class Args:
                api_url = "https://cli.example.com"
                api_key = "cli-secret"
                insecure = False
                config = None

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


class TestResolveSkipArchived:
    """Test skip_archived resolution priority (CLI flag > config profile > default)."""

    def test_defaults_false(self):
        """Test that skip_archived defaults to False with no flag or config."""

        class Args:
            skip_archived = None
            config = None

        with TemporaryDirectory() as tmpdir:
            assert resolve_skip_archived(Path(tmpdir), Args()) is False

    def test_no_args(self):
        """Test that skip_archived defaults to False when args is None."""
        with TemporaryDirectory() as tmpdir:
            assert resolve_skip_archived(Path(tmpdir), None) is False

    def test_cli_flag_true(self):
        """Test that the --skip-archived CLI flag is honored."""

        class Args:
            skip_archived = True
            config = None

        with TemporaryDirectory() as tmpdir:
            assert resolve_skip_archived(Path(tmpdir), Args()) is True

    def test_config_profile_true(self):
        """Test that skip_archived: true in the config profile is honored."""
        with TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            save_config_profile(repo_root, "prod", "https://prod.example.com", "prod-key")
            config_path = repo_root / ".n8n-gitops.yaml"
            configs = yaml.safe_load(config_path.read_text())
            configs["prod"]["skip_archived"] = True
            config_path.write_text(yaml.dump(configs, default_flow_style=False, sort_keys=False))

            class Args:
                skip_archived = None
                config = "prod"

            assert resolve_skip_archived(repo_root, Args()) is True

    def test_cli_flag_overrides_absent_config_setting(self):
        """Test that the CLI flag wins even when the config profile doesn't set it."""
        with TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            save_config_profile(repo_root, "prod", "https://prod.example.com", "prod-key")

            class Args:
                skip_archived = True
                config = "prod"

            assert resolve_skip_archived(repo_root, Args()) is True

    def test_missing_config_profile_defaults_false(self):
        """Test that a missing config profile falls back to False rather than raising."""

        class Args:
            skip_archived = None
            config = "does-not-exist"

        with TemporaryDirectory() as tmpdir:
            assert resolve_skip_archived(Path(tmpdir), Args()) is False
