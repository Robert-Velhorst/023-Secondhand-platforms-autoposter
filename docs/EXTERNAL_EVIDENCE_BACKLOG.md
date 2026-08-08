# External Evidence Backlog

This is the single list of `Partial` rows in `docs/GOAL_COMPLETION_MATRIX.md`.

| Phase | Evidence required | Capture location |
| --- | --- | --- |
| 30 | Target secret-manager configuration, access policy, and rotation rehearsal. | `docs/RELEASE_EVIDENCE_RECORD.md` |
| 32 | Target host, deployed SHA, API/worker process proof, HTTPS/CORS/storage configuration. | `docs/RELEASE_EVIDENCE_RECORD.md` |
| 33 | Alembic upgrade and rollback decision against target PostgreSQL. | `docs/RELEASE_EVIDENCE_RECORD.md` |
| 53 | Target backup and restore rehearsal followed by reconciliation. | `docs/RELEASE_EVIDENCE_RECORD.md` |
| 69 | Canary deployment and rollback evidence from the selected host. | `docs/RELEASE_EVIDENCE_RECORD.md` |
| 81 | Observed real non-technical user walkthrough. | `docs/NON_TECHNICAL_USER_WALKTHROUGH_RECORD.md` |
| 92 | Fresh-clone verification at the final pushed commit. | `docs/FRESH_CLONE_DRY_RUN.md` |
| 93 | Manual keyboard, 200% zoom, screen-reader, and operator verification results. | `docs/BROWSER_ACCESSIBILITY_QA.md` and `docs/RELEASE_EVIDENCE_RECORD.md` |
| 94 | Repeat final no-excuses search after all other launch evidence. | `docs/FINAL_NO_EXCUSES_SEARCH.md` |
| 100 | Official-provider credentials, account approval, sandbox lifecycle proof, and cleanup evidence if official publishing is enabled. | `docs/OFFICIAL_API_CREDENTIAL_CHECKLIST.md` |
| 103 | Production PostgreSQL/storage/worker migration and cutover proof. | `docs/RELEASE_EVIDENCE_RECORD.md` |
| 115 | Named human operator completes the runbook and signs readiness. | `docs/FINAL_ACCEPTANCE_RECORD.md` |

Current status: blocked on external evidence for final production launch. Run `python scripts/release_gate.py --json` for the launch-record fields still marked `Not captured`. The repository must not synthesize these observations.

Before the final handoff, repeat `docs/FINAL_NO_EXCUSES_SEARCH.md` and validate every statement in
`docs/FINAL_RESPONSE_REQUIREMENTS.md`.
