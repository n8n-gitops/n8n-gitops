# **Project Plan: `n8n-gitops` (Python) — GitOps CLI for n8n Community**

## **Scope**

Build an external CLI that:

* Creates a standard repo structure (`create-project`)

* Validates repo \+ manifests (`validate`)

* Exports workflows from an n8n instance (`export`)

* Deploys workflows from repo or a Git ref (`deploy`)

* “Rollback” by deploying a Git ref (`rollback`)

* Externalizes code from Code nodes via `@@n8n-gitops:include ...` \+ optional `sha256=...`

* Uses API-key auth via env vars, `.n8n-auth`, or CLI flags

Non-goals (v1):

* Credential secret migration (only validate presence by name where possible)

* Two-way code externalization on export (export will keep inline code)

---

## **Milestone 0 — Decisions & Conventions**

### **M0.1 Supported auth inputs (priority order)**

1. CLI flags: `--api-url`, `--api-key`

2. Environment: `N8N_API_URL`, `N8N_API_KEY`

3. `.n8n-auth` file in repo root

### **M0.2 Repo root and n8n root**

* Default repo root: current directory

* Default n8n root: `<repo>/n8n`

### **M0.3 Workflow identity**

* Match by exact workflow name from `manifests/workflows.yaml`

* Upsert strategy: list workflows → map name→id → update or create

### **M0.4 Code externalization path constraint**

* Includes must resolve under: `<repo>/n8n/scripts/**`

* Deny `..` and absolute paths

---

## **Milestone 1 — CLI skeleton and scaffolding**

### **Tasks**

1. Create python package \+ CLI entrypoint:

   * `n8n_gitops/cli.py` with subcommands using `argparse`

   * Console script entry: `n8n-gitops`

2. Implement `create-project`:

   * `n8n-gitops create-project <path>`

   * Creates structure \+ default files

### **Files to create**

* `pyproject.toml` (or `setup.cfg`) with console entrypoint

* `n8n_gitops/__init__.py`

* `n8n_gitops/cli.py`

* `n8n_gitops/commands/create_project.py`

### **Default files created by `create-project`**

`<path>/`  
  `n8n/`  
    `workflows/`  
    `manifests/`  
      `workflows.yaml`  
      `env.schema.json`  
    `scripts/`  
  `.gitignore`  
  `.n8n-auth.example`  
  `README.md`

**.gitignore**

`.n8n-auth`  
`.env`  
`__pycache__/`  
`*.pyc`

**.n8n-auth.example**

`N8N_API_URL=`  
`N8N_API_KEY=`

**n8n/manifests/workflows.yaml**

`workflows: []`

**n8n/manifests/env.schema.json**

`{`  
  `"required": ["N8N_API_URL", "N8N_API_KEY"],`  
  `"vars": {}`  
`}`

### **Acceptance criteria**

* Running `n8n-gitops create-project ./demo` creates the tree and files exactly as specified.

* `.n8n-auth` is not created automatically (only `.n8n-auth.example`).

---

## **Milestone 2 — Auth \+ config loading**

### **Tasks**

1. Implement auth loader:

   * Parse CLI args

   * Parse environment

   * Parse `.n8n-auth` (simple KEY=VALUE or INI-like)

2. Implement `.env` support:

   * If `--env-file` provided, load using `python-dotenv` (optional)

### **Files**

* `n8n_gitops/auth.py`

* `n8n_gitops/config.py`

### **Interfaces**

**`AuthConfig`**

`@dataclass`  
`class AuthConfig:`  
    `api_url: str`  
    `api_key: str`

**`load_auth(repo_root: Path, args: Namespace) -> AuthConfig`**

* Priority rules enforced

* Raises `ConfigError` if incomplete

### **Acceptance criteria**

* Auth resolves correctly across the three sources, with deterministic precedence.

* `.n8n-auth` is only read from repo root, never elsewhere.

---

## **Milestone 3 — Git ref snapshot reader**

### **Tasks**

1. Implement a file loader that can read:

   * From working tree (default)

   * From git ref using `git show <ref>:<path>`

2. Provide a unified interface for reading:

   * `n8n/manifests/workflows.yaml`

   * workflow JSON files

   * scripts includes

### **Files**

* `n8n_gitops/gitref.py`

### **Interfaces**

**`Snapshot`**

`class Snapshot(Protocol):`  
    `def read_text(self, rel_path: str) -> str: ...`  
    `def read_bytes(self, rel_path: str) -> bytes: ...`  
    `def exists(self, rel_path: str) -> bool: ...`

**Implementations**

* `WorkingTreeSnapshot(repo_root: Path)`

* `GitRefSnapshot(repo_root: Path, git_ref: str)` (uses subprocess `git show`)

### **Acceptance criteria**

* `--git-ref <tag>` causes deploy/validate to read manifest \+ workflows \+ scripts from that tag even if working tree differs.

