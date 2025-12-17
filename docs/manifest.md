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
workflows:
  - name: "Workflow Name"
    file: "workflows/filename.json"
    active: true
    tags:
      - tag1
      - tag2
    requires_credentials:
      - credential-name
    requires_env:
      - ENV_VAR_NAME
```

## Fields

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

#### `file` (required)

Path to the workflow JSON file, relative to `n8n/` directory.

```yaml
file: "workflows/payment-processing.json"
```

Always use forward slashes (`/`), even on Windows.

#### `active` (optional, default: `false`)

Whether the workflow should be active (running) in n8n.

```yaml
active: true   # Workflow will be activated after deployment
active: false  # Workflow will be deactivated after deployment
```

The deployment process calls the appropriate API endpoint:
- `active: true` → POST `/api/v1/workflows/{id}/activate`
- `active: false` → POST `/api/v1/workflows/{id}/deactivate`

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
workflows:
  - name: "Payment Processing"
    file: "workflows/payment-processing.json"
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
    file: "workflows/data-sync.json"
    active: false
    tags:
      - development
      - data
    requires_credentials:
      - google-sheets
    requires_env: []

  - name: "Email Notifications"
    file: "workflows/email-notifications.json"
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
- Required fields (`name`, `file`) are present
- No duplicate workflow names
- Referenced workflow files exist
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
    file: "workflows/new-workflow.json"
    active: true
```

Result:
- New workflow is created in n8n
- Workflow is activated

### Replace

If a workflow name already exists in n8n:

```yaml
workflows:
  - name: "Existing Workflow"
    file: "workflows/existing-workflow.json"
    active: false
```

Result:
- Old workflow is deleted
- New workflow is created with same name
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
n8n-gitops export --externalize-code
```

Don't manually edit the manifest unless you know what you're doing.

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
Error: Workflow file not found: workflows/missing.json
```

Fix: Ensure the `file` path is correct and the file exists.

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
