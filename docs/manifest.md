---
sidebar_position: 6
title: Manifest File
---

# Manifest File

The manifest file (`n8n/manifests/workflows.yaml`) defines which workflows to deploy and their configuration.

## Location

```
n8n/manifests/workflows.yaml
```

This file is created automatically when you run `n8n-gitops export`.

## Format

The manifest is a YAML file with the following structure:

```yaml
# Code externalization setting (optional, default: true)
externalize_code: true

workflows:
  - name: "Workflow Name"
    active: true
    is_archived: false
    tags:
      - tag1
      - tag2
    requires_credentials:
      - credential-name
    requires_env:
      - ENV_VAR_NAME
```

## Fields

### `externalize_code` (optional, default: `true`)

Controls whether code from workflow nodes (Python, JavaScript) is extracted to separate files.

```yaml
externalize_code: true   # Extract code to n8n/scripts/ directory
externalize_code: false  # Keep code inline in workflow JSON
```

**When `true`**:
- Code is extracted to `n8n/scripts/{Workflow_Name}/{Node_Name}.py` or `.js`
- Workflow JSON contains include directives: `@@n8n-gitops:include scripts/path/file.ext`
- Better for version control (proper syntax highlighting, diffs)

**When `false`**:
- Code remains inline in workflow JSON files
- Simpler structure, all workflow data in one file

This setting is applied during `n8n-gitops export` and affects all workflows.

### `workflows` (required)

List of workflow specifications.

### Workflow Specification

Each workflow has the following fields:

#### `name` (required)

The workflow name. Must match the name in the workflow JSON file.

```yaml
name: "Payment Processing"
```

**Important**:
- Must be unique across all workflows
- Used to match with existing workflows in n8n
- Case-sensitive
- **Auto-generates the workflow file path**: The file path is automatically derived from the workflow name
  - Example: `"Payment Processing"` → `workflows/Payment_Processing.json`
  - Example: `"Data Sync - v2"` → `workflows/Data_Sync_-_v2.json`
  - Spaces become underscores, special characters are sanitized

#### `active` (optional, default: `false`)

Whether the workflow should be active (running) in n8n.

```yaml
active: true   # Workflow will be activated after deployment
active: false  # Workflow will be deactivated after deployment
```

The deployment process calls the appropriate API endpoint:
- `active: true` → POST `/api/v1/workflows/{id}/activate`
- `active: false` → POST `/api/v1/workflows/{id}/deactivate`

#### `is_archived` (optional, default: `false`)

Whether the workflow was archived in n8n at the time it was exported.

```yaml
is_archived: true
```

This is a **snapshot, not a control**: `n8n-gitops export` records it so archived state is visible in git without opening n8n, but `deploy` does not read this field — it queries the live archive state from the n8n API directly when deciding whether a workflow needs to be unarchived before updating it. Editing `is_archived` by hand has no effect; it will be overwritten on the next export.

