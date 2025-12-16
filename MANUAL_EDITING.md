# Manual Editing Guide

This guide covers best practices for manually editing workflow files and how to avoid common pitfalls.

## Safe Manual Editing

### ✅ Safe to Edit

These fields and sections are safe to manually edit in workflow JSON files:

- **`name`**: Workflow name
- **`active`**: Whether workflow is active (true/false)
- **`nodes`**: Array of workflow nodes
  - Node parameters
  - Node positions
  - Code fields (or replace with `@@n8n-gitops:include` directives)
- **`connections`**: Node connections
- **`settings`**: Workflow settings
- **`tags`**: Array of tag strings

### ❌ DO NOT Edit (n8n-Managed Fields)

These fields are automatically managed by n8n and should **never** be manually added or edited:

- **`id`**: Workflow ID (auto-generated)
- **`createdAt`**: Creation timestamp
- **`updatedAt`**: Update timestamp
- **`versionId`**: Version identifier
- **`shared`**: Sharing/permissions data
- **`isArchived`**: Archive status
- **`triggerCount`**: Execution counter
- **`meta`**: Metadata (if null, remove it)
- **`pinData`**: Test data (if empty, remove it)
- **`staticData`**: Static data (if null, remove it)

## Why These Fields Cause Problems

When you export a workflow directly from n8n, it includes metadata fields that n8n manages internally. If you try to send these fields back during an update/deploy, the n8n API will reject the request with:

```
HTTP 400: {'message': 'request/body must NOT have additional properties'}
```

**n8n-gitops automatically strips these fields during deployment**, but it's best practice to not have them in your workflow files at all.

## Recommended Workflow

### 1. Always Export Using n8n-gitops

Instead of copying workflow JSON directly from n8n's UI or database:

```bash
# Export workflows cleanly
n8n-gitops export --all --externalize-code

# Or export specific workflows
n8n-gitops export --names "My Workflow" --externalize-code
```

This ensures exported files don't contain problematic fields.

### 2. Validate Before Committing

Before committing manually edited workflows:

```bash
# Validate and check for issues
n8n-gitops validate

# Strict validation
n8n-gitops validate --strict
```

This will warn you about n8n-managed fields:

```
⚠ Workflow My workflow contains n8n-managed fields that will cause
  deployment errors: versionId, shared, isArchived, meta (null/empty),
  pinData (null/empty), staticData (null/empty), triggerCount.
  These fields are automatically stripped during deployment, but you
  should remove them from the workflow file.
  Re-export with: n8n-gitops export --names "My workflow" [--externalize-code]
```

### 3. Use Dry-Run Before Deploying

Always preview your deployment:

```bash
# See what would be deployed
n8n-gitops deploy --dry-run

# Then deploy for real
n8n-gitops deploy
```

## Common Manual Editing Scenarios

### Scenario 1: Changing Workflow Name

**Safe approach:**

```json
{
  "name": "New Workflow Name",
  "nodes": [...],
  "connections": {...}
}
```

### Scenario 2: Adding a New Node

**Safe approach:**

```json
{
  "nodes": [
    {
      "name": "New Node",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "https://api.example.com"
      },
      "position": [500, 300]
    }
  ]
}
```

**Note**: Node IDs are optional for new nodes; n8n will generate them.

### Scenario 3: Modifying Code

**Option A**: Edit inline code directly

```json
{
  "parameters": {
    "jsCode": "console.log('updated code');"
  }
}
```

**Option B**: Use include directive (recommended)

```json
{
  "parameters": {
    "jsCode": "@@n8n-gitops:include scripts/my-workflow/process.js sha256=..."
  }
}
```

### Scenario 4: Copying Workflow from n8n UI

If you copy JSON directly from n8n's UI, it will contain problematic fields.

**Wrong approach:**
```bash
# Copy from n8n UI → Paste into file → Deploy
# ❌ This will include all n8n-managed fields
```

**Right approach:**
```bash
# Use export command
n8n-gitops export --names "Workflow Name" --externalize-code

# Edit the exported file
vim n8n/workflows/Workflow_Name.json

# Validate
n8n-gitops validate

# Deploy
n8n-gitops deploy
```

## Fixing Problematic Files

If you have a workflow file with n8n-managed fields:

### Quick Fix: Re-export

The easiest solution is to re-export the workflow:

```bash
n8n-gitops export --names "Problematic Workflow" --externalize-code
```

This will overwrite the file with a clean version.

### Manual Fix: Remove Fields

If you want to keep manual changes, remove the problematic fields:

```bash
# Edit the workflow file
vim n8n/workflows/my-workflow.json

# Remove these fields if present:
# - id, createdAt, updatedAt, versionId
# - shared, isArchived, triggerCount
# - meta (if null), pinData (if empty), staticData (if null)

# Validate
n8n-gitops validate

# Deploy
n8n-gitops deploy
```

### Automated Fix: Use jq

If you have many files to clean:

```bash
# Clean a single workflow file
jq 'del(.id, .createdAt, .updatedAt, .versionId, .shared, .isArchived, .triggerCount, .meta, .pinData, .staticData)' \
  n8n/workflows/my-workflow.json > temp.json && mv temp.json n8n/workflows/my-workflow.json

# Or clean all workflows
for file in n8n/workflows/*.json; do
  jq 'del(.id, .createdAt, .updatedAt, .versionId, .shared, .isArchived, .triggerCount, .meta, .pinData, .staticData)' \
    "$file" > temp.json && mv temp.json "$file"
done
```

## What n8n-gitops Does Automatically

During deployment, n8n-gitops **automatically**:

1. ✅ Strips all n8n-managed fields
2. ✅ Removes null/empty problematic fields
3. ✅ Renders include directives to inline code
4. ✅ Sends only the fields n8n API expects

**This means your deployment will succeed even if your files have problematic fields**, but you'll get warnings during validation.

## Best Practices Summary

1. ✅ **Always use `n8n-gitops export`** instead of copying from n8n UI
2. ✅ **Run `n8n-gitops validate`** before committing manual changes
3. ✅ **Use `--dry-run`** to preview deployments
4. ✅ **Keep workflow files clean** by removing n8n-managed fields
5. ✅ **Re-export workflows** periodically to get the cleanest version
6. ❌ **Never manually add** `id`, `createdAt`, `updatedAt`, etc.
7. ❌ **Don't copy JSON** directly from n8n's export/UI

## Getting Help

If deployment fails:

1. Check the error message - it often tells you what's wrong
2. Run `n8n-gitops validate` to see warnings
3. Try re-exporting: `n8n-gitops export --names "Your Workflow"`
4. Use `--dry-run` to preview: `n8n-gitops deploy --dry-run`

Example error with helpful tip:

```
✗ Error: API request failed: PUT /api/v1/workflows/abc123 -> HTTP 400:
  {'message': 'request/body must NOT have additional properties'}

💡 Tip: The workflow file may contain n8n-managed fields.
Run 'n8n-gitops validate' to check for problematic fields.
Re-export the workflow to get a clean version:
  n8n-gitops export --names "My Workflow" --externalize-code
```

## See Also

- [Main README](README.md)
- [Code Externalization Guide](EXTERNALIZATION_GUIDE.md)
- [Example Project](examples/demo-project/)
