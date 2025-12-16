"""Tests for JSON normalization."""

import json

from n8n_gitops.normalize import normalize_json, normalize_obj


class TestNormalizeObj:
    """Test object normalization."""

    def test_normalize_dict(self):
        """Test normalizing a dictionary."""
        obj = {"z": 3, "a": 1, "m": 2}
        result = normalize_obj(obj)
        # Keys should be sorted
        assert list(result.keys()) == ["a", "m", "z"]
        assert result == {"a": 1, "m": 2, "z": 3}

    def test_normalize_nested_dict(self):
        """Test normalizing nested dictionaries."""
        obj = {
            "z": {"y": 2, "x": 1},
            "a": {"c": 4, "b": 3}
        }
        result = normalize_obj(obj)
        # Top-level keys sorted
        assert list(result.keys()) == ["a", "z"]
        # Nested keys sorted
        assert list(result["a"].keys()) == ["b", "c"]
        assert list(result["z"].keys()) == ["x", "y"]

    def test_normalize_list(self):
        """Test normalizing lists."""
        obj = [{"b": 2, "a": 1}, {"d": 4, "c": 3}]
        result = normalize_obj(obj)
        # List items should have sorted keys
        assert list(result[0].keys()) == ["a", "b"]
        assert list(result[1].keys()) == ["c", "d"]

    def test_normalize_primitives(self):
        """Test that primitives are unchanged."""
        assert normalize_obj(42) == 42
        assert normalize_obj("hello") == "hello"
        assert normalize_obj(True) is True
        assert normalize_obj(None) is None


class TestNormalizeJson:
    """Test JSON normalization."""

    def test_normalize_json_basic(self):
        """Test basic JSON normalization."""
        obj = {"z": 3, "a": 1, "m": 2}
        result = normalize_json(obj)
        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed == {"a": 1, "m": 2, "z": 3}
        # Should have newline at end
        assert result.endswith("\n")

    def test_normalize_json_stable_output(self):
        """Test that normalization produces stable output."""
        obj = {"z": 3, "a": 1, "m": 2}
        result1 = normalize_json(obj)
        result2 = normalize_json(obj)
        # Should produce identical output
        assert result1 == result2

    def test_normalize_json_formatting(self):
        """Test JSON formatting."""
        obj = {"a": 1, "b": [1, 2, 3]}
        result = normalize_json(obj)
        # Should have 2-space indentation
        assert "  " in result
        # Should have newline at end
        assert result.endswith("\n")

    def test_normalize_json_unicode(self):
        """Test that unicode is preserved."""
        obj = {"message": "Hello 世界"}
        result = normalize_json(obj)
        parsed = json.loads(result)
        assert parsed["message"] == "Hello 世界"

    def test_normalize_json_consistency(self):
        """Test that running twice produces identical results."""
        obj = {
            "z": {"nested": [3, 2, 1]},
            "a": {"x": 1, "y": 2}
        }
        result1 = normalize_json(obj)
        # Parse and normalize again
        parsed = json.loads(result1)
        result2 = normalize_json(parsed)
        # Should be identical
        assert result1 == result2
