# Example n8n-gitops Project

This is a demo project showing how to use n8n-gitops with code externalization.

## Structure

```
demo-project/
├── n8n/
│   ├── workflows/
│   │   └── example-workflow.json    # Workflow using include directive
│   ├── manifests/
│   │   ├── workflows.yaml            # Workflow manifest
│   │   └── env.schema.json           # Environment schema
│   └── scripts/
│       └── example/
│           └── hello.py              # External Python code
└── README.md
```

## Code Externalization Example

The workflow `example-workflow.json` contains a Code node with this directive:

```
@@n8n-gitops:include scripts/example/hello.py
```

When deployed, this directive is replaced with the contents of `n8n/scripts/example/hello.py`.

## Try It Out

1. Configure your n8n credentials:
   ```bash
   export N8N_API_URL=https://your-n8n-instance.com
   export N8N_API_KEY=your-api-key
   ```

2. Validate the workflow:
   ```bash
   n8n-gitops validate --repo-root .
   ```

3. Deploy to n8n:
   ```bash
   n8n-gitops deploy --repo-root .
   ```

## Adding Checksums

To add SHA256 checksums for verification:

1. Generate the checksum:
   ```bash
   sha256sum n8n/scripts/example/hello.py
   ```

2. Update the directive in the workflow JSON:
   ```
   @@n8n-gitops:include scripts/example/hello.py sha256=<hash-here>
   ```

3. Validate with checksum enforcement:
   ```bash
   n8n-gitops validate --enforce-checksum --repo-root .
   ```
