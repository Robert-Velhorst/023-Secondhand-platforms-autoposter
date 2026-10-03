# Post-Completion Maintenance Plan

- Weekly: review failed/paused jobs, worker heartbeat, dependency alerts, and storage capacity.
- Monthly: run dependency audit, database reconciliation, backup restore rehearsal in staging, and audit-retention purge.
- Per release: run full verification, browser critical path, migration upgrade/downgrade review, no-excuses search, support-bundle redaction test, and fresh-clone dry run.
- Per provider change: re-check official policy/terms, capabilities, required fields, cooldowns, manual wording, and credential checklist.
- Per schema change: include forward migration, downgrade decision, backup requirement, PostgreSQL validation, export/import compatibility, and reconciliation updates.

Version changes are recorded in `CHANGELOG.md`. Production incidents use the operator pause before retries or provider-side investigation.
