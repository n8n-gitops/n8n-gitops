"""Tests for manifest parsing and validation."""

import pytest

from n8n_gitops.exceptions import ManifestError
from n8n_gitops.manifest import load_manifest


class MockSnapshot:
    """Mock snapshot for testing."""

    def __init__(self, files: dict[str, str]):
        self.files = files

    def read_text(self, rel_path: str) -> str:
        if rel_path not in self.files:
            raise FileNotFoundError(f"File not found: {rel_path}")
        return self.files[rel_path]

    def exists(self, rel_path: str) -> bool:
        return rel_path in self.files


class TestLoadManifest:
    """Test manifest loading and validation."""

    def test_load_valid_manifest(self):
        """Test loading a valid manifest."""
        snapshot = MockSnapshot({
            "n8n/manifests/workflows.yaml": """
workflows:
  - name: "Test Workflow"
    active: true
"""
        })
        manifest = load_manifest(snapshot)
        assert len(manifest.workflows) == 1
        assert manifest.workflows[0].name == "Test Workflow"
        assert manifest.workflows[0].file == "workflows/Test_Workflow.json"
        assert manifest.workflows[0].active is True

    def test_load_manifest_with_all_fields(self):
        """Test loading manifest with all optional fields."""
        snapshot = MockSnapshot({
            "n8n/manifests/workflows.yaml": """
tags:
  - production
  - critical

workflows:
  - name: "Complete Workflow"
    active: true
    tags:
      - production
      - critical
    requires_credentials:
      - stripe-api
    requires_env:
      - STRIPE_KEY
"""
        })
        manifest = load_manifest(snapshot)
        wf = manifest.workflows[0]
        assert wf.name == "Complete Workflow"
        assert wf.file == "workflows/Complete_Workflow.json"
        assert wf.tags == ["production", "critical"]
        assert wf.requires_credentials == ["stripe-api"]
        assert wf.requires_env == ["STRIPE_KEY"]

    def test_manifest_missing_workflows_key(self):
        """Test that manifest without 'workflows' key fails."""
        snapshot = MockSnapshot({
            "n8n/manifests/workflows.yaml": """
invalid: true
"""
        })
        with pytest.raises(ManifestError, match="missing required 'workflows' key"):
            load_manifest(snapshot)

    def test_manifest_workflows_not_list(self):
        """Test that 'workflows' must be a list."""
        snapshot = MockSnapshot({
            "n8n/manifests/workflows.yaml": """
workflows: "not a list"
"""
        })
        with pytest.raises(ManifestError, match="must be a list"):
            load_manifest(snapshot)

    def test_manifest_entry_missing_name(self):
        """Test that workflow entry must have 'name'."""
        snapshot = MockSnapshot({
            "n8n/manifests/workflows.yaml": """
workflows:
  - file: "workflows/test.json"
"""
        })
        with pytest.raises(ManifestError, match="missing required field 'name'"):
            load_manifest(snapshot)

    def test_manifest_duplicate_names(self):
        """Test that duplicate workflow names are rejected."""
        snapshot = MockSnapshot({
            "n8n/manifests/workflows.yaml": """
workflows:
  - name: "Duplicate"
  - name: "Duplicate"
"""
        })
        with pytest.raises(ManifestError, match="Duplicate workflow name"):
            load_manifest(snapshot)

    def test_manifest_empty_workflows(self):
        """Test manifest with empty workflows list."""
        snapshot = MockSnapshot({
            "n8n/manifests/workflows.yaml": """
workflows: []
"""
        })
        manifest = load_manifest(snapshot)
        assert len(manifest.workflows) == 0

    def test_manifest_invalid_yaml(self):
        """Test that invalid YAML is rejected."""
        snapshot = MockSnapshot({
            "n8n/manifests/workflows.yaml": """
workflows:
  - name: "Test
    invalid yaml
"""
        })
        with pytest.raises(ManifestError, match="Failed to parse manifest YAML"):
            load_manifest(snapshot)

    def test_manifest_with_tags(self):
        """Test that tags section is properly loaded (new list format)."""
        snapshot = MockSnapshot({
            "n8n/manifests/workflows.yaml": """
tags:
  - production
  - development
  - critical

workflows:
  - name: "Test Workflow"
    active: true
    tags:
      - production
      - critical
"""
        })
        manifest = load_manifest(snapshot)
        assert len(manifest.tags) == 3
        assert "production" in manifest.tags
        assert "development" in manifest.tags
        assert "critical" in manifest.tags
        assert manifest.workflows[0].tags == ["production", "critical"]

    def test_manifest_empty_tags(self):
        """Test that empty tags section works."""
        snapshot = MockSnapshot({
            "n8n/manifests/workflows.yaml": """
tags: []

workflows:
  - name: "Test Workflow"
"""
        })
        manifest = load_manifest(snapshot)
        assert len(manifest.tags) == 0
        assert manifest.workflows[0].tags == []

    def test_manifest_tags_invalid_type(self):
        """Test that tags must be a list or dictionary."""
        snapshot = MockSnapshot({
            "n8n/manifests/workflows.yaml": """
tags: "invalid string"

workflows: []
"""
        })
        with pytest.raises(ManifestError, match="'tags' must be a list or dictionary"):
            load_manifest(snapshot)

    def test_manifest_backward_compatibility_dict_tags(self):
        """Test backward compatibility with old dict format."""
        snapshot = MockSnapshot({
            "n8n/manifests/workflows.yaml": """
tags:
  "1": "production"
  "2": "development"

workflows:
  - name: "Test Workflow"
    tags:
      - "1"
      - "2"
"""
        })
        # Should load successfully and convert to new format
        manifest = load_manifest(snapshot)
        # Tags should be converted to list of unique names
        assert len(manifest.tags) == 2
        assert "production" in manifest.tags
        assert "development" in manifest.tags
        # Workflow tags should be converted from IDs to names
        assert manifest.workflows[0].tags == ["production", "development"]

    def test_manifest_workflow_tag_validation(self):
        """Test that workflow tags must exist in manifest tags section."""
        snapshot = MockSnapshot({
            "n8n/manifests/workflows.yaml": """
tags:
  - production
  - development

workflows:
  - name: "Test Workflow"
    tags:
      - production
      - undefined-tag
"""
        })
        with pytest.raises(ManifestError, match="references undefined tag 'undefined-tag'"):
            load_manifest(snapshot)
