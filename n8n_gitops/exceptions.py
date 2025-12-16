"""Common exceptions for n8n-gitops."""


class N8nGitOpsError(Exception):
    """Base exception for n8n-gitops."""
    pass


class ConfigError(N8nGitOpsError):
    """Configuration error."""
    pass


class ValidationError(N8nGitOpsError):
    """Validation error."""
    pass


class ManifestError(N8nGitOpsError):
    """Manifest parsing or validation error."""
    pass


class RenderError(N8nGitOpsError):
    """Workflow rendering error."""
    pass


class GitRefError(N8nGitOpsError):
    """Git ref snapshot error."""
    pass


class APIError(N8nGitOpsError):
    """n8n API error."""
    pass
