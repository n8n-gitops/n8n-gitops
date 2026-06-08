# GitHub Actions Examples

Three ready-to-use workflow files that implement the full n8n-gitops GitOps pipeline on GitHub Actions.

## Workflows

| File | Trigger | Purpose |
|---|---|---|
| `validate.yaml` | Pull request targeting `main` (paths: `n8n/**`) | Validate and dry-run on every PR touching workflows |
| `deploy.yaml` | Push of a `v*.*.*` tag + manual | Deploy the tagged ref to n8n |
| `sync.yaml` | Daily schedule (02:00 UTC) + manual | Sync n8n state back into Git (n8n is authoritative) |
| `drift.yaml` | Every 6 hours + manual | Detect when n8n deviates from Git state and fail |

## Setup

Add these secrets to your repository (`Settings → Secrets and variables → Actions`):

| Secret | Value |
|---|---|
| `N8N_BASE_URL` | Your n8n instance URL, e.g. `https://n8n.example.com` |
| `N8N_API_KEY` | Your n8n API key (`Settings → n8n API` inside n8n) |
| `GH_PAT` | A GitHub personal access token with `repo` scope (needed by `export.yaml` to push commits) |

Copy the files you need into your repository's `.github/workflows/` directory.

## Pipeline Flow

```
PR opened            → validate.yaml   → validate --strict + deploy --dry-run
PR merged            → (no deploy yet)
git tag v1.2.0       → deploy.yaml     → validate --strict + deploy --git-ref v1.2.0
daily 02:00 UTC      → sync.yaml       → export + commit any changes back to Git
every 6 hours        → drift.yaml      → export + diff + fail if prod != Git
```

## Sync vs Drift Detection

These two workflows look similar but answer opposite questions:

**`sync.yaml`** — "What is running in n8n? Commit it."
Exports whatever is in n8n and commits it to Git. n8n is treated as the source of truth. Useful when the team
edits workflows directly in the n8n UI and wants Git as an audit trail and backup.

**`drift.yaml`** — "Does n8n match what Git says it should? Fail if not."
Exports the current n8n state and diffs it against Git without committing anything. Git is the source of truth.
The job fails with a full diff if production has deviated — signalling an unauthorized or untracked change.

Pick one model and stick to it. Running both simultaneously will cause `drift.yaml` to fire every time `sync.yaml`
commits a change that was not made through Git.

To act on drift failures, add a notification step after the diff check:

```yaml
- name: Notify on drift
  if: failure()
  uses: slackapi/slack-github-action@v2
  with:
    payload: '{"text":"⚠️ n8n drift detected — production does not match Git state: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"}'
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```