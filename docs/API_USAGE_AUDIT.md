# API Usage Audit

This audit maps the FastAPI surface to visible frontend usage, tests, and remaining gaps.

## Summary

- Frontend entrypoint: `public/app.js`
- API implementation: `app/api.py`
- Current UI coverage: dashboard, listings, queue, accounts, settings, export/import
- Current test coverage: API smoke flow, hardening, auth, storage, worker, revisions, category mappings, data portability, diagnostics, listing quality

## Route Map

| Method | Route | Frontend usage | Test coverage | Notes |
| --- | --- | --- | --- | --- |
| `GET` | `/api/health` | Boot health badge | `test_api_hardening.py` | Public endpoint. |
| `GET` | `/api/worker-status` | Operator readiness endpoint | `test_worker_health.py`, `test_operator_controls.py` | Reports heartbeat and persistent pause state. |
| `GET` | `/api/action-center` | Dashboard onboarding and reminders | `test_action_center.py` | Authenticated and owner-scoped. |
| `GET` | `/api/diagnostics` | Settings diagnostics panel | `test_doctor.py` | Visible and tested through doctor coverage. |
| `GET` | `/api/metrics` | Operator/runbook endpoint | `test_api_hardening.py` | Lightweight JSON counters for local/operator monitoring. |
| `GET` | `/api/analytics` | Dashboard Insights panel | `test_analytics.py` | User-scoped local product analytics; no external tracking. |
| `POST` | `/api/auth/register` | Auth form create account | `test_api.py`, `test_auth_security.py` | Visible and tested. |
| `POST` | `/api/auth/login` | Auth form sign in | `test_api.py`, `test_auth_security.py` | Visible and tested. |
| `POST` | `/api/auth/logout` | Sidebar sign out | `test_auth_security.py` | Visible and tested. |
| `GET` | `/api/auth/me` | Boot current user | `test_auth_security.py` | Visible through user email. |
| `DELETE` | `/api/auth/me` | Settings privacy delete action | `test_data_portability.py` | Visible and tested. |
| `GET` | `/api/audit-events` | Settings privacy activity review | `test_data_portability.py` | Visible and tested; owner-scoped and sanitized. |
| `GET` | `/api/platforms` | Account, template, mapping, listing platform controls and compliance notes | `test_api.py`, `test_ui_wording.py` | Visible and tested. |
| `GET` | `/api/listings` | Dashboard/listing list with search/filter/sort/page controls | `test_api_hardening.py` | Visible and tested. |
| `POST` | `/api/listings` | New listing button | `test_api.py` | Visible and tested. |
| `GET` | `/api/listings/{listing_id}` | Not directly used | `test_api.py` | Useful for future deep-linking. |
| `PATCH` | `/api/listings/{listing_id}` | Listing editor save | `test_listing_revisions.py`, `test_api.py` | Visible and tested. |
| `DELETE` | `/api/listings/{listing_id}` | Listing editor delete | `test_api.py` | Visible and tested. |
| `POST` | `/api/listings/{listing_id}/duplicate` | Listing editor duplicate | `test_listing_revisions.py` | Visible and tested. |
| `POST` | `/api/listings/{listing_id}/images` | Listing image upload | `test_storage_uploads.py`, `test_api.py` | Visible and tested. |
| `PATCH` | `/api/listings/{listing_id}/images/order` | Image tile up/down buttons | `test_storage_uploads.py` | Visible and tested. |
| `DELETE` | `/api/listings/{listing_id}/images/{image_id}` | Image tile delete | `test_storage_uploads.py` | Visible and tested. |
| `POST` | `/api/listings/{listing_id}/platforms` | Platform selection and description overrides | `test_listing_revisions.py`, `test_category_mappings.py` | Visible and tested. |
| `GET` | `/api/listings/{listing_id}/validate` | Validate button | `test_api.py`, `test_category_mappings.py` | Visible and tested. |
| `GET` | `/api/listings/{listing_id}/quality` | Listing quality assistant panel | `test_listing_quality.py` | Visible and tested; explicit `deterministic_local` provider, no external data transfer, and user-applied suggestions only. |
| `POST` | `/api/listings/{listing_id}/publish` | Queue assisted package button | `test_api.py`, `test_category_mappings.py`, `test_worker.py` | Visible and tested. |
| `GET` | `/api/jobs` | Dashboard/latest jobs and queue view with platform/status/sort/page controls | `test_worker.py` | Visible and tested. |
| `GET` | `/api/jobs/{job_id}` | Not directly used | `test_worker.py` | Useful for future deep-linking. |
| `POST` | `/api/jobs/{job_id}/retry` | Queue job detail retry button | `test_worker.py` | Visible and tested. |
| `POST` | `/api/jobs/{job_id}/manual-completion` | Queue job detail manual completion form | `test_api.py`, `test_job_polling_ui.py` | Visible and tested; only assisted jobs waiting for user action can be confirmed. |
| `GET` | `/api/accounts` | Accounts list with platform/status/sort/page controls | `test_api.py`, `test_extended_query_controls.py` | Visible and tested. |
| `POST` | `/api/accounts` | Account form | `test_api.py` | Visible and tested. |
| `PATCH` | `/api/accounts/{account_id}` | Account edit flow | `test_api.py`, `test_extended_query_controls.py` | Visible and tested; connection metadata is scrubbed. |
| `DELETE` | `/api/accounts/{account_id}` | Account list delete button | `test_api.py` | Visible and tested. |
| `GET` | `/api/templates` | Settings template list with search/platform/sort/page controls | `test_api.py`, `test_data_portability.py`, `test_extended_query_controls.py` | Visible and tested. |
| `POST` | `/api/templates` | Settings template form | `test_api.py`, `test_data_portability.py` | Visible and tested. |
| `PATCH` | `/api/templates/{template_id}` | Settings template edit flow | `test_api.py` | Visible and tested. |
| `DELETE` | `/api/templates/{template_id}` | Settings template delete button | `test_api.py` | Visible and tested. |
| `GET` | `/api/category-mappings` | Settings mapping list with source/platform/sort/page controls | `test_category_mappings.py`, `test_data_portability.py`, `test_extended_query_controls.py` | Visible and tested. |
| `POST` | `/api/category-mappings` | Settings mapping form | `test_category_mappings.py`, `test_data_portability.py` | Visible and tested. |
| `PATCH` | `/api/category-mappings/{mapping_id}` | Settings mapping edit flow | `test_category_mappings.py` | Visible and tested. |
| `DELETE` | `/api/category-mappings/{mapping_id}` | Settings mapping delete | `test_category_mappings.py` | Visible and tested. |
| `GET` | `/api/export` | Settings export JSON | `test_data_portability.py` | Visible and tested. |
| `POST` | `/api/import` | Settings import JSON | `test_data_portability.py` | Visible and tested. |
| `GET` | `/api/export/listings.csv` | Settings export listings CSV | `test_data_portability.py` | Visible and tested. |
| `POST` | `/api/import/listings.csv` | Settings import listings CSV | `test_data_portability.py` | Visible and tested. |
| `GET` | `/api/export/images.zip` | Settings export images ZIP | `test_data_portability.py` | Visible and tested. |

## Required Follow-Up

- Keep query controls aligned as additional list screens are added.
- Keep image reorder coverage aligned if drag-and-drop replaces the current up/down controls.
- Keep this audit updated whenever a route is added, removed, or made visible in the UI.
