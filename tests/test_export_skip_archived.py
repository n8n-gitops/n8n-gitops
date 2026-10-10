"""Tests for archived-workflow handling during export."""

from pathlib import Path
from tempfile import TemporaryDirectory

from n8n_gitops.commands.export_workflows import (
    _export_single_workflow,
    _filter_archived_workflows,
)


class TestFilterArchivedWorkflows:
    """Test _filter_archived_workflows()."""

    def test_skip_archived_false_keeps_all(self):
        """Test that archived workflows are kept when skip_archived is False."""
        workflows = [
            {"id": "1", "name": "Active", "isArchived": False},
            {"id": "2", "name": "Archived", "isArchived": True},
        ]
        result = _filter_archived_workflows(workflows, skip_archived=False)
        assert result == workflows

    def test_skip_archived_true_excludes_archived(self):
        """Test that archived workflows are excluded when skip_archived is True."""
        workflows = [
            {"id": "1", "name": "Active", "isArchived": False},
            {"id": "2", "name": "Archived", "isArchived": True},
        ]
        result = _filter_archived_workflows(workflows, skip_archived=True)
        assert [wf["name"] for wf in result] == ["Active"]

    def test_skip_archived_true_missing_field_treated_as_not_archived(self):
        """Test that workflows without an isArchived field are treated as active."""
        workflows = [{"id": "1", "name": "No Flag"}]
        result = _filter_archived_workflows(workflows, skip_archived=True)
        assert result == workflows

    def test_empty_list(self):
        """Test filtering an empty list returns an empty list."""
        assert _filter_archived_workflows([], skip_archived=True) == []


class FakeClient:
    """Fake N8n client returning a fixed workflow payload."""

    def __init__(self, workflow: dict):
        self._workflow = workflow

    def get_workflow(self, workflow_id: str) -> dict:
        return self._workflow


class TestExportSingleWorkflowIsArchived:
    """Test that _export_single_workflow records is_archived in the manifest spec."""

    def test_is_archived_true_recorded_in_spec(self):
        """Test that an archived workflow's spec has is_archived True."""
        workflow = {
            "id": "1",
            "name": "Archived Workflow",
            "active": False,
            "isArchived": True,
            "nodes": [],
            "connections": {},
        }
        client = FakeClient(workflow)

        with TemporaryDirectory() as tmpdir:
            workflows_dir = Path(tmpdir) / "workflows"
            scripts_dir = Path(tmpdir) / "scripts"
            workflows_dir.mkdir()
            scripts_dir.mkdir()

            spec, _ = _export_single_workflow(
                client, {"id": "1", "name": "Archived Workflow"},
                workflows_dir, scripts_dir, False, {}, {},
            )

        assert spec is not None
        assert spec["is_archived"] is True

    def test_is_archived_false_when_not_archived(self):
        """Test that a non-archived workflow's spec has is_archived False."""
        workflow = {
            "id": "1",
            "name": "Active Workflow",
            "active": True,
            "isArchived": False,
            "nodes": [],
            "connections": {},
        }
        client = FakeClient(workflow)

        with TemporaryDirectory() as tmpdir:
            workflows_dir = Path(tmpdir) / "workflows"
            scripts_dir = Path(tmpdir) / "scripts"
            workflows_dir.mkdir()
            scripts_dir.mkdir()

            spec, _ = _export_single_workflow(
                client, {"id": "1", "name": "Active Workflow"},
                workflows_dir, scripts_dir, False, {}, {},
            )

        assert spec is not None
        assert spec["is_archived"] is False

    def test_is_archived_defaults_false_when_field_absent(self):
        """Test that is_archived defaults to False when the API omits the field."""
        workflow = {
            "id": "1",
            "name": "Legacy Workflow",
            "active": True,
            "nodes": [],
            "connections": {},
        }
        client = FakeClient(workflow)

        with TemporaryDirectory() as tmpdir:
            workflows_dir = Path(tmpdir) / "workflows"
            scripts_dir = Path(tmpdir) / "scripts"
            workflows_dir.mkdir()
            scripts_dir.mkdir()

            spec, _ = _export_single_workflow(
                client, {"id": "1", "name": "Legacy Workflow"},
                workflows_dir, scripts_dir, False, {}, {},
            )

        assert spec is not None
        assert spec["is_archived"] is False
