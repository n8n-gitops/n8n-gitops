# Authentication

n8n-gitops requires API credentials to connect to your n8n instance.

## Authentication Methods

Authentication credentials are resolved in this priority order:

1. **CLI flags**: `--api-url` and `--api-key`
2. **Environment variables**: `N8N_API_URL` and `N8N_API_KEY`
3. **`.n8n-auth` file** in repository root

## Method 1: CLI Flags

Pass credentials directly via command-line flags:

```bash
n8n-gitops export \
  --api-url https://your-n8n-instance.com \
  --api-key your-api-key-here
```

This method overrides all other authentication sources.

## Method 2: Environment Variables

Set environment variables:

```bash
export N8N_API_URL=https://your-n8n-instance.com
export N8N_API_KEY=your-api-key-here

n8n-gitops export
```

Or use a `.env` file with a tool like `direnv`:

```bash
# .env
N8N_API_URL=https://your-n8n-instance.com
N8N_API_KEY=your-api-key-here
```

## Method 3: .n8n-auth File (Recommended)

Create a `.n8n-auth` file in your repository root:

```bash
cp .n8n-auth.example .n8n-auth
```

Edit `.n8n-auth`:
```
N8N_API_URL=https://your-n8n-instance.com
N8N_API_KEY=your-api-key-here
```

**Important**: The `.n8n-auth` file is gitignored by default to prevent accidentally committing secrets.

### .n8n-auth File Format

The file supports:
- Simple `KEY=VALUE` format
- Comments with `#`
- Empty lines
- Values with or without quotes

Example:
```bash
# n8n API Configuration
N8N_API_URL=https://your-n8n-instance.com
N8N_API_KEY="your-api-key-here"

# Optional: Custom timeout
# TIMEOUT=60
```

## Getting Your API Key

To get your n8n API key:

1. Log in to your n8n instance
2. Go to **Settings** → **API**
3. Create a new API key
4. Copy the key (you won't be able to see it again)

## Security Best Practices

1. **Never commit** `.n8n-auth` to version control
2. **Use environment variables** in CI/CD pipelines
3. **Rotate API keys** regularly
4. **Use separate API keys** for different environments (dev, staging, prod)
5. **Limit API key permissions** if your n8n version supports it

## CI/CD Usage

For CI/CD pipelines, use environment variables:

```yaml
# GitHub Actions example
- name: Deploy workflows
  run: n8n-gitops deploy --git-ref ${{ github.ref }}
  env:
    N8N_API_URL: ${{ secrets.N8N_API_URL }}
    N8N_API_KEY: ${{ secrets.N8N_API_KEY }}
```

```yaml
# GitLab CI example
deploy:
  script:
    - n8n-gitops deploy --git-ref $CI_COMMIT_TAG
  variables:
    N8N_API_URL: $N8N_API_URL
    N8N_API_KEY: $N8N_API_KEY
```

## Troubleshooting

### Error: Missing credentials

If you see this error:
```
Error: Missing N8N_API_URL or N8N_API_KEY
```

Check that:
1. Your `.n8n-auth` file exists and is in the repository root
2. The file has the correct format (KEY=VALUE)
3. Both `N8N_API_URL` and `N8N_API_KEY` are set

### Error: Authentication failed

If you see authentication errors:
1. Verify your API key is correct
2. Check that your n8n instance URL is accessible
3. Ensure the API key hasn't been revoked
4. Test the API key manually with curl:

```bash
curl 'https://your-n8n-instance.com/api/v1/workflows' \
  --header 'X-N8N-API-KEY: your-api-key-here'
```
