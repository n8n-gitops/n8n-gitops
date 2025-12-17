# Code Externalization

Store Python/JavaScript code in separate files instead of inline in workflow JSON, making code easier to version control, review, and maintain.

## Overview

Instead of storing code inline in workflow JSON:

```json
{
  "nodes": [
    {
      "parameters": {
        "pythonCode": "def process(data):\n    return data.upper()\n\nresult = process(input)"
      }
    }
  ]
}
```

Store it in separate files:

**Workflow JSON:**
```json
{
  "nodes": [
    {
      "parameters": {
        "pythonCode": "@@n8n-gitops:include scripts/my-workflow/process_data_pythonCode.py"
      }
    }
  ]
}
```

**Script file (`n8n/scripts/my-workflow/process_data_pythonCode.py`):**
```python
def process(data):
    return data.upper()

result = process(input)
```

## Benefits

✅ **Better version control**: See actual code diffs, not escaped JSON strings
✅ **Code review**: Review Python/JavaScript in native format
✅ **IDE support**: Syntax highlighting, linting, autocomplete
✅ **Reusability**: Share code between workflows
✅ **Testing**: Test code independently of workflows

## Include Directive Syntax

### Basic Syntax

```
@@n8n-gitops:include <path>
```

Where `<path>` is relative to `n8n/` directory and must be under `scripts/`.

### Examples

```
@@n8n-gitops:include scripts/payments/retry.py
@@n8n-gitops:include scripts/utilities/format.js
@@n8n-gitops:include scripts/my-workflow/helper_pythonCode.py
```

### Path Rules

✅ **Allowed:**
- `scripts/payments/process.py`
- `scripts/my-workflow/transform.js`
- `scripts/utils/helpers/format.py`

❌ **Not allowed:**
- `../secrets.txt` (path traversal)
- `/etc/passwd` (absolute path)
- `config/api-keys.json` (not under scripts/)

## Exporting with Externalization

Use `--externalize-code` flag to extract code when exporting:

```bash
n8n-gitops export --externalize-code
```

This will:
1. Detect inline code in workflow nodes
2. Extract code to separate files in `n8n/scripts/<workflow-name>/`
3. Replace inline code with include directives
4. Use appropriate file extensions (`.py` for Python, `.js` for JavaScript)

### Supported Code Fields

Code is extracted from these node parameter fields:

| Field | Extension | Example Node Type |
|-------|-----------|-------------------|
| `pythonCode` | `.py` | Code (Python) |
| `jsCode` | `.js` | Code (JavaScript) |
| `code` | `.js` | Function, Function Item |
| `functionCode` | `.js` | Function (legacy) |

### File Naming

Format: `{node-name}_{field-name}.{ext}`

Examples:
- Node "Process Data" with `pythonCode` → `Process_Data_pythonCode.py`
- Node "Transform" with `jsCode` → `Transform_jsCode.js`
- Node "Calculate-Price" with `code` → `Calculate_Price_code.js`

## Directory Structure

```
my-n8n-project/
├── n8n/
│   ├── workflows/
│   │   ├── payment-processing.json
│   │   └── data-sync.json
│   ├── scripts/
│   │   ├── payment-processing/
│   │   │   ├── validate_payment_pythonCode.py
│   │   │   ├── retry_logic_pythonCode.py
│   │   │   └── format_response_jsCode.js
│   │   └── data-sync/
│   │       └── transform_data_pythonCode.py
│   └── manifests/
│       └── workflows.yaml
```

## Switching Between Modes

### From Inline to Externalized

```bash
# Export with inline code
n8n-gitops export

# Switch to externalized code
n8n-gitops export --externalize-code
```

Result:
- Script files are created in `n8n/scripts/`
- Workflow JSON updated with include directives

### From Externalized to Inline

```bash
# Export with externalized code
n8n-gitops export --externalize-code

# Switch to inline code
n8n-gitops export
```

Result:
- Script files are deleted from `n8n/scripts/`
- Workflow JSON updated with inline code

## Deployment with Includes

During deployment, include directives are automatically resolved:

```bash
n8n-gitops deploy
```

