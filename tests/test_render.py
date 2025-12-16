"""Tests for code include rendering."""

import pytest

from n8n_gitops.exceptions import RenderError
from n8n_gitops.render import (
    compute_sha256,
    parse_include_directive,
    validate_include_path,
)


class TestParseIncludeDirective:
    """Test include directive parser."""

    def test_parse_basic_include(self):
        """Test parsing basic include directive."""
        directive = "@@n8n-gitops:include scripts/example/hello.py"
        result = parse_include_directive(directive)
        assert result is not None
        path, sha256 = result
        assert path == "scripts/example/hello.py"
        assert sha256 is None

    def test_parse_include_with_checksum(self):
        """Test parsing include directive with checksum."""
        directive = (
            "@@n8n-gitops:include scripts/example/hello.py "
            "sha256=abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
        )
        result = parse_include_directive(directive)
        assert result is not None
        path, sha256 = result
        assert path == "scripts/example/hello.py"
        assert sha256 == "abc123def456abc123def456abc123def456abc123def456abc123def456abcd"

    def test_parse_not_directive(self):
        """Test that regular code is not parsed as directive."""
        code = "print('hello world')"
        result = parse_include_directive(code)
        assert result is None

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        result = parse_include_directive("")
        assert result is None

    def test_parse_none(self):
        """Test parsing None."""
        result = parse_include_directive(None)
        assert result is None

    def test_parse_invalid_checksum(self):
        """Test parsing directive with invalid checksum length."""
        directive = "@@n8n-gitops:include scripts/test.py sha256=tooshort"
        result = parse_include_directive(directive)
        # Should not match because checksum is not 64 hex chars
        assert result is None


class TestValidateIncludePath:
    """Test include path validation."""

    def test_valid_path(self):
        """Test valid include path."""
        validate_include_path("scripts/example/hello.py")
        # Should not raise

    def test_path_without_scripts_prefix(self):
        """Test path that doesn't start with scripts/."""
        with pytest.raises(RenderError, match="must be under scripts/"):
            validate_include_path("example/hello.py")

    def test_absolute_path(self):
        """Test that absolute paths are rejected."""
        with pytest.raises(RenderError, match="cannot be absolute"):
            validate_include_path("/etc/passwd")

    def test_path_traversal(self):
        """Test that path traversal is prevented."""
        with pytest.raises(RenderError, match="cannot contain"):
            validate_include_path("scripts/../../../etc/passwd")

    def test_path_with_double_dot(self):
        """Test that .. in path is rejected."""
        with pytest.raises(RenderError, match="cannot contain"):
            validate_include_path("scripts/../../other/file.py")


class TestComputeSha256:
    """Test SHA256 computation."""

    def test_compute_sha256(self):
        """Test SHA256 hash computation."""
        content = b"hello world"
        hash_result = compute_sha256(content)
        # Known SHA256 of "hello world"
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert hash_result == expected

    def test_compute_sha256_empty(self):
        """Test SHA256 of empty bytes."""
        content = b""
        hash_result = compute_sha256(content)
        # Known SHA256 of empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert hash_result == expected

    def test_compute_sha256_consistency(self):
        """Test that same input produces same hash."""
        content = b"test data"
        hash1 = compute_sha256(content)
        hash2 = compute_sha256(content)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex is 64 characters
