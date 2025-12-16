"""Tests for code externalization functionality."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from n8n_gitops.commands.export_workflows import (
    _externalize_workflow_code,
    _get_file_extension,
    _sanitize_filename,
)
from n8n_gitops.gitref import WorkingTreeSnapshot
from n8n_gitops.render import RenderOptions, render_workflow_json


class TestGetFileExtension:
    """Test file extension detection for code fields."""

    def test_python_code_extension(self):
        """Test that pythonCode gets .py extension."""
        assert _get_file_extension("pythonCode") == ".py"

    def test_js_code_extension(self):
        """Test that jsCode gets .js extension."""
        assert _get_file_extension("jsCode") == ".js"

    def test_code_extension(self):
        """Test that code field gets .js extension."""
        assert _get_file_extension("code") == ".js"

    def test_function_code_extension(self):
        """Test that functionCode gets .js extension."""
        assert _get_file_extension("functionCode") == ".js"

    def test_unknown_field_extension(self):
        """Test that unknown fields get .txt extension."""
        assert _get_file_extension("unknownCode") == ".txt"


class TestSanitizeFilename:
    """Test filename sanitization."""

    def test_sanitize_basic_name(self):
        """Test sanitizing basic name."""
        assert _sanitize_filename("Simple Name") == "Simple_Name"

    def test_sanitize_special_characters(self):
        """Test removing special characters."""
        # Special chars become underscores, then trailing underscores are removed
        assert _sanitize_filename("Name!@#$%^&*()") == "Name"

    def test_sanitize_multiple_underscores(self):
        """Test collapsing multiple underscores."""
        assert _sanitize_filename("Name___With___Spaces") == "Name_With_Spaces"

    def test_sanitize_leading_trailing_underscores(self):
        """Test removing leading/trailing underscores."""
        assert _sanitize_filename("__Name__") == "Name"

    def test_sanitize_empty_returns_default(self):
        """Test that empty string returns 'workflow'."""
        assert _sanitize_filename("") == "workflow"

    def test_sanitize_keeps_hyphens_dots(self):
        """Test that hyphens and dots are preserved."""
        assert _sanitize_filename("my-workflow.v2") == "my-workflow.v2"


class TestExternalizeWorkflowCode:
    """Test workflow code externalization."""

    def test_externalize_javascript_code(self):
        """Test externalizing JavaScript code."""
        with TemporaryDirectory() as tmpdir:
            scripts_dir = Path(tmpdir)
            workflow = {
                "name": "Test Workflow",
                "nodes": [
                    {
                        "name": "JS Node",
                        "parameters": {
                            "jsCode": "console.log('hello');"
                        }
                    }
                ]
            }

            modified, count = _externalize_workflow_code(
                workflow, "Test Workflow", scripts_dir
            )

            assert count == 1
            assert modified["nodes"][0]["parameters"]["jsCode"].startswith(
                "@@n8n-gitops:include"
            )

            # Check script file was created
            script_file = scripts_dir / "Test_Workflow" / "JS_Node_jsCode.js"
            assert script_file.exists()
            assert script_file.read_text() == "console.log('hello');"

    def test_externalize_python_code(self):
        """Test externalizing Python code."""
        with TemporaryDirectory() as tmpdir:
            scripts_dir = Path(tmpdir)
            workflow = {
                "name": "Test Workflow",
                "nodes": [
                    {
                        "name": "Python Node",
                        "parameters": {
                            "pythonCode": "print('hello')"
                        }
                    }
                ]
            }

            modified, count = _externalize_workflow_code(
                workflow, "Test Workflow", scripts_dir
            )

            assert count == 1

            # Check script file was created with .py extension
            script_file = scripts_dir / "Test_Workflow" / "Python_Node_pythonCode.py"
            assert script_file.exists()
            assert script_file.read_text() == "print('hello')"

    def test_externalize_multiple_code_blocks(self):
        """Test externalizing multiple code blocks."""
        with TemporaryDirectory() as tmpdir:
            scripts_dir = Path(tmpdir)
            workflow = {
                "name": "Multi Code",
                "nodes": [
                    {
                        "name": "JS Node",
                        "parameters": {
                            "jsCode": "console.log('js');"
                        }
                    },
                    {
                        "name": "Python Node",
                        "parameters": {
                            "pythonCode": "print('python')"
                        }
                    }
                ]
            }

            modified, count = _externalize_workflow_code(
                workflow, "Multi Code", scripts_dir
            )

            assert count == 2

            # Check both files were created
            js_file = scripts_dir / "Multi_Code" / "JS_Node_jsCode.js"
            py_file = scripts_dir / "Multi_Code" / "Python_Node_pythonCode.py"
            assert js_file.exists()
            assert py_file.exists()

    def test_skip_existing_include_directives(self):
        """Test that existing include directives are not re-externalized."""
        with TemporaryDirectory() as tmpdir:
            scripts_dir = Path(tmpdir)
            workflow = {
                "name": "Test",
                "nodes": [
                    {
                        "name": "Node",
                        "parameters": {
                            "jsCode": "@@n8n-gitops:include scripts/existing.js sha256=abc123"
                        }
                    }
                ]
            }

            modified, count = _externalize_workflow_code(
                workflow, "Test", scripts_dir
            )

            assert count == 0
            assert "@@n8n-gitops:include" in modified["nodes"][0]["parameters"]["jsCode"]

    def test_skip_empty_code(self):
        """Test that empty code is not externalized."""
        with TemporaryDirectory() as tmpdir:
            scripts_dir = Path(tmpdir)
            workflow = {
                "name": "Test",
                "nodes": [
                    {
                        "name": "Node",
                        "parameters": {
                            "jsCode": ""
                        }
                    }
                ]
            }

            modified, count = _externalize_workflow_code(
                workflow, "Test", scripts_dir
            )

            assert count == 0

    def test_skip_non_string_code(self):
        """Test that non-string code values are skipped."""
        with TemporaryDirectory() as tmpdir:
            scripts_dir = Path(tmpdir)
            workflow = {
                "name": "Test",
                "nodes": [
                    {
                        "name": "Node",
                        "parameters": {
                            "jsCode": {"not": "a string"}
                        }
                    }
                ]
            }

            modified, count = _externalize_workflow_code(
                workflow, "Test", scripts_dir
            )

            assert count == 0

    def test_handle_duplicate_filenames(self):
        """Test that duplicate filenames are handled with counters."""
        with TemporaryDirectory() as tmpdir:
            scripts_dir = Path(tmpdir)
            workflow = {
                "name": "Test",
                "nodes": [
                    {
                        "name": "Same Name",
                        "parameters": {
                            "jsCode": "console.log('first');"
                        }
                    },
                    {
                        "name": "Same Name",
                        "parameters": {
                            "jsCode": "console.log('second');"
                        }
                    }
                ]
            }

            modified, count = _externalize_workflow_code(
                workflow, "Test", scripts_dir
            )

            assert count == 2

            # Check both files exist with different names
            file1 = scripts_dir / "Test" / "Same_Name_jsCode.js"
            file2 = scripts_dir / "Test" / "Same_Name_jsCode_1.js"
            assert file1.exists()
            assert file2.exists()
            assert file1.read_text() == "console.log('first');"
            assert file2.read_text() == "console.log('second');"

    def test_include_directive_has_checksum(self):
        """Test that generated include directives have checksums."""
        with TemporaryDirectory() as tmpdir:
            scripts_dir = Path(tmpdir)
            workflow = {
                "name": "Test",
                "nodes": [
                    {
                        "name": "Node",
                        "parameters": {
                            "jsCode": "console.log('hello');"
                        }
                    }
                ]
            }

            modified, count = _externalize_workflow_code(
                workflow, "Test", scripts_dir
            )

            directive = modified["nodes"][0]["parameters"]["jsCode"]
            assert "sha256=" in directive
            # Check that sha256 value is 64 hex characters
            sha_part = directive.split("sha256=")[1]
            assert len(sha_part) == 64
            assert all(c in "0123456789abcdef" for c in sha_part)

    def test_workflow_without_nodes(self):
        """Test handling workflow without nodes."""
        with TemporaryDirectory() as tmpdir:
            scripts_dir = Path(tmpdir)
            workflow = {"name": "Empty"}

            modified, count = _externalize_workflow_code(
                workflow, "Empty", scripts_dir
            )

            assert count == 0

    def test_node_without_parameters(self):
        """Test handling node without parameters."""
        with TemporaryDirectory() as tmpdir:
            scripts_dir = Path(tmpdir)
            workflow = {
                "name": "Test",
                "nodes": [
                    {
                        "name": "Node Without Params"
                    }
                ]
            }

            modified, count = _externalize_workflow_code(
                workflow, "Test", scripts_dir
            )

            assert count == 0


class TestExternalizationRoundTrip:
    """Test that externalization and rendering work together correctly."""

    def test_round_trip_javascript(self):
        """Test round-trip externalization and rendering for JavaScript."""
        with TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            scripts_dir = repo_root / "n8n" / "scripts"
            scripts_dir.mkdir(parents=True)

            original_code = "console.log('test');\nreturn $input.all();"
            workflow = {
                "name": "Test",
                "nodes": [
                    {
                        "name": "JS Node",
                        "id": "node1",
                        "parameters": {
                            "jsCode": original_code
                        }
                    }
                ]
            }

            # Step 1: Externalize
            modified, count = _externalize_workflow_code(
                workflow, "Test", scripts_dir
            )
            assert count == 1

            # Step 2: Render (what deploy does)
            snapshot = WorkingTreeSnapshot(repo_root)
            options = RenderOptions(enforce_checksum=True)

            rendered, reports = render_workflow_json(
                modified,
                snapshot,
                n8n_root="n8n",
                git_ref=None,
                options=options
            )

            # Step 3: Verify code matches original
            rendered_code = rendered["nodes"][0]["parameters"]["jsCode"]
            assert rendered_code == original_code
            assert len(reports) == 1
            assert reports[0].status == "included"

    def test_round_trip_python(self):
        """Test round-trip externalization and rendering for Python."""
        with TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            scripts_dir = repo_root / "n8n" / "scripts"
            scripts_dir.mkdir(parents=True)

            original_code = "# Python code\nprint('test')\nreturn items"
            workflow = {
                "name": "Test",
                "nodes": [
                    {
                        "name": "Python Node",
                        "id": "node1",
                        "parameters": {
                            "pythonCode": original_code
                        }
                    }
                ]
            }

            # Externalize
            modified, count = _externalize_workflow_code(
                workflow, "Test", scripts_dir
            )
            assert count == 1

            # Render
            snapshot = WorkingTreeSnapshot(repo_root)
            rendered, reports = render_workflow_json(
                modified, snapshot, n8n_root="n8n"
            )

            # Verify
            rendered_code = rendered["nodes"][0]["parameters"]["pythonCode"]
            assert rendered_code == original_code

    def test_round_trip_multiple_nodes(self):
        """Test round-trip with multiple code nodes."""
        with TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            scripts_dir = repo_root / "n8n" / "scripts"
            scripts_dir.mkdir(parents=True)

            js_code = "console.log('js');"
            py_code = "print('python')"

            workflow = {
                "name": "Multi",
                "nodes": [
                    {
                        "name": "JS",
                        "id": "js-node",
                        "parameters": {"jsCode": js_code}
                    },
                    {
                        "name": "PY",
                        "id": "py-node",
                        "parameters": {"pythonCode": py_code}
                    }
                ]
            }

            # Externalize
            modified, count = _externalize_workflow_code(
                workflow, "Multi", scripts_dir
            )
            assert count == 2

            # Render
            snapshot = WorkingTreeSnapshot(repo_root)
            rendered, reports = render_workflow_json(
                modified, snapshot, n8n_root="n8n"
            )

            # Verify both codes match
            assert rendered["nodes"][0]["parameters"]["jsCode"] == js_code
            assert rendered["nodes"][1]["parameters"]["pythonCode"] == py_code
            assert len(reports) == 2
            assert all(r.status == "included" for r in reports)
