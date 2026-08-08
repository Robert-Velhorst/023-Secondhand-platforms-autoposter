# Troubleshooting and Error Catalog

| Symptom | Meaning | Safe next action |
| --- | --- | --- |
| Registration says invalid fields | Email/password failed schema validation | Use a deliverable-format email domain and at least eight password characters. |
| Validation reports missing images/fields | Package is intentionally not ready | Use each Fix action, save/autosave, and validate again. |
| Job is `needs_user_action` | Provider-owned posting step remains manual | Open the platform, submit deliberately, then record URL and listing ID. |
| Job failed | Worker retained an error and logs | Fix the reported cause; retry only when the UI says retry is safe. |
| Worker status is `paused` | Operator emergency stop is active | Inspect `python -m app.operator_control status`; resume only after the recorded incident is cleared. |
| Worker status is unhealthy | No recent worker heartbeat | Check process logs, database migration, configuration, and worker command. |
| Autosave failed | The edit remains visible but was not persisted | Check the error/request ID and use Save to retry after connectivity returns. |
| Migration mismatch | Database is not at Alembic head | Back up first, then run `alembic upgrade head`; do not enable auto-create in production. |

Useful commands:

```powershell
python -m app.doctor
python -m app.reconcile
python -m app.operator_control status
python -m app.support_bundle --output .tmp\autoposter-support.zip
python scripts\release_gate.py --json
```

Support bundles contain summaries and configuration-presence booleans only. They must not contain listing content, user emails, raw database URLs, tokens, or secret values.
