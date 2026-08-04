"""Tests for filename-collision detection during export."""

import pytest

from n8n_gitops.commands.export_workflows import _check_filename_collisions


class TestCheckFilenameCollisions:
    """_check_filename_collisions() must abort loudly instead of silently overwriting."""

    def test_no_collision_passes_silently(self):
        workflows = [
            {"id": "1", "name": "Workflow A"},
            {"id": "2", "name": "Workflow B"},
        ]
        _check_filename_collisions(workflows)  # should not raise

    def test_duplicate_names_raise(self):
        workflows = [
            {"id": "1", "name": "Webhook: New Relation Handler"},
            {"id": "2", "name": "Webhook: New Relation Handler"},
        ]
        with pytest.raises(SystemExit):
            _check_filename_collisions(workflows)

    def test_names_colliding_after_sanitization_raise(self):
        # "Foo Bar" and "Foo  Bar!" both sanitize to "Foo_Bar.json"
        workflows = [
            {"id": "1", "name": "Foo Bar"},
            {"id": "2", "name": "Foo  Bar!"},
        ]
        with pytest.raises(SystemExit):
            _check_filename_collisions(workflows)

    def test_workflows_missing_name_are_ignored(self):
        workflows = [
            {"id": "1", "name": "Workflow A"},
            {"id": "2"},
        ]
        _check_filename_collisions(workflows)  # should not raise
