# Requirements Traceability

The row-level source of truth is the 116-phase table in `docs/GOAL_COMPLETION_MATRIX.md`. This document maps phase groups to implementation surfaces and verification evidence.

| Phases | Requirement area | Primary implementation | Verification/evidence |
| --- | --- | --- | --- |
| 0-4 | Integrity, audit, product, critical path, architecture | Repository structure and FastAPI/static-dashboard design | `TECHNICAL_AUDIT.md`, `CRITICAL_PATH.md`, architecture/provenance tests |
| 5-9 | Data, configuration, authentication, ownership, API contracts | Models, schemas, config, security, middleware, dependencies | Migration, startup, auth, isolation, and API hardening tests |
| 10-14 | Frontend/core flow/provider honesty | `public/`, adapters, API/job service | Browser workflow, UI wording, no-mocks production tests |
| 15-19 | Storage, workers, idempotency, rates, audit | Storage service, jobs, worker, rate-limit, audit | Storage/worker/rate-limit/data-portability tests |
| 20-27 | Dashboard, forms, queries, portability, templates, suggestions, review, reminders | Dashboard/action center, listing autosave, local suggestion provider | Action-center, frontend-state, quality, query, acceptance tests |
| 28-36 | Privacy, web security, secrets, local/deploy, migrations, doctor, observability, diagnostics | Auth deletion/export, headers, secret references, Docker, Alembic, doctor, support bundle | Security, deployment, migrations, observability, support redaction tests |
| 37-48 | Demo/fake-lab/factories/test suites/adversarial/isolation/files/provider failure | Demo module, test fake provider, shared factories, full tests | Pytest suite and adversarial reports |
| 49-58 | Accessibility, responsive, performance, scale, backup, reconciliation, analytics, SaaS, i18n, flags | UI semantics/CSS, indexes, reconcile CLI, analytics/localization/flags | Browser matrix, accessibility, query, reconciliation, analytics tests |
| 59-67 | State/domain/invariants/safety/credentials/threat/privacy/supply chain/licenses | State service, models/schemas, prepublish UI, security and provider docs | State/invariant/prepublish/security/dependency evidence |
| 68-77 | CI, release, operations, help, troubleshooting, audits, debt, bug hunt | GitHub workflows, release gate, runbooks and audits | CI checks, release-gate tests, documentation contract tests |
| 78-88 | Red-team loops through context-loss safety | Review docs, goal matrix, task graph, worklog/checkpoints | Documentation truthfulness and traceability tests |
| 89-99 | Stabilization, DoD, clone/manual/final evidence, maintenance, roadmap | Gate docs/scripts and final evidence records | Verify/release/final-response gates and fresh-clone procedure |
| 100-105 | Provider cleanup, support bundle, retention, production migration, emergency stop, onboarding | Provider checklist, support/reconcile/operator CLIs, action center | Provider, support, operator, action-center tests |
| 106-115 | Scope decision, quality, decision minimization, exception dashboard, retries, ambiguity, versioning, regression, maintenance, operator readiness | Personal-account scope, suggestion provider, action center, job service, version/changelog | Quality/action-center/worker/full regression plus external operator gate |

The canonical matrix uses `Partial` or `Not applicable` whenever repository code cannot truthfully satisfy an external or out-of-scope phase. `docs/EXTERNAL_EVIDENCE_BACKLOG.md` contains every current `Partial` phase.
