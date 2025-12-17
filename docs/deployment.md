# Deployment

Deploy workflows from your Git repository to your n8n instance.

## Deploy Command

```bash
n8n-gitops deploy [options]
```

## Basic Usage

### Deploy from Working Tree

Deploy workflows from your current working directory:

```bash
n8n-gitops deploy
```

### Deploy from Git Reference

Deploy workflows from a specific Git tag, branch, or commit:

```bash
# Deploy from a tag
n8n-gitops deploy --git-ref v1.0.0

# Deploy from a branch
n8n-gitops deploy --git-ref main

# Deploy from a commit
n8n-gitops deploy --git-ref abc123def
```

This reads workflow files, scripts, and manifests directly from Git history using `git show` - no checkout required.

### Dry Run

Preview what would be deployed without making changes:

```bash
n8n-gitops deploy --dry-run
```

## Options

### `--git-ref <ref>`

Deploy from a specific Git reference (tag, branch, or commit).

```bash
n8n-gitops deploy --git-ref v1.0.0
```

### `--dry-run`

Show deployment plan without making changes.

```bash
n8n-gitops deploy --dry-run
```

Output:
```
Deployment plan:
  + CREATE: New Workflow
  ⟳ REPLACE: Existing Workflow
      ✓ Include: scripts/existing/process.py

[DRY RUN] No changes made
```

### `--backup`

Backup old workflows by renaming them with a timestamp before replacing:

```bash
n8n-gitops deploy --backup
```

Behavior:
- Old workflow is renamed to `[BKP 2025-01-15 14:30:00] Workflow Name`
- New workflow is created with the original name
- Old workflow remains in n8n (deactivated)

### `--prune`

Delete workflows in n8n that are not in the manifest:

```bash
n8n-gitops deploy --prune
```

**Warning**: This will permanently delete workflows. Use with caution.

## Deployment Process

### 1. Load and Validate

1. Loads authentication credentials
2. Creates snapshot from Git ref (or working tree)
3. Loads manifest from `n8n/manifests/workflows.yaml`
4. Validates workflow files and include directives

### 2. Fetch Remote State

1. Connects to n8n API
2. Lists all remote workflows
3. Creates name-to-ID mapping

### 3. Plan Deployment

For each workflow in manifest:
- **CREATE**: Workflow doesn't exist in n8n
- **REPLACE**: Workflow exists, will be deleted and recreated

The deployment plan is displayed before execution (unless `--dry-run`).

### 4. Execute Deployment

For each workflow:

1. **Render workflow**:
   - Load workflow JSON
   - Resolve `@@n8n-gitops:include` directives
   - Inject code from script files
   - Remove read-only fields

2. **Create or Replace**:
   - **CREATE**: Create new workflow via API
   - **REPLACE**:
     - With `--backup`: Rename old → Create new
     - Without `--backup`: Delete old → Create new

3. **Set Active State**:
   - Call `/api/v1/workflows/{id}/activate` if `active: true`
   - Call `/api/v1/workflows/{id}/deactivate` if `active: false`

### 5. Prune (Optional)

If `--prune` is specified, delete workflows in n8n that are not in the manifest.

## Deployment Strategies

### Replace Strategy (Default)

The default strategy deletes old workflows and creates new ones:

```bash
n8n-gitops deploy
```

**Pros:**
- Clean slate for each deployment
- Guaranteed consistency with Git state
- No merge conflicts

**Cons:**
- Workflow ID changes
- Execution history is lost
- Webhooks URLs change

### Replace with Backup

Keep old workflows as backups:

```bash
n8n-gitops deploy --backup
```

**Pros:**
- Can recover if deployment goes wrong
- Execution history preserved in backup

**Cons:**
- Accumulates backup workflows over time
- Need to manually clean up old backups

## Example Output

```
Deploying workflows from /path/to/project
Using git ref: v1.0.0
Target: https://n8n.example.com

Loaded manifest: 2 workflow(s)

Fetching remote workflows...
Found 1 remote workflow(s)

Deployment plan:
  + CREATE: New Payment Workflow
  ⟳ REPLACE: Existing Data Sync
      ✓ Include: scripts/Existing_Data_Sync/process_pythonCode.py

Executing deployment...
  Creating: New Payment Workflow...
    ✓ Created with ID: abc123
    Activating workflow...
    ✓ Activated

  Replacing: Existing Data Sync...
    Deleting old workflow...
    ✓ Old workflow deleted
    Creating new workflow...
    ✓ Created with ID: def456
    Deactivating workflow...
    ✓ Deactivated

✓ Deployment successful!
```

## Active State Management

The deployment process manages workflow active state based on the manifest:

```yaml
# n8n/manifests/workflows.yaml
workflows:
  - name: "Production Workflow"
    file: "workflows/production.json"
    active: true  # Will be activated after deployment

  - name: "Test Workflow"
    file: "workflows/test.json"
    active: false  # Will be deactivated after deployment
```

After creating/replacing a workflow:
1. If `active: true` → POST to `/api/v1/workflows/{id}/activate`
2. If `active: false` → POST to `/api/v1/workflows/{id}/deactivate`

## Include Directives

Workflows with include directives are automatically rendered during deployment:

```json
{
  "nodes": [
    {
      "parameters": {
        "pythonCode": "@@n8n-gitops:include scripts/payment/process.py"
      }
    }
  ]
}
```

The include directive is resolved and replaced with the actual code before deployment.

See [Code Externalization](code-externalization.md) for details.

## Rollback Command

The `rollback` command is an alias for `deploy --git-ref`:

```bash
# These are equivalent:
n8n-gitops rollback --git-ref v0.9.0
n8n-gitops deploy --git-ref v0.9.0
```

## Error Handling

### Validation Errors

If workflow validation fails:

```
Error rendering workflow Payment Processing: Include path outside scripts/
```

Fix the issue in your repository and try again.

### API Errors

If the n8n API returns an error:

```
✗ Error: API request failed: POST /api/v1/workflows -> HTTP 400:
{"message": "Additional properties are not allowed"}

💡 Tip: The workflow file may contain n8n-managed fields.
Run 'n8n-gitops validate' to check for problematic fields.
Re-export the workflow to get a clean version:
  n8n-gitops export --externalize-code
```

Common fixes:
1. Re-export the workflow: `n8n-gitops export`
2. Run validation: `n8n-gitops validate`
3. Check API credentials

## Authentication

The deploy command requires authentication. See [Authentication](authentication.md) for details.

## See Also

- [Export](export.md) - Export workflows from n8n
- [Manifest File](manifest.md) - Understand the manifest format
- [Code Externalization](code-externalization.md) - Learn about include directives
- [Validation](commands.md#validate) - Validate before deployment