To exclude archived workflows from export entirely instead of just flagging them, see [`--skip-archived`](export.md#skip-archived).

#### `tags` (optional, default: `[]`)

List of tags for the workflow.

```yaml
tags:
  - production
  - payments
  - critical
```

**Note**: Tags are informational in the manifest. They are not currently applied during deployment.

#### `requires_credentials` (optional, default: `[]`)

List of credential names required by this workflow.

```yaml
requires_credentials:
  - stripe-api
  - slack-webhook
  - postgres-db
```

**Note**: This is informational only. Credentials must be configured manually in n8n.

#### `requires_env` (optional, default: `[]`)

List of environment variable names required by this workflow.

```yaml
requires_env:
  - STRIPE_API_KEY
  - WEBHOOK_URL
  - DATABASE_URL
```

**Note**: This is informational only. Can be used with validation in the future.

## Example

```yaml
# Code externalization (default: true)
externalize_code: true

workflows:
  - name: "Payment Processing"
    active: true
    tags:
      - production
      - payments
    requires_credentials:
      - stripe-api
      - postgres-db
    requires_env:
      - STRIPE_WEBHOOK_SECRET

  - name: "Data Sync"
    active: false
    tags:
      - development
      - data
    requires_credentials:
      - google-sheets
    requires_env: []

  - name: "Email Notifications"
    active: true
    tags:
      - production
      - notifications
    requires_credentials:
      - smtp-server
    requires_env:
      - SMTP_HOST
      - SMTP_PORT
      - SMTP_USER
      - SMTP_PASS
```

**Note**: File paths are auto-generated from workflow names:
- `"Payment Processing"` → `workflows/Payment_Processing.json`
- `"Data Sync"` → `workflows/Data_Sync.json`
- `"Email Notifications"` → `workflows/Email_Notifications.json`

## Mirror Mode

When you run `n8n-gitops export`, the manifest is updated in **mirror mode**:

✅ New workflows are added
✅ Existing workflows are updated
✅ Workflows not in n8n are removed

This ensures the manifest always reflects the current state of your n8n instance.

## Validation

Validate your manifest before deployment:

```bash
n8n-gitops validate
```

This checks:
- Manifest file exists and is valid YAML
- Required fields (`name`) are present
- No duplicate workflow names
- Referenced workflow files exist (auto-generated from names)
- Workflow JSON is valid

## Deployment Behavior

During deployment (`n8n-gitops deploy`):

1. **Load manifest**: Read `n8n/manifests/workflows.yaml`
2. **Match workflows**: Match by `name` with existing workflows in n8n
3. **Create or Replace**:
   - If workflow doesn't exist: CREATE
   - If workflow exists: REPLACE (delete + create)
4. **Set active state**: Call activate/deactivate API based on `active` field

### Create

If a workflow name doesn't exist in n8n:

```yaml
workflows:
  - name: "New Workflow"
    active: true
```

Result:
- New workflow is created in n8n (reads from `workflows/New_Workflow.json`)
- Workflow is activated

### Replace

If a workflow name already exists in n8n:

```yaml
workflows:
  - name: "Existing Workflow"
    active: false
```

Result:
- Old workflow is deleted
- New workflow is created with same name (reads from `workflows/Existing_Workflow.json`)
- Workflow is deactivated
- **Note**: Workflow ID changes

### Prune

With `--prune` flag, workflows in n8n but not in manifest are deleted:

```bash
n8n-gitops deploy --prune
```

**Warning**: This permanently deletes workflows. Use with caution.

## Environment Schema

The manifest directory also contains `env.schema.json` for environment variable validation:

```
n8n/manifests/
├── workflows.yaml
└── env.schema.json
```

Example `env.schema.json`:
```json
{
  "required": ["N8N_API_URL", "N8N_API_KEY"],
  "vars": {
    "STRIPE_API_KEY": {
      "type": "string",
      "description": "Stripe API key for payment processing"
    },
    "DATABASE_URL": {
      "type": "string",
      "description": "PostgreSQL connection string"
    }
  }
}
```

**Note**: Environment schema validation is not yet implemented but planned for future releases.

## Best Practices

### 1. Keep Manifest in Sync

Always export to keep manifest up to date:

```bash
n8n-gitops export
```

The manifest will be updated automatically in mirror mode. Don't manually edit the manifest unless you know what you're doing.

### 2. Use Descriptive Names

Good:
```yaml
name: "Payment Processing - Stripe"
name: "Data Sync - Google Sheets to PostgreSQL"
```

Bad:
```yaml
name: "Workflow 1"
name: "Test"
```

### 3. Tag Workflows Appropriately

Use tags to organize workflows:

```yaml
tags:
  - production      # Production workflows
  - development     # Development/test workflows
  - critical        # Critical business processes
  - payments        # Payment-related workflows
  - data           # Data processing workflows
```

### 4. Document Requirements

Always list required credentials and environment variables:

```yaml
requires_credentials:
  - stripe-api
requires_env:
  - STRIPE_WEBHOOK_SECRET
```

This helps new team members understand dependencies.

### 5. Set Active State Carefully

Think about whether workflows should be active in each environment:

**Production:**
```yaml
name: "Payment Processing"
active: true  # Always active in production
```

**Development:**
```yaml
name: "Test Workflow"
active: false  # Inactive by default
```

## Troubleshooting

### Error: Duplicate workflow names

```
Error: Duplicate workflow name: Payment Processing
```

Fix: Ensure all workflow names in the manifest are unique.

### Error: Workflow file not found

```
Error: Workflow file not found: workflows/My_Workflow.json
```

Fix: The file path is auto-generated from the workflow name. Ensure:
1. The workflow JSON file exists in `n8n/workflows/`
2. The filename matches the sanitized workflow name (spaces → underscores)
3. Example: Workflow name `"My Workflow"` requires file `workflows/My_Workflow.json`

### Error: Invalid YAML

```
Error: Invalid YAML in manifest
```

Fix: Validate YAML syntax. Use an online YAML validator or:

```bash
python3 -c "import yaml; yaml.safe_load(open('n8n/manifests/workflows.yaml'))"
```

## See Also

- [Export](export.md) - Export workflows and update manifest
- [Deployment](deployment.md) - Deploy workflows from manifest
- [Commands](commands.md#validate) - Validate manifest