* Errors are clear when a file is missing from the ref.

---

## **Milestone 4 — Manifest parsing \+ validation**

### **Tasks**

1. Parse YAML manifest:

   * Ensure `workflows` key exists and is a list

   * Ensure each entry has `name` and `file`

   * Ensure unique `name`

2. Resolve file paths relative to `<n8n root>/`

   * manifest uses `file: "workflows/abc.json"` (relative to `n8n/`)

### **Files**

* `n8n_gitops/manifest.py`

### **Interfaces**

**`WorkflowSpec`**

`@dataclass`  
`class WorkflowSpec:`  
    `name: str`  
    `file: str`  
    `active: bool = False`  
    `tags: list[str] = field(default_factory=list)`  
    `requires_credentials: list[str] = field(default_factory=list)`  
    `requires_env: list[str] = field(default_factory=list)`

**`Manifest`**

`@dataclass`  
`class Manifest:`  
    `workflows: list[WorkflowSpec]`

**`load_manifest(snapshot: Snapshot, n8n_root: str="n8n") -> Manifest`**

### **Acceptance criteria**

* Manifest errors list the entry index and missing field(s).

* Duplicate names fail validation.

---

## **Milestone 5 — JSON normalization**

### **Tasks**

1. Implement deterministic JSON output:

   * stable key ordering (recursive)

   * indent=2

   * newline at EOF

2. Implement “volatile field stripping” as configurable allow/deny list (safe defaults: do nothing unless fields exist)

### **Files**

* `n8n_gitops/normalize.py`

### **Interfaces**

* `normalize_json(obj: Any) -> str`

* `normalize_obj(obj: Any) -> Any` (returns deep-sorted dict/list)

### **Acceptance criteria**

* Running normalization twice produces identical output bytes.

* Git diffs are stable across platforms (LF newlines).

---

## **Milestone 6 — Code include grammar \+ renderer**

### **Placeholder grammar**

Stored in the workflow node code field as **single line**:

**Base**

`@@n8n-gitops:include <relative-path>`

**Checksum**

`@@n8n-gitops:include <relative-path> sha256=<hex>`

Constraints:

* `<relative-path>` must resolve under `n8n/scripts/**`

* no absolute paths

* no `..`

### **Regex (implementation detail)**

Use a strict regex:

* Directive:

  * `^@@n8n-gitops:include\s+([^\s]+)(?:\s+sha256=([a-fA-F0-9]{64}))?\s*$`

### **Tasks**

1. Implement include parser: `parse_include_directive(text: str) -> Optional[(path, sha256)]`

2. Implement path validation:

   * ensure under `n8n/scripts/**`

3. Implement hashing:

   * sha256 hex of raw file bytes normalized to LF (or hash raw bytes; pick one and document it—recommended: hash raw bytes)

4. Implement renderer:

   * walk nodes

   * find code fields

   * replace directive with file contents

   * apply rules: no-inline-code, checksum enforcement

### **Files**

* `n8n_gitops/render.py`

### **Interfaces**

**`RenderOptions`**

`@dataclass`  
`class RenderOptions:`  
    `enforce_no_inline_code: bool = False`  
    `enforce_checksum: bool = False`  
    `require_checksum: bool = False`  
    `add_generated_header: bool = True`

**`render_workflow_json(workflow: dict, snapshot: Snapshot, *, n8n_root="n8n", git_ref: str|None, options: RenderOptions) -> tuple[dict, list[dict]]`**

Render report item example:

`{`  
  `"node_name": "...",`  
  `"node_id": "...",`  
  `"field": "pythonCode",`  
  `"include_path": "scripts/payments/retry.py",`  
  `"sha256_expected": "...",`  
  `"sha256_actual": "...",`  
  `"status": "included" | "checksum_mismatch" | "inline_code" | "missing_file"`  
`}`

### **Code field detection**

Implement a conservative approach:

* If node has `parameters`, check these keys in order:

  * `pythonCode`

  * `jsCode`

  * `code`

  * `functionCode`

* If any exist and are strings, treat as code-bearing fields.  
   (Keep it extensible via config list.)

### **Validation rules (enforced in renderer/validate)**

* **No inline code**

  * If a code field is present and does not match include directive:

    * warn by default

    * fail if `enforce_no_inline_code=True`

* **Checksum enforcement**

  * If directive has sha256:

    * fail if mismatch when `enforce_checksum=True`

  * If directive has no sha256:

    * fail when `require_checksum=True`

### **Acceptance criteria**

* Placeholders correctly load from `n8n/scripts/**`

* Path traversal attempts fail

* Checksums verified

* Inline code triggers warning/fail depending on options

---

## **Milestone 7 — n8n API client**

### **Tasks**

1. Implement client with API key auth header

2. Implement operations:

   * `list_workflows() -> list[{id,name,...}]`

   * `get_workflow(id)`

   * `create_workflow(payload)`

   * `update_workflow(id, payload)`

   * `set_active(id, bool)`

