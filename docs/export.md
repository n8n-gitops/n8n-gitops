---
sidebar_position: 3
title: Export
---

# Export Command

The `export` command downloads all workflows from your n8n instance and saves them locally in **mirror mode**.

## Usage

```bash
n8n-gitops export
```

## Mirror Mode

The export command operates in **mirror mode**, which means:

✅ **Always exports ALL workflows** from your n8n instance
✅ **Deletes local workflows** that don't exist in n8n
✅ **Deletes orphaned script files** when switching modes
✅ **Updates the manifest** to match remote state exactly

This ensures your local repository is always a perfect mirror of your n8n instance.

## Externalize Code Setting

Code externalization is controlled by the `externalize_code` flag in `n8n/manifests/workflows.yaml` (default: `true`).

- `externalize_code: true` → Extract code to `n8n/scripts/` and insert include directives in workflow JSON (default behavior).
- `externalize_code: false` → Keep code inline in workflow JSON; script directories are removed on export.

Adjust the manifest before running `n8n-gitops export` to switch modes.

## Examples

### Basic Export

Export all workflows with inline code:

```bash
n8n-gitops export
```

Result:
```
n8n/
├── workflows/
│   ├── workflow1.json
│   └── workflow2.json
├── credentials.yaml
└── manifests/
    └── workflows.yaml
```

### Export with Code Externalization (default)

With `externalize_code: true` in `n8n/manifests/workflows.yaml` (default), export produces:
```
n8n/
├── workflows/
│   ├── workflow1.json (contains @@n8n-gitops:include directives)
│   └── workflow2.json
├── scripts/
│   ├── workflow1/
│   │   ├── process_data.py
│   │   └── transform.js
│   └── workflow2/
│       └── helper.py
├── credentials.yaml
└── manifests/
    └── workflows.yaml
```

### Switching Between Modes

- **Go inline:** Set `externalize_code: false` in `n8n/manifests/workflows.yaml`, then run `n8n-gitops export` (scripts are removed; workflows contain inline code).
- **Go back to externalized:** Set `externalize_code: true` in `n8n/manifests/workflows.yaml`, then run `n8n-gitops export` (scripts are regenerated; workflows reference include directives).

## What Gets Exported

### Workflow Files

Each workflow is saved as a JSON file in `n8n/workflows/`:
- Filename is sanitized from workflow name
- File contains normalized JSON (stable formatting)
- Volatile fields are stripped (id, createdAt, updatedAt, etc.)

### Manifest

The manifest file `n8n/manifests/workflows.yaml` is updated with:
- Workflow names
- File paths (relative to `n8n/`)
- Active state
- Tags

Example:
```yaml
workflows:
  - name: "Payment Processing"
    file: "workflows/payment-processing.json"
    active: true
    tags:
      - production
      - payments
  - name: "Data Sync"
    file: "workflows/data-sync.json"
    active: false
    tags: []
```

### Credentials Documentation

The export command automatically generates `n8n/credentials.yaml` to document which credentials are used by your workflows. This file is **informational only** and helps you understand credential dependencies across your workflows.

**What's included:**
- Credential type (e.g., `postgres`, `slack`, `httpHeaderAuth`)
- Credential name (as configured in n8n)
- List of workflows using each credential

**Example:**
```yaml
postgres:
  - name: Production DB
    workflows:
      - Data Sync
      - Payment Processing
  - name: Analytics DB
    workflows:
      - Reporting Workflow
slack:
  - name: Team Notifications
    workflows:
      - Alert System
      - Status Updates
httpHeaderAuth:
  - name: External API Key
    workflows:
      - Data Import
```

#### Inferred Credentials

When credentials haven't been configured in n8n yet (common with imported template workflows), n8n-gitops infers required credentials from node types and parameters. These appear under a separate `_inferred` section:

```yaml
_inferred:
  gmail:
  - node_type: n8n-nodes-base.gmail
    source: node_type
    workflows:
    - My Workflow
  facebookGraphApi:
  - node_type: n8n-nodes-base.httpRequest
    source: parameter
    workflows:
    - Social Media Workflow
```

Each entry includes:
- **node_type** - The n8n node type that requires this credential
- **source** - How the credential was inferred: `parameter` (from `nodeCredentialType`) or `node_type` (from the node type name)
- **workflows** - Which workflows need this credential

Once you configure the credentials in n8n and re-export, they will move from `_inferred` to the configured section with their actual names.

**Important notes:**
- This file is **documentation only** and is not used during deployment
- Credentials themselves (API keys, passwords, etc.) are **never exported**
- Credentials must be manually configured in each n8n instance
- The file is regenerated on each export based on workflow analysis

**File location:**
```
n8n/
├── credentials.yaml  ← Generated credential documentation
├── workflows/
│   └── *.json
└── manifests/
    └── workflows.yaml
```

### Script Files (when `externalize_code` is true)

Code is extracted from these node fields:
- `pythonCode` → `.py` files
- `jsCode` → `.js` files
- `code` → `.js` files
- `functionCode` → `.js` files

Script file naming:
- Format: `{node-name}.{ext}`
- Example: `Process_Data.py`
- Saved in: `n8n/scripts/{workflow-name}/`

## Mirror Mode Behavior

### Deleting Workflows

If a workflow exists locally but not in n8n:

```bash
n8n-gitops export
```

Output:
```
🗑  Deleting local workflow not in remote: Old Workflow
    → Deleted scripts directory: scripts/Old_Workflow/
```

### Deleting Script Files

When `externalize_code` is `false`, export removes script directories to keep the repo aligned with inline code:

```
🗑  Deleting scripts directory (inline code mode): scripts/workflow1/
🗑  Deleting scripts directory (inline code mode): scripts/workflow2/
```

### Overwriting Files

When `externalize_code` is `true`, script files are overwritten on each export (no `_1`, `_2` suffixes).

## Output Example

```
Exporting workflows from https://n8n.example.com
Target directory: /path/to/project/n8n/workflows

Fetching workflows...
Found 3 workflow(s)

Exporting 3 workflow(s) (mirror mode)...
Code externalization: ENABLED

  Exporting: Payment Processing
    ✓ Externalized 2 code block(s)
      → Externalized pythonCode from node 'Process Payment' to scripts/Payment_Processing/Process_Payment.py
      → Externalized jsCode from node 'Transform Data' to scripts/Payment_Processing/Transform_Data.js
    ✓ Saved to: n8n/workflows/Payment_Processing.json

  Exporting: Data Sync
    ✓ Saved to: n8n/workflows/Data_Sync.json

  Exporting: Email Notifications
    ✓ Externalized 1 code block(s)
      → Externalized pythonCode from node 'Format Email' to scripts/Email_Notifications/Format_Email.py
    ✓ Saved to: n8n/workflows/Email_Notifications.json

Generating credentials documentation...
  ✓ Documented 3 credential(s) in n8n/credentials.yaml

Updating manifest...
  ✓ Updated manifest: n8n/manifests/workflows.yaml

✓ Export complete! Exported 3 workflow(s)
✓ Externalized 3 code block(s) to script files

Next steps:
  1. Review the exported workflows
  2. Review the externalized scripts in n8n/scripts/ (when `externalize_code` is true)
  3. git add n8n/
  4. git commit -m 'Export workflows from n8n'
```

## Authentication

The export command requires authentication. See [Authentication](authentication.md) for details.

## See Also

- [Code Externalization](code-externalization.md) - Learn about include directives
- [Manifest File](manifest.md) - Understand the manifest format
- [Deployment](deployment.md) - Deploy workflows back to n8n
