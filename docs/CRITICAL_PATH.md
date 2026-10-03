# Critical Path

The protected seller path is:

1. Register or sign in with bearer-session authentication.
2. Create a reusable listing; edits autosave after 1.2 seconds or can be saved explicitly.
3. Upload a validated real image.
4. Select a marketplace and optionally enter a platform-specific description override.
5. Run validation and resolve every missing field in the prepublish review.
6. Review compliance notes and the copy-ready package.
7. Queue an assisted package. The worker records logs, attempts, cooldowns, and truthful status.
8. Complete the provider-owned posting step manually.
9. Record the final marketplace URL and listing ID.
10. Review the published mapping, job history, audit history, analytics, and export.

## Automated evidence

- `tests/test_acceptance_workflow.py` covers the complete API-level seller path.
- `scripts/browser_e2e_workflow.cjs` covers the rendered workflow, image upload, manual completion, export, and deletion.
- `tests/test_action_center.py` proves onboarding and reminders are owner-scoped.
- `tests/test_operator_controls.py` proves an emergency pause prevents claims without killing worker observability.

## Failure expectations

- Missing fields produce validation details and fix actions, not success.
- Assisted jobs stop at `needs_user_action` until the user confirms a real provider-side result.
- Failed jobs retain logs and bounded retry guidance.
- Paused workers return paused readiness and do not claim queued jobs.
