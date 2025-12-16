"""n8n API client."""

import time
from typing import Any

import requests

from n8n_gitops.exceptions import APIError


class N8nClient:
    """Client for interacting with n8n API."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialize n8n API client.

        Args:
            api_url: Base URL of n8n instance
            api_key: API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for 429/5xx errors
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-N8N-API-KEY": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint path
            json_data: JSON data for request body
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            APIError: If request fails after retries
        """
        url = f"{self.api_url}{endpoint}"
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    json=json_data,
                    params=params,
                    timeout=self.timeout,
                )

                # Handle rate limiting and server errors with retry
                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt < self.max_retries - 1:
                        # Exponential backoff: 1s, 2s, 4s
                        wait_time = 2 ** attempt
                        time.sleep(wait_time)
                        continue
                    # Last attempt, raise error
                    response.raise_for_status()

                # Raise for other client/server errors
                response.raise_for_status()

                # Return JSON response
                return response.json()

            except requests.exceptions.HTTPError as e:
                # Extract error details from response
                error_detail = ""
                try:
                    error_json = e.response.json()
                    error_detail = str(error_json)
                except Exception:
                    error_detail = e.response.text[:200]

                last_error = APIError(
                    f"API request failed: {method} {endpoint} -> "
                    f"HTTP {e.response.status_code}: {error_detail}"
                )

            except requests.exceptions.Timeout as e:
                last_error = APIError(f"Request timeout: {method} {endpoint} -> {e}")

            except requests.exceptions.RequestException as e:
                last_error = APIError(f"Request error: {method} {endpoint} -> {e}")

            # If this wasn't a retryable error, break immediately
            if not isinstance(last_error, APIError) or attempt == self.max_retries - 1:
                break

        # If we got here, all retries failed
        if last_error:
            raise last_error
        raise APIError(f"Request failed after {self.max_retries} retries")

    def list_workflows(self) -> list[dict[str, Any]]:
        """List all workflows.

        Returns:
            List of workflow objects

        Raises:
            APIError: If request fails
        """
        result = self._request("GET", "/api/v1/workflows")
        if isinstance(result, list):
            return result
        # Some n8n versions wrap results in data
        if isinstance(result, dict) and "data" in result:
            return result["data"]
        return []

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Get a specific workflow by ID.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow object

        Raises:
            APIError: If request fails
        """
        result = self._request("GET", f"/api/v1/workflows/{workflow_id}")
        if isinstance(result, dict):
            return result
        raise APIError(f"Unexpected response type for get_workflow: {type(result)}")

    def create_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """Create a new workflow.

        Args:
            workflow: Workflow object

        Returns:
            Created workflow object with ID

        Raises:
            APIError: If request fails
        """
        result = self._request("POST", "/api/v1/workflows", json_data=workflow)
        if isinstance(result, dict):
            return result
        raise APIError(f"Unexpected response type for create_workflow: {type(result)}")

    def update_workflow(
        self, workflow_id: str, workflow: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing workflow.

        Args:
            workflow_id: Workflow ID
            workflow: Updated workflow object

        Returns:
            Updated workflow object

        Raises:
            APIError: If request fails
        """
        result = self._request(
            "PUT", f"/api/v1/workflows/{workflow_id}", json_data=workflow
        )
        if isinstance(result, dict):
            return result
        raise APIError(f"Unexpected response type for update_workflow: {type(result)}")

    def activate_workflow(self, workflow_id: str) -> None:
        """Activate a workflow.

        Args:
            workflow_id: Workflow ID

        Raises:
            APIError: If request fails
        """
        # Update workflow with active: true
        self._request(
            "PATCH",
            f"/api/v1/workflows/{workflow_id}",
            json_data={"active": True},
        )

    def deactivate_workflow(self, workflow_id: str) -> None:
        """Deactivate a workflow.

        Args:
            workflow_id: Workflow ID

        Raises:
            APIError: If request fails
        """
        # Update workflow with active: false
        self._request(
            "PATCH",
            f"/api/v1/workflows/{workflow_id}",
            json_data={"active": False},
        )

    def archive_workflow(self, workflow_id: str) -> None:
        """Archive a workflow.

        Workflows must be archived before they can be deleted.

        Args:
            workflow_id: Workflow ID

        Raises:
            APIError: If request fails
        """
        self._request(
            "PUT",
            f"/api/v1/workflows/{workflow_id}/archive",
        )

    def delete_workflow(self, workflow_id: str) -> None:
        """Delete an archived workflow.

        Note: Workflow must be archived first using archive_workflow().

        Args:
            workflow_id: Workflow ID

        Raises:
            APIError: If request fails
        """
        self._request(
            "DELETE",
            f"/api/v1/workflows/{workflow_id}",
        )
