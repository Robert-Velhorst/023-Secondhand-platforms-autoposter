# Stable dependency candidate — 24 October 2026

This is a review candidate, not a production release. It includes the pending
Python 3.15.1/certifi security changes from PR #119. That narrower PR remains
separate until a reviewed merge reconciles the branches.

## Version targets and reproducible installation

All 20 direct declarations across runtime, development, packaging, inactive
legacy dependencies and audit tooling were checked against public PyPI stable,
non-yanked releases. Fourteen declarations changed. Versions are exact pins,
including FastAPI 0.162.0, Uvicorn 0.54.0, SQLAlchemy 2.1.6, Alembic 1.20.1,
Psycopg 3.3.6, Pydantic Settings 2.16.1, boto3 1.43.118, Ruff 0.17.2,
PyInstaller 6.22.3 and pip-audit 2.10.1.

Python 3.15.1 is the selected runtime and packaging version. Ruff targets
Python 3.15; nine annotations were modernized for that target without
disabling rules. CI uses current pinned checkout 7.0.1, setup-python 7.1.0
and upload-artifact 7.0.2 releases. Linux CI selects Ubuntu 26.04. Existing
PostgreSQL integration uses the pinned 18.6 image; this is not proof of an
operator database engine upgrade.

The runtime, development and audit tool locks are universal for the selected
Python version. The Windows packaging lock targets CPython 3.15.1 win-amd64.
All contain hashes. Development, packaging and audit lock resolution uses the
runtime lock as a constraint. CI and Docker install from the locks with
`--require-hashes`. The audit reads every lock without re-resolving it.

The optional legacy manifest was updated, but its existing spaCy Python
version marker was retained. The retired Selenium automation remains
quarantined and is not imported, installed into the application profiles,
enabled or executed by this update. It is not qualified for Python 3.15.

## Windows packaging

For a new, isolated environment:

```powershell
py -3.15 -m venv .venv-build-candidate
./scripts/build-windows.ps1 -Python ./.venv-build-candidate/Scripts/python.exe
```

The script verifies exact CPython 3.15.1 win-amd64 before installation. An
existing older environment is rejected and preserved. When the default
environment is absent, `-BootstrapPython` may name the exact interpreter to
create it. No global Python installation is changed. A CI build retains the
candidate executable and SHA-256 checksum; a build alone does not establish
launcher, child-process, recovery, signing or installer acceptance.

## Recorded local evidence and remaining work

- Hash-verified installation of development and audit profiles succeeded in a
  separate Python 3.15.1 environment. The installed dependency check passed.
- Ruff lint and Python compilation passed after the annotation changes.
- Strict advisory scans of runtime, development, Windows packaging and audit
  locks reported no known vulnerabilities for the local Windows marker
  environment. Other platform branches still need their hosted checks. This
  does not cover native OS packages, inactive legacy packages or unknown
  vulnerabilities.
- The inspected interpreter actually embeds SQLite **3.53.1**, below the
  current 3.54.1 target. No database was opened by that version probe. The
  native library upgrade and migration/backup/recovery qualification remain
  required; the Python update alone does not satisfy them.
- Full application/PostgreSQL integration CI, Windows executable behavior,
  installed image inventories and scans, browser behavior, live provider
  integrations and deployment acceptance remain unqualified for this head.
- No application tests were run locally for this candidate. Earlier reports
  in the repository describe their own dated source commits.

No operator data, database, marketplace submission or deployment was changed.
Hetzner remains the deployment target under `DEPLOYMENT_TARGET.md`.

Primary package metadata: `https://pypi.org/pypi/<package>/json`. Exact archive
integrity values and selected versions are recorded in the committed locks.
