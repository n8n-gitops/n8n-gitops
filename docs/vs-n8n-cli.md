---
sidebar_position: 9
title: n8n-gitops vs n8n-cli
---

# n8n-gitops vs n8n-cli

In May 2025, n8n released an official lightweight CLI package (`@n8n/cli`) — a REST API client separate from the full
n8n server binary. This page clarifies how it compares to n8n-gitops so you can choose the right tool for each use case.

> **Short answer:** they serve different purposes and complement each other. n8n-cli is an API client for interacting
> with n8n programmatically. n8n-gitops is a GitOps lifecycle management tool for operating n8n as a platform.

## Quick Comparison

| Capability                  | n8n-cli (`@n8n/cli`)                           | n8n-gitops                                       |
|-----------------------------|------------------------------------------------|--------------------------------------------------|
| **Purpose**                 | API client / CRUD operations                   | GitOps lifecycle management                      |
| **Install**                 | `npx @n8n/cli` (zero-install) or `npm i -g`    | `pip install n8n-gitops`                         |
| **CI/CD suitable**          | Partial (scripting and one-off operations)     | ✅ Full pipeline support                          |
| **Export format**           | Individual workflow JSON per request           | Structured directory layout, code separated      |
| **Code files**              | Embedded as escaped strings                    | Real `.js` / `.py` files under `scripts/`        |
| **Git diff readable**       | ✗                                              | ✅                                                |
| **PR / code review**        | Not meaningful                                 | Full diff, normal review                         |
| **Validation**              | None                                           | `validate --strict` before deploy                |
| **Deploy from Git ref**     | ✗                                              | ✅ Tag, branch, or commit                         |
| **Dry-run**                 | ✗                                              | ✅                                                |
| **Active state tracking**   | ✗                                              | ✅ Manifest-driven                                |
| **Drift correction**        | ✗                                              | ✅ `--prune` mode                                 |
| **Environment support**     | Named config profiles                          | Per-environment config with secrets separation   |
| **Rollback**                | ✗                                              | ✅ Redeploy a prior tag                           |
| **Credential visibility**   | List and schema — no secret values exported    | Dependency declared in YAML, secrets never touch Git |
| **Works against remote**    | ✅ REST API only, runs from any machine         | ✅ REST API only, runs from any machine           |
| **Executions management**   | ✅ list, get, retry, stop, delete              | ✗                                                |
| **Projects / variables**    | ✅ Full CRUD                                   | ✗                                                |
| **Data tables**             | ✅ rows, upsert, delete                        | ✗                                                |
| **Status**                  | Beta                                           | Alpha                                            |

## When n8n-cli Fits Best

- Scripting one-off operations: listing workflows, triggering executions, creating credentials programmatically.
- Building integrations or automation agents that need to interact with n8n on demand.
- Quickly inspecting an instance from the terminal without installing the full n8n package.
- Managing entities that n8n-gitops does not cover: executions, projects, variables, data tables, users.

```bash
# Zero-install: inspect workflows and executions
npx @n8n/cli workflow list
npx @n8n/cli execution list --status=error --limit=10

# Create a credential from a schema
npx @n8n/cli credential schema gmailOAuth2
npx @n8n/cli credential create --type=gmailOAuth2 --name='My Gmail' --file=cred.json
```

## When n8n-gitops Fits Best

- Treating n8n workflows as code: structured files, real diffs, meaningful PR reviews.
- Deploying from Git refs — tag-based promotion across dev, staging, and production environments.
- Enforcing a GitOps pipeline: validate on PR, dry-run on merge, deploy on tag.
- Correcting drift: ensuring the running n8n instance always matches what Git declares.
- Rollback without manual intervention: redeploy a prior tag in seconds.

```bash
# Full GitOps pipeline
n8n-gitops export                          # mirror n8n into Git
n8n-gitops validate --strict               # enforce contract before PR merge
n8n-gitops deploy --git-ref v1.2.0        # deploy immutable tag
n8n-gitops rollback --git-ref v1.1.0      # revert to prior state
```

## Using Both Together

The two tools are complementary. A typical platform engineering setup might use:

- **n8n-gitops** to manage the workflow deployment lifecycle (export, validate, deploy, rollback) via CI/CD.
- **n8n-cli** for operational tasks outside the deployment pipeline: inspecting failed executions, rotating credentials, 
  querying projects, or any ad hoc interaction with the n8n API.

Neither tool replaces the other. n8n-gitops does not manage executions or projects; n8n-cli does not provide a
GitOps deployment model.

## Key Differences Summarised

| Dimension          | n8n-cli                              | n8n-gitops                                |
|--------------------|--------------------------------------|-------------------------------------------|
| Model              | Imperative (do this now)             | Declarative (reconcile to this state)     |
| Primary interface  | Individual commands per entity       | Manifest + Git ref drives the full system |
| What it manages    | Any n8n entity via API               | Workflow lifecycle end-to-end             |
| GitOps semantics   | None                                 | Full (export → validate → PR → deploy → rollback) |