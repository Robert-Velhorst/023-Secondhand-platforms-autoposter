# Fresh-Clone Dry Run

Date: 2026-08-08

Commit verified: `7107e4293217df2bac44e9bd113e026f689870b0`

Clone source:

```text
https://github.com/Robert-Velhorst/023-Secondhand-platforms-autoposter.git
```

Clone target:

```text
C:\Users\NO\Documents\Codex\2026-07-13\lo\work\repo\.tmp\fresh-clone-7107e42
```

## Commands Run

```bash
git -c http.sslBackend=openssl clone --branch agent/production-launch-hardening --single-branch https://github.com/Robert-Velhorst/023-Secondhand-platforms-autoposter.git .tmp/fresh-clone-7107e42
cd .tmp/fresh-clone-7107e42
python scripts/verify.py
```

The first verification attempt was discarded because it inherited the source checkout working
directory. The recorded result below is from a second run whose pytest `rootdir` was the fresh
clone path shown above.

## Result

Fresh-clone verification passed at commit `7107e4293217df2bac44e9bd113e026f689870b0`.

- Ruff lint: passed.
- Python compile checks: passed.
- Pytest suite: passed, 210 tests.
- Doctor: database, uploads, adapters, and legacy isolation passed.
- Expected warnings: development default secret and the brand-new local SQLite database not yet
  stamped at Alembic head `20260808_0012`.

GitHub Verify and Supply Chain workflows also passed for the same commit. This proves the pushed
implementation can be cloned and verified independently. It does not prove target deployment,
PostgreSQL migration, backup/restore, manual accessibility, real-user acceptance, or official
marketplace publication.