3. Retry & error handling:

   * configurable retries (e.g. 3\) on 429/5xx

   * clear error messages with endpoint \+ response snippet

### **Files**

* `n8n_gitops/n8n_client.py`

### **Interfaces**

`class N8nClient:`  
    `def __init__(self, api_url: str, api_key: str, timeout: int = 30): ...`  
    `def list_workflows(self) -> list[dict]: ...`  
    `def get_workflow(self, workflow_id: str) -> dict: ...`  
    `def create_workflow(self, workflow: dict) -> dict: ...`  
    `def update_workflow(self, workflow_id: str, workflow: dict) -> dict: ...`  
    `def activate_workflow(self, workflow_id: str) -> None: ...`  
    `def deactivate_workflow(self, workflow_id: str) -> None: ...`

### **Acceptance criteria**

* Can connect to a real instance and list workflows

* Update/create works

* Activate/deactivate works

---

## **Milestone 8 — `validate` command**

### **Tasks**

1. Load snapshot (working tree or git ref)

2. Load manifest

3. For each workflow:

   * load JSON

   * parse

   * run `render_workflow_json` in validation mode

   * ensure normalization

4. Validate env schema:

   * load env vars (from `.env` optional \+ process env)

   * validate required keys and patterns/types (simple checks or JSONSchema)

### **Files**

* `n8n_gitops/commands/validate.py`

* `n8n_gitops/envschema.py` (or integrate into config)

### **CLI flags**

* `--strict` (turn warnings into failures)

* `--enforce-no-inline-code`

* `--enforce-checksum`

* `--require-checksum`

### **Acceptance criteria**

* `validate` fails on:

  * missing workflow file

  * malformed JSON

  * include path outside scripts

  * checksum mismatch when enforced

  * inline code when enforced

* `validate` warns on inline code when not enforced

---

## **Milestone 9 — `deploy` and `rollback`**

### **Tasks**

1. Load snapshot (git ref or working tree)

2. Load manifest

3. Resolve auth \+ instantiate client

4. Fetch remote workflows list; map name→id

5. For each workflow spec:

   * load JSON

   * render with include injection

   * normalize

   * upsert (create/update)

   * set active state

6. Dry run:

   * compute plan (create/update/activate/deactivate)

   * print report

   * no writes

### **Files**

* `n8n_gitops/commands/deploy.py`

* `n8n_gitops/commands/rollback.py`

### **Rollback behavior**

* Alias to deploy:

  * `rollback --git-ref <ref>` \== `deploy --git-ref <ref>`

### **Acceptance criteria**

* Deploy from `--git-ref` works without checking out that ref

* Dry run prints the plan and exits 0 without changes

* Workflow is matched by name and updated correctly

* Active state matches manifest

---

## **Milestone 10 — `export` (bootstrap/sync)**

### **Tasks**

1. Connect to n8n, list workflows

2. Export selected workflows:

   * `--all`

   * `--names "A,B,C"`

   * `--from-manifest`

3. Write normalized JSON to `n8n/workflows/*.json`

4. Optionally update manifest in `--all` mode (append entries if missing)

### **Files**

* `n8n_gitops/commands/export.py`

### **Notes (v1)**

* Export will store inline code as-is (n8n-native).

* Externalization back into scripts can be added later.

### **Acceptance criteria**

* Export writes normalized, stable JSON files

* Can export by name or all

---

## **Milestone 11 — Documentation & examples**

### **Tasks**

1. README:

   * Quickstart

   * Auth setup

   * Git ref deploy

   * Include directive usage \+ checksum

   * Recommended workflow practices (n8n as orchestrator)

2. Example include:

   * `n8n/scripts/example/hello.py`

   * workflow JSON using include directive

### **Acceptance criteria**

* New user can run:

  * `create-project`

  * configure `.n8n-auth`

  * `export --all`

  * edit \+ commit \+ tag \+ `deploy --git-ref tag`

---

## **Milestone 12 — Quality gates (tests)**

### **Minimum unit tests**

* Include directive parser

* Path traversal prevention

* Checksum match/mismatch

* Renderer replaces code correctly

* Normalizer stable output

* Manifest validation

Suggested tooling:

* `pytest`

---

# **CLI Usage Examples**

### **Create repo structure**

`n8n-gitops create-project .`

### **Deploy current working tree**

`export N8N_API_URL=https://n8n.example.com`  
`export N8N_API_KEY=xxxx`  
`n8n-gitops deploy`

### **Deploy a git tag**

`n8n-gitops deploy --git-ref release-2025-12-16`

### **Enforce “no inline code” and require checksums**

`n8n-gitops validate --strict --enforce-no-inline-code --require-checksum`

### **Code include example inside a code field**

`@@n8n-gitops:include scripts/payments/retry.py sha256=<64-hex>`  
