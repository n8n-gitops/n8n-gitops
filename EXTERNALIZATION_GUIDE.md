# Code Externalization Guide

This guide explains how to use the code externalization feature to manage Python and JavaScript code in separate files instead of inline in workflow JSON.

## Overview

When you export workflows from n8n, code nodes typically contain inline code directly in the JSON. The `--externalize-code` flag automatically:

1. **Detects** inline code in workflow nodes
2. **Extracts** it to separate script files
3. **Replaces** inline code with include directives
4. **Generates** SHA256 checksums for verification

## Quick Start

### Export with Code Externalization

```bash
# Export all workflows and externalize their code
n8n-gitops export --all --externalize-code
```

### Example Transformation

**Before** (inline code in workflow JSON):
```json
{
  "name": "Code in JavaScript",
  "parameters": {
    "jsCode": "for (const item of $input.all()) {\n  item.json.myNewField = 1;\n}\nreturn $input.all();"
  },
  "type": "n8n-nodes-base.code"
}
```

**After** (with include directive):
```json
{
  "name": "Code in JavaScript",
  "parameters": {
    "jsCode": "@@n8n-gitops:include scripts/My_Workflow/Code_in_JavaScript_jsCode.js sha256=4dead6f6..."
  },
  "type": "n8n-nodes-base.code"
}
```

**Script file** created at `n8n/scripts/My_Workflow/Code_in_JavaScript_jsCode.js`:
```javascript
for (const item of $input.all()) {
  item.json.myNewField = 1;
}
return $input.all();
```

## Supported Code Fields

The following code field types are automatically detected and externalized:

| Field Name | Language | File Extension |
|------------|----------|----------------|
| `pythonCode` | Python | `.py` |
| `jsCode` | JavaScript | `.js` |
| `code` | JavaScript | `.js` |
| `functionCode` | JavaScript | `.js` |

## Directory Structure

Externalized code is organized by workflow:

```
n8n/
├── workflows/
│   └── my-workflow.json          # Workflow with include directives
├── scripts/
│   └── My_Workflow/              # Workflow-specific directory
│       ├── Node_Name_jsCode.js   # JavaScript from "Node Name"
│       └── Process_pythonCode.py # Python from "Process" node
└── manifests/
    └── workflows.yaml
```

## Workflow Example

### 1. Export from n8n

```bash
n8n-gitops export --all --externalize-code
```

Output:
```
Exporting 1 workflow(s)...
Code externalization: ENABLED

  Exporting: Data Processing Pipeline
      → Externalized jsCode from node 'Transform Data' to scripts/Data_Processing_Pipeline/Transform_Data_jsCode.js
      → Externalized pythonCode from node 'Process Records' to scripts/Data_Processing_Pipeline/Process_Records_pythonCode.py
    ✓ Externalized 2 code block(s)
    ✓ Saved to: n8n/workflows/Data_Processing_Pipeline.json

✓ Export complete! Exported 1 workflow(s)
✓ Externalized 2 code block(s) to script files
```

### 2. Edit the Script Files

Now you can edit the code in your favorite editor with syntax highlighting, linting, etc.:

```python
# n8n/scripts/Data_Processing_Pipeline/Process_Records_pythonCode.py

def process_record(item):
    """Process a single record."""
    # Your improved logic here
    item.json['processed'] = True
    item.json['timestamp'] = datetime.now().isoformat()
    return item

# Main execution
results = [process_record(item) for item in items]
return results
```

### 3. Commit to Git

```bash
git add n8n/
git commit -m "Externalize workflow code for better version control"
git tag v1.1.0
```

### 4. Deploy

When you deploy, the code is automatically included:

```bash
n8n-gitops deploy --git-ref v1.1.0
```

The deploy command:
1. Reads the workflow JSON with include directives
2. Loads the script files from the specified paths
3. Verifies SHA256 checksums
4. Replaces directives with actual code
5. Deploys to n8n with the code inline

## Checksum Verification

Each include directive includes a SHA256 checksum:

```
@@n8n-gitops:include scripts/MyWorkflow/code.js sha256=4dead6f6933d04491997edd6604c224c52d2e0333a9b8d677dbae224bc8b6a42
```

Benefits:
- **Integrity**: Ensures code hasn't been accidentally modified
- **Safety**: Deploy fails if checksums don't match (when `--enforce-checksum` is used)
- **Transparency**: Easy to see when code has changed in Git diffs

### Update Checksums After Editing

When you edit a script file, you need to update the checksum in the workflow JSON:

