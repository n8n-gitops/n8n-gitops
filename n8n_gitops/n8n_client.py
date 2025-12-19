"""n8n API client."""

import time
from typing import Any

import requests

from n8n_gitops.exceptions import APIError


def _is_retryable_status(status_code: int) -> bool:
    """Check if HTTP status code is retryable.

    Args:
        status_code: HTTP status code

    Returns:
        True if status code is retryable (429 or 5xx)
    """
    return status_code in (429, 500, 502, 503, 504)


def _extract_error_detail(response: requests.Response) -> str:
    """Extract error details from HTTP response.

    Args:
        response: HTTP response object

    Returns:
        Error detail string
    """
    try:
        error_json = response.json()
        return str(error_json)
    except Exception:
        return response.text[:200]


def _create_http_error(
    exception: requests.exceptions.HTTPError,
    method: str,
    endpoint: str
) -> APIError:
    """Create APIError from HTTPError exception.

    Args:
        exception: HTTPError exception
        method: HTTP method
        endpoint: API endpoint

    Returns:
        APIError with detailed message
    """
    error_detail = _extract_error_detail(exception.response)
    return APIError(
        f"API request failed: {method} {endpoint} -> "
        f"HTTP {exception.response.status_code}: {error_detail}"
    )


def _handle_retryable_status(
    response: requests.Response,
    attempt: int,
    max_retries: int
) -> bool:
    """Handle retryable HTTP status codes.

    Args:
        response: HTTP response object
        attempt: Current attempt number (0-indexed)
        max_retries: Maximum number of retries

    Returns:
        True if should retry, False otherwise

    Raises:
        requests.exceptions.HTTPError: If last attempt or non-retryable error
    """
    if _is_retryable_status(response.status_code):
        if attempt < max_retries - 1:
            # Exponential backoff: 1s, 2s, 4s
            wait_time = 2 ** attempt
            time.sleep(wait_time)
            return True
        # Last attempt, raise error
        response.raise_for_status()
    return False


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

    def _execute_request(
        self,
        method: str,
        url: str,
        json_data: dict[str, Any] | None,
        params: dict[str, Any] | None,
        attempt: int
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Execute a single request attempt.

        Args:
            method: HTTP method
            url: Full URL
            json_data: JSON data for request body
            params: Query parameters
            attempt: Current attempt number (0-indexed)

        Returns:
            Response JSON data if successful, None if should retry

        Raises:
            APIError: If request fails non-retryably
        """
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=json_data,
                params=params,
                timeout=self.timeout,
            )

            # Handle retryable status codes
            if _handle_retryable_status(response, attempt, self.max_retries):
                return None  # Signal to retry

            # Raise for other client/server errors
            response.raise_for_status()

            # Return JSON response
            return response.json()

        except requests.exceptions.HTTPError as e:
            raise _create_http_error(e, method, url)
        except requests.exceptions.Timeout as e:
            raise APIError(f"Request timeout: {method} {url} -> {e}")
        except requests.exceptions.RequestException as e:
            raise APIError(f"Request error: {method} {url} -> {e}")

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

        for attempt in range(self.max_retries):
            result = self._execute_request(method, url, json_data, params, attempt)
            if result is not None:
                return result
            # result is None means we should retry

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
        self._request(
            "POST",
            f"/api/v1/workflows/{workflow_id}/activate",
            json_data={},
        )

    def deactivate_workflow(self, workflow_id: str) -> None:
        """Deactivate a workflow.

        Args:
            workflow_id: Workflow ID

        Raises:
            APIError: If request fails
        """
        self._request(
            "POST",
            f"/api/v1/workflows/{workflow_id}/deactivate",
        )

    def delete_workflow(self, workflow_id: str) -> None:
        """Delete a workflow.

        Args:
            workflow_id: Workflow ID

        Raises:
            APIError: If request fails
        """
        self._request(
            "DELETE",
            f"/api/v1/workflows/{workflow_id}",
        )

    def list_tags(self) -> list[dict[str, Any]]:
        """List all tags with pagination support.

        Returns:
            List of tag objects

        Raises:
            APIError: If request fails
        """
        all_tags: list[dict[str, Any]] = []
        cursor: str | None = ""

        # Paginate through all tags
        while cursor is not None:
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor

            result = self._request("GET", "/api/v1/tags", params=params)

            if isinstance(result, dict):
                # Extract tags from data field
                tags = result.get("data", [])
                if isinstance(tags, list):
                    all_tags.extend(tags)

                # Get next cursor for pagination
                cursor = result.get("nextCursor")
            elif isinstance(result, list):
                # Fallback for older n8n versions that return list directly
                all_tags.extend(result)
                cursor = None
            else:
                # No more data
                cursor = None

        return all_tags

    def create_tag(self, name: str) -> dict[str, Any]:
        """Create a new tag.

        Args:
            name: Tag name

        Returns:
            Created tag object with ID

        Raises:
            APIError: If request fails
        """
        result = self._request("POST", "/api/v1/tags", json_data={"name": name})
        if isinstance(result, dict):
            return result
        raise APIError(f"Unexpected response type for create_tag: {type(result)}")

    def update_tag(self, tag_id: str, name: str) -> dict[str, Any]:
        """Update a tag's name.

        Args:
            tag_id: Tag ID
            name: New tag name

        Returns:
            Updated tag object

        Raises:
            APIError: If request fails
        """
        result = self._request(
            "PUT", f"/api/v1/tags/{tag_id}", json_data={"name": name}
        )
        if isinstance(result, dict):
            return result
        raise APIError(f"Unexpected response type for update_tag: {type(result)}")

    def delete_tag(self, tag_id: str) -> None:
        """Delete a tag.

        Args:
            tag_id: Tag ID

        Raises:
            APIError: If request fails
        """
        self._request("DELETE", f"/api/v1/tags/{tag_id}")

    def update_workflow_tags(self, workflow_id: str, tag_ids: list[str]) -> None:
        """Update tags assigned to a workflow.

        Args:
            workflow_id: Workflow ID
            tag_ids: List of tag IDs to assign to the workflow

        Raises:
            APIError: If request fails
        """
        # Convert tag IDs to required format: [{"id": "tag-id"}, ...]
        tags_data = [{"id": tag_id} for tag_id in tag_ids]

        self._request(
            "PUT",
            f"/api/v1/workflows/{workflow_id}/tags",
            json_data=tags_data,
        )
