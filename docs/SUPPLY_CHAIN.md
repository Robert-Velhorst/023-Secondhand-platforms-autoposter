# Supply Chain And Dependencies

The production application dependencies are declared in `requirements.txt`. Test and lint tools are isolated in `requirements-dev.txt`, and legacy browser-automation dependencies remain isolated in `requirements-legacy.txt`; neither is installed in the production image.

The Windows standalone build installs `requirements-build.lock.txt`, a complete
Python 3.13 x64 Windows dependency resolution with hashes, using pip's
`--require-hashes` mode. `requirements-build.txt` remains the human-maintained
input constraints file. Refresh the lock deliberately with uv for the build
target, review the complete diff, and rebuild/test the Windows executable before
shipping; do not edit resolved transitive pins by hand.

## Vulnerability Audit

Run the dependency audit with:

```bash
python -m pip install pip-audit==2.9.0
python scripts/audit_dependencies.py
```

The script audits `requirements.txt` and `requirements-build.lock.txt` with
`pip-audit --strict`. The GitHub Actions workflow `.github/workflows/supply-chain.yml` runs the same audit on pushes, pull requests, a weekly schedule, and manual dispatch.

GitHub Actions dependencies are pinned to immutable commit SHAs for their documented Node 24
releases. The container base image is digest-pinned. Dependabot checks Python, GitHub Actions, and
Docker dependencies weekly. Workflows use
read-only repository permissions, concurrency cancellation, and explicit job timeouts.

## Dependency Rules

- Pin direct dependencies unless a bounded compatibility range is intentional.
- Keep legacy Selenium/browser automation dependencies out of the production install.
- Do not add marketplace SDKs until official API credentials, sandbox tests, and the credential checklist are ready.
- Treat audit failures as release blockers unless a documented temporary exception is approved.
- Document any exception with package name, advisory ID, reason, compensating controls, owner, and expiry date.

## Current Exceptions

None.