```bash
# Generate new checksum
sha256sum n8n/scripts/MyWorkflow/code.js

# Update the workflow JSON with the new checksum
# Or re-export to automatically update checksums
```

## Best Practices

### 1. **Use Meaningful Node Names**

Node names become part of the script filename:
```
Node: "Transform Customer Data"
→ File: Transform_Customer_Data_jsCode.js
```

### 2. **Organize by Workflow**

Each workflow gets its own scripts directory, preventing conflicts:
```
scripts/
├── Customer_Processing/
│   └── transform.js
└── Invoice_Generation/
    └── transform.js  # No conflict!
```

### 3. **Validate Before Deploying**

```bash
# Validate with checksum enforcement
n8n-gitops validate --enforce-checksum

# Validate strict mode (all warnings become errors)
n8n-gitops validate --strict --enforce-no-inline-code --require-checksum
```

### 4. **Git Workflow**

```bash
# 1. Export with externalization
n8n-gitops export --all --externalize-code

# 2. Review changes
git diff

# 3. Commit
git add n8n/
git commit -m "feat: externalize workflow code"

# 4. Tag
git tag v2.0.0

# 5. Deploy
n8n-gitops deploy --git-ref v2.0.0 --dry-run  # Preview
n8n-gitops deploy --git-ref v2.0.0            # Apply
```

## Advanced Usage

### Selective Externalization

If you want to externalize only specific workflows:

```bash
# Export specific workflows with externalization
n8n-gitops export --names "Workflow A,Workflow B" --externalize-code
```

### Manual Externalization

You can also manually create include directives:

1. Create your script file:
   ```bash
   mkdir -p n8n/scripts/MyWorkflow
   echo 'console.log("Hello from external file")' > n8n/scripts/MyWorkflow/hello.js
   ```

2. Generate checksum:
   ```bash
   sha256sum n8n/scripts/MyWorkflow/hello.js
   ```

3. Update workflow JSON:
   ```json
   {
     "parameters": {
       "jsCode": "@@n8n-gitops:include scripts/MyWorkflow/hello.js sha256=<checksum>"
     }
   }
   ```

### Validation Modes

```bash
# Warn about inline code (default)
n8n-gitops validate

# Fail on inline code
n8n-gitops validate --enforce-no-inline-code

# Require all includes to have checksums
n8n-gitops validate --require-checksum

# Fail on checksum mismatches
n8n-gitops validate --enforce-checksum

# All validations enabled
n8n-gitops validate --strict --enforce-no-inline-code --require-checksum --enforce-checksum
```

## Troubleshooting

### Checksum Mismatch

**Error**: `Checksum mismatch for scripts/MyWorkflow/code.js`

**Solution**: The script file has been modified. Either:
1. Revert the changes to match the checksum
2. Update the checksum in the workflow JSON
3. Re-export the workflow to automatically update the checksum

### Include File Not Found

**Error**: `Include file not found: scripts/MyWorkflow/code.js`

**Solution**: Ensure the script file exists at the specified path relative to `n8n/`.

### Path Traversal Error

**Error**: `Include path cannot contain '..'`

**Solution**: Include paths must be under `scripts/` and cannot use `..` for security.

## Migration Guide

### Migrating Existing Workflows

If you have existing workflows with inline code:

1. **Export with externalization**:
   ```bash
   n8n-gitops export --all --externalize-code
   ```

2. **Review the changes**:
   ```bash
   git diff n8n/workflows/
   git status n8n/scripts/
   ```

3. **Test locally** (if possible):
   - Review the externalized scripts
   - Ensure logic is preserved
   - Check for any code that might have been split incorrectly

4. **Validate**:
   ```bash
   n8n-gitops validate --strict
   ```

5. **Deploy to test environment**:
   ```bash
   n8n-gitops deploy --dry-run
   n8n-gitops deploy
   ```

6. **Commit**:
   ```bash
   git add .
   git commit -m "chore: externalize workflow code"
   ```

## Benefits

✅ **Better Version Control**: Code changes are visible in Git diffs
✅ **IDE Support**: Use syntax highlighting, linting, and autocomplete
✅ **Code Reuse**: Share code between workflows
✅ **Testing**: Test code independently of workflows
✅ **Collaboration**: Review code changes in pull requests
✅ **Security**: Checksums verify code integrity
✅ **Organization**: Clear separation of workflow logic and implementation

## See Also

- [Main README](README.md) - General documentation
- [Example Project](examples/demo-project/) - Sample workflow with externalized code
- [Validation Guide](README.md#validate) - How to validate workflows
