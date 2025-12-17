## **How `n8n-gitops` Aligns with GitOps Principles**

GitOps is not a toolset; it is a set of operational principles that treat Git as the authoritative source of truth for
systems that run in production. While GitOps originated in infrastructure and Kubernetes ecosystems, the same principles
apply naturally to workflow engines like n8n, where logic, side effects, and external integrations must be governed with
the same rigor as application code.

`n8n-gitops` was designed explicitly to apply these principles to n8n without changing how teams build workflows.

### **Git as the Single Source of Truth**

In a GitOps model, Git is the canonical representation of what should be running in production. The running system is
expected to converge toward what is defined in the repository, not the other way around.

With `n8n-gitops`, workflows are exported in mirror mode and committed to Git, making the repository the authoritative
description of workflow state. Production is never treated as a configuration source. Any change that is not represented
in Git is, by definition, undocumented and unsupported. This eliminates configuration drift and ensures that the state
of the system can always be reconstructed from version control.

### **Declarative Desired State**

GitOps favors declaring *what should exist*, not issuing imperative commands to mutate state manually.

The workflow manifest used by `n8n-gitops` describes which workflows exist, whether they should be active, and what
dependencies they require. Deployment is an act of reconciling the target n8n instance with that declared state. If a
workflow exists in Git, it will exist in n8n. If it does not, it will not. This declarative approach replaces ad hoc UI
actions with predictable reconciliation.

### **Change Through Pull Requests**

A core GitOps principle is that all changes flow through Git operations, typically pull requests, rather than direct
interaction with production systems.

By externalizing workflow logic and storing definitions in Git, `n8n-gitops` enables teams to review workflow changes
the same way they review application code. Logic changes are visible, diffable, and attributable. Approval becomes
explicit. Deployment becomes a consequence of merging, not a manual act performed by an individual with production
access.

### **Automated and Repeatable Deployments**

In GitOps, humans do not deploy to production; systems do.

`n8n-gitops` enforces this by making deployment an automated operation driven by a Git reference. A tag, branch, or
commit is deployed through the API, producing the same result every time. This removes ambiguity, reduces operational
risk, and ensures that environments can be promoted consistently using the same artifacts.

### **Auditability and Traceability**

GitOps provides a natural audit log through Git history.

Because every workflow change lives in Git, it becomes trivial to answer questions such as who changed a workflow, when
it changed, why it changed, and which version is currently running. This is especially important for workflows that
interact with external systems, financial operations, or customer data, where traceability is not optional.

### **Rollback as a First-Class Operation**

A system aligned with GitOps treats rollback as a normal operation, not an emergency procedure.

With `n8n-gitops`, rollback is simply redeploying a previous Git reference. There is no need to reconstruct state
manually or reverse UI actions. This lowers the cost of failure and encourages safer iteration, because recovery is
predictable and well understood.

### **Separation of Concerns Between Authoring and Operations**

GitOps draws a clear boundary between authoring changes and operating production systems.

In this model, n8n remains the authoring environment where workflows are designed and tested visually. Git becomes the
governance layer where changes are reviewed and approved. CI/CD becomes the execution layer that applies those changes.
Production access no longer implies deployment authority, which is a critical distinction for teams operating at scale.

### **Applying GitOps Beyond Infrastructure**

While GitOps is often associated with Kubernetes, its principles are not infrastructure-specific. Any system that
executes logic and causes side effects benefits from the same guarantees.

`n8n-gitops` applies GitOps where it is often missing: automation platforms. By doing so, it allows teams to adopt n8n
without lowering their operational standards or introducing special exceptions for “workflow code.”

## **Why This Matters**

When workflows can execute arbitrary code, trigger external APIs, and modify production data, treating them as
second-class citizens compared to application code is a mistake. GitOps provides a proven model for operating such
systems safely.

`n8n-gitops` exists to make that model practical for n8n, without sacrificing the usability that makes the platform
attractive in the first place.

## **GitOps Principles Mapping**

The table below summarizes how `n8n-gitops` maps core GitOps principles to concrete behavior in n8n, including where
manual intervention is intentionally required.

| GitOps Principle                       | How It Applies to n8n                                                                                   | How `n8n-gitops` Implements It                                                                                                                                              |
|----------------------------------------|---------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Git as single source of truth          | Workflow logic and configuration must be defined in version control, not inferred from a running system | Workflows are exported in mirror mode and stored in Git. Production state is always derived from the repository, never edited directly                                      |
| Declarative desired state              | The system should converge toward a declared state rather than being mutated imperatively               | A manifest defines which workflows exist, their activation state, and dependencies. Deployment reconciles n8n to this declared state                                        |
| Changes via pull requests              | Production changes must be reviewed and approved before being applied                                   | Workflow JSON and externalized code live in Git, enabling normal PR-based review, discussion, and approval                                                                  |
| Automated, repeatable deployment       | Deployments must be executed by automation, not humans                                                  | Workflows are deployed from a specific Git ref via the API, producing deterministic and repeatable results                                                                  |
| Auditability and traceability          | It must be possible to know who changed what and when                                                   | Git history provides a complete audit trail of workflow logic, structure, and deployment intent                                                                             |
| Rollback as a first-class operation    | Reverting changes should be simple and reliable                                                         | Rolling back is done by redeploying a previous Git tag, branch, or commit                                                                                                   |
| Separation of authoring and operations | Designing workflows should be decoupled from deploying them                                             | n8n is used as an IDE; Git and CI/CD own promotion and deployment                                                                                                           |
| Explicit handling of secrets           | Secrets must not be stored in Git or auto-provisioned without control                                   | Credentials are never exported or created automatically. Instead, `n8n-gitops` generates a manifest listing required credentials so they can be created manually and safely |

## **On Credentials and the One Intentional Manual Step**

Credentials are the only part of the system that is intentionally excluded from full automation. This is not an
oversight; it is a deliberate design decision aligned with security best practices.

n8n credentials often contain sensitive material such as API keys, tokens, and passwords. Automatically exporting,
versioning, or recreating them from Git would introduce unacceptable security risks and blur the boundary between
configuration and secrets.

To address this without compromising GitOps discipline, `n8n-gitops` analyzes workflows during export and generates a
credentials manifest that documents which credentials are required and which workflows depend on them. This makes
credential setup explicit, repeatable, and reviewable, while keeping secret material out of Git and out of automation
pipelines.

In practice, this means workflow logic and structure are fully GitOps-managed, while credentials are provisioned once
per environment through controlled, manual steps or external secret-management processes. This mirrors how GitOps is
commonly applied in infrastructure systems, where secrets are referenced declaratively but managed separately.

