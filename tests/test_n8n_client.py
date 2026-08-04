"""Tests for the n8n API client, focused on list pagination."""

from unittest.mock import MagicMock, patch

from n8n_gitops.n8n_client import N8nClient


def _mock_response(json_data):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = json_data
    response.raise_for_status.return_value = None
    return response


class TestListWorkflowsPagination:
    """list_workflows() must page through every workflow, not just the first page."""

    def test_single_page(self):
        client = N8nClient("https://example.com", "key")
        page = {"data": [{"id": "1", "name": "wf-1"}], "nextCursor": None}

        with patch.object(client.session, "request", return_value=_mock_response(page)) as mock_request:
            workflows = client.list_workflows()

        assert workflows == [{"id": "1", "name": "wf-1"}]
        mock_request.assert_called_once()

    def test_follows_cursor_across_multiple_pages(self):
        client = N8nClient("https://example.com", "key")
        page1 = {
            "data": [{"id": str(i), "name": f"wf-{i}"} for i in range(100)],
            "nextCursor": "cursor-2",
        }
        page2 = {
            "data": [{"id": str(i), "name": f"wf-{i}"} for i in range(100, 150)],
            "nextCursor": None,
        }

        with patch.object(
            client.session, "request", side_effect=[_mock_response(page1), _mock_response(page2)]
        ) as mock_request:
            workflows = client.list_workflows()

        assert len(workflows) == 150
        assert mock_request.call_count == 2
        second_call_params = mock_request.call_args_list[1].kwargs["params"]
        assert second_call_params["cursor"] == "cursor-2"

    def test_fallback_for_plain_list_response(self):
        client = N8nClient("https://example.com", "key")
        legacy_response = [{"id": "1", "name": "wf-1"}]

        with patch.object(client.session, "request", return_value=_mock_response(legacy_response)):
            workflows = client.list_workflows()

        assert workflows == [{"id": "1", "name": "wf-1"}]
