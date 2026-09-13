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
| Old labels or behavior after an upgrade | A previously cached page or still-open tab may be running the old frontend | Save pending edits, reload, and if necessary hard-refresh once. Verify all application processes use the same release. Do not clear application data or delete the database. |

Frontend HTML, JavaScript, CSS, and the tab icon now use `Cache-Control: no-cache`: browsers can retain files, but must revalidate them before normal reuse. Matching ETags still return body-free HTTP 304 responses, avoiding repeated full downloads. This is not a live-update mechanism for already-open tabs and does not retroactively invalidate files cached under an older release's policy. Browser history restoration and a proxy configured to override origin headers need separate checks. See [MDN's cache-control reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control#no-cache).

Analytics bars use SVG geometry and external CSS so the strict `style-src 'self'` security policy can remain enabled. Do not add `unsafe-inline` to conceal styling errors; investigate any new console violations and confirm the browser loaded the intended release.

Useful commands:

```powershell
python -m app.doctor
python -m app.reconcile
python -m app.operator_control status
python -m app.support_bundle --output .tmp\autoposter-support.zip
python scripts\release_gate.py --json
```

Support bundles contain summaries and configuration-presence booleans only. They must not contain listing content, user emails, raw database URLs, tokens, or secret values.