The deployment process:
1. Reads workflow JSON
2. Detects `@@n8n-gitops:include` directives
3. Loads referenced script files
4. Replaces directives with actual code
5. Deploys to n8n with inline code

**Important**: n8n always receives workflows with inline code. Include directives are a Git-only feature.

## Example Workflow

### 1. Export with Externalization

```bash
n8n-gitops export --externalize-code
```

### 2. Edit Script File

Edit `n8n/scripts/payment-processing/validate_payment_pythonCode.py`:

```python
def validate_payment(amount, currency):
    """Validate payment parameters."""
    if amount <= 0:
        raise ValueError("Amount must be positive")

    if currency not in ["USD", "EUR", "GBP"]:
        raise ValueError(f"Unsupported currency: {currency}")

    return {"valid": True, "amount": amount, "currency": currency}

# Main execution
payment = items[0].json
result = validate_payment(payment["amount"], payment["currency"])
```

### 3. Commit Changes

```bash
git add n8n/scripts/payment-processing/validate_payment_pythonCode.py
git commit -m "Improve payment validation logic"
git tag v1.1.0
```

### 4. Deploy

```bash
n8n-gitops deploy --git-ref v1.1.0
```

The updated code is automatically injected into the workflow during deployment.

## Workflow JSON Example

### Before Externalization

```json
{
  "name": "Payment Processing",
  "nodes": [
    {
      "name": "Validate Payment",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "pythonCode": "def validate(amount):\n    if amount <= 0:\n        raise ValueError('Invalid')\n    return amount\n\nresult = validate(items[0].json.amount)"
      }
    },
    {
      "name": "Format Response",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "const format = (data) => {\n  return { status: 'ok', data };\n};\n\nreturn format(items[0].json);"
      }
    }
  ]
}
```

### After Externalization

**Workflow JSON:**
```json
{
  "name": "Payment Processing",
  "nodes": [
    {
      "name": "Validate Payment",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "pythonCode": "@@n8n-gitops:include scripts/payment-processing/Validate_Payment_pythonCode.py"
      }
    },
    {
      "name": "Format Response",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "@@n8n-gitops:include scripts/payment-processing/Format_Response_jsCode.js"
      }
    }
  ]
}
```

**`n8n/scripts/payment-processing/Validate_Payment_pythonCode.py`:**
```python
def validate(amount):
    if amount <= 0:
        raise ValueError('Invalid')
    return amount

result = validate(items[0].json.amount)
```

**`n8n/scripts/payment-processing/Format_Response_jsCode.js`:**
```javascript
const format = (data) => {
  return { status: 'ok', data };
};

return format(items[0].json);
```

## Best Practices

### 1. Always Use Externalization in Git

```bash
# Always export with externalization for Git
n8n-gitops export --externalize-code
```

This gives you the best version control experience.

### 2. Use Descriptive Node Names

Good:
- "Validate Payment Data"
- "Transform User Input"
- "Format API Response"

Bad:
- "Code"
- "Python"
- "Node 1"

Node names become part of filenames, so make them descriptive.

### 3. Keep Scripts Directory Clean

Don't manually create files in `n8n/scripts/`. Always use:
```bash
n8n-gitops export --externalize-code
```

### 4. Add Comments

Since code is in separate files, add proper comments:

```python
"""
Validate payment data before processing.

Checks:
- Amount is positive
- Currency is supported
- Required fields are present
"""
def validate_payment(data):
    # Implementation...
```

### 5. Test Scripts Independently

You can test extracted scripts with standard Python/JavaScript tools:

```bash
# Python
python3 n8n/scripts/payment/validate_pythonCode.py

# JavaScript
node n8n/scripts/payment/format_jsCode.js
```

## Validation

Validate include directives before deployment:

```bash
n8n-gitops validate
```

This checks:
- Include paths are valid
- Referenced files exist
- Paths don't escape `scripts/` directory
- No path traversal attempts

## See Also

- [Export](export.md) - Export workflows with externalization
- [Deployment](deployment.md) - Deploy workflows with includes
- [Manifest File](manifest.md) - Workflow manifest format
