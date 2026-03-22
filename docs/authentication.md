---
sidebar_position: 2
title: Authentication
---

# Authentication

n8n-gitops requires API credentials to connect to your n8n instance.

## Authentication Methods

Authentication credentials are resolved in this priority order:

1. **CLI flags**: `--api-url` and `--api-key`
2. **Config profiles**: `--config <name>` (saved via `n8n-gitops configure`)
3. **Environment variables**: `N8N_API_URL` and `N8N_API_KEY`

## Method 1: Config Profiles (Recommended for multiple instances)

Save named profiles for different n8n instances:

```bash
# Save a profile
n8n-gitops configure --config dev \
  --api-url https://n8n-dev.example.com \
  --api-key your-dev-key \
  --insecure

n8n-gitops configure --config prod \
  --api-url https://n8n-prod.example.com \
  --api-key your-prod-key

# Use a profile
n8n-gitops export --config dev
n8n-gitops deploy --config prod --git-ref v1.0.0
```

Profiles are saved to `.n8n-gitops.yaml` in the repo root. This file is gitignored by default since it contains API keys.

## Method 2: CLI Flags

Pass credentials directly via command-line flags:

```bash
n8n-gitops export \
  --api-url https://your-n8n-instance.com \
  --api-key your-api-key-here
```

This method overrides all other authentication sources, including config profiles.

## Method 3: Environment Variables

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

## Getting Your API Key

To get your n8n API key:

1. Log in to your n8n instance
2. Go to **Settings** → **API**
3. Create a new API key
4. Copy the key (you won't be able to see it again)

## Self-Signed Certificates

If your n8n instance uses a self-signed SSL certificate, use the `--insecure` flag or save it in a config profile:

```bash
# Via flag
n8n-gitops export --insecure

# Or save in profile
n8n-gitops configure --config dev --api-url URL --api-key KEY --insecure
n8n-gitops export --config dev
```

**Warning**: This disables SSL certificate verification for all requests. Only use this when connecting to trusted instances with self-signed certificates.

## Security Best Practices

1. **Never commit** `.n8n-gitops.yaml` to version control (gitignored by default)
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
1. You have a config profile set up (`n8n-gitops configure --config <name>`)
2. Or environment variables `N8N_API_URL` and `N8N_API_KEY` are set
3. Or you're passing `--api-url` and `--api-key` flags

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
