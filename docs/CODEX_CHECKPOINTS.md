# Codex Checkpoints and Resume Safety

## Current checkpoint

- Working branch: `agent/production-launch-hardening`
- Starting commit for the 116-phase run: `0fa6d38`
- Canonical phase record: `docs/GOAL_COMPLETION_MATRIX.md`
- Authoritative local gate: `python scripts/verify.py`
- Production gate: `python scripts/release_gate.py --json`
- Critical path: `docs/CRITICAL_PATH.md`

## Resume procedure

1. Inspect `git status --short`, branch, HEAD, remote, and recent log.
2. Preserve unrelated working-tree changes; do not reset them.
3. Read this file, the goal matrix, worklog, external evidence backlog, and final verification report.
4. Run focused tests for the area being changed, then the full verification gate.
5. Repeat browser QA after visible UI changes.
6. Update the matrix and verification evidence in the same commit.
7. Never mark production launch complete while `scripts/release_gate.py` reports blocked.
