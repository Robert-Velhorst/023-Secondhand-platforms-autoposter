# UI Action Audit

This audit maps visible dashboard actions to behavior in `public/app.js` and backend endpoints. It complements `docs/API_USAGE_AUDIT.md`, which maps routes to frontend usage.

## Summary

- Core navigation, listing, image, validation, quality, publishing, queue, account, template, category mapping, diagnostics, data portability, and privacy actions are wired.
- Some actions are intentionally local-only, such as tab navigation, copy-to-clipboard, suggestion application, and form reset/cancel behavior.
- Executed Chromium workflow evidence exists for core seller flows; full keyboard, screen-reader, zoom, and cross-browser launch QA remains tracked separately.

## Auth And Shell

| UI action | Handler | Backend behavior | Status |
| --- | --- | --- | --- |
| Sign in | `#authForm submit` | `POST /api/auth/login` | Wired |
| Create account | `#registerButton click` | `POST /api/auth/register` | Wired |
| Sign out | `#logoutButton click` | `POST /api/auth/logout` then local token clear | Wired |
| Sidebar navigation | `.nav click` | Local view switch | Wired |
| Boot current user | `boot()` | `GET /api/auth/me`, `GET /api/health` | Wired |

## Dashboard

| UI action | Handler | Backend behavior | Status |
| --- | --- | --- | --- |
| Load dashboard metrics and insights | `loadAll()` / `renderDashboard()` | `GET /api/listings`, `/api/jobs`, `/api/accounts`, `/api/templates`, `/api/category-mappings`, `/api/analytics` | Wired |
| Click recent listing | `#recentListings click` | Local selection and view switch | Wired |
| Click latest job | `#jobList click` from queue list pattern; dashboard latest jobs are display-only | Local display only | Intentional |
| Open onboarding step or reminder | `#onboardingSteps` / `#actionCenterList click` | Owner-scoped state from `GET /api/action-center`, then local navigation | Wired |

## Listings

| UI action | Handler | Backend behavior | Status |
| --- | --- | --- | --- |
| New listing | `#newListingButton click` | `POST /api/listings` | Wired |
| Refresh listings | `#refreshButton click` | Reloads list endpoints | Wired |
| Search/filter/sort/page listings | query control handlers | `GET /api/listings` with query parameters | Wired |
| Select listing | `#listingList click` | Local selection | Wired |
| Save listing | `#listingForm submit` | `PATCH /api/listings/{id}` and platform override saves | Wired |
| Autosave listing fields | listing form `input` / `change`, 1.2 second debounce | `PATCH /api/listings/{id}` with visible pending, saving, saved, or recovery state | Wired |
| Apply template | `#applyTemplateButton click` | Local description update before save | Wired |
| Duplicate listing | `#duplicateButton click` | `POST /api/listings/{id}/duplicate` | Wired |
| Delete listing | `#deleteListingButton click` | `DELETE /api/listings/{id}` | Wired |

## Quality, Images, And Platforms

| UI action | Handler | Backend behavior | Status |
| --- | --- | --- | --- |
| Run quality check | `#qualityButton click` | `GET /api/listings/{id}/quality` | Wired |
| Apply quality suggestion | `#qualityAssistant click` | Local form update before save | Wired |
| Focus quality/missing-field fix | quality/prepublish click handlers | Local focus/scroll | Wired |
| Upload images | `#imageInput change` | `POST /api/listings/{id}/images` | Wired |
| Reorder images | `#imageList click` move buttons | `PATCH /api/listings/{id}/images/order` | Wired |
| Delete image | `#imageList click` delete button | `DELETE /api/listings/{id}/images/{image_id}` | Wired |
| Select platform / edit platform description | `#platformList change/input` plus save paths | Local review-state invalidation; `POST /api/listings/{id}/platforms` during save/validate/publish | Wired |
| Validate platforms | `#validateButton click` | `GET /api/listings/{id}/validate` | Wired |
| Copy prepublish package or field | `#prepublishReview click` | Clipboard/local fallback | Wired |
| Queue assisted package | `#publishButton click` | `POST /api/listings/{id}/publish` | Wired |

## Queue

| UI action | Handler | Backend behavior | Status |
| --- | --- | --- | --- |
| Refresh jobs | `#refreshJobsButton click` | Reloads list endpoints | Wired |
| Pause/resume live job refresh | `#jobPollingToggle click` | Local polling state; `GET /api/jobs` and analytics refresh while enabled | Wired |
| Filter/sort/page jobs | queue query handlers | `GET /api/jobs` with query parameters | Wired |
| Open job details | `#jobList click` | Local detail render from loaded jobs | Wired |
| Retry job | `#retryJobButton click` | `POST /api/jobs/{id}/retry` | Wired |
| Record manual completion | `#manualCompletionForm submit` | `POST /api/jobs/{id}/manual-completion` | Wired |

## Accounts

| UI action | Handler | Backend behavior | Status |
| --- | --- | --- | --- |
| Save account | `#accountForm submit` | `POST /api/accounts` | Wired |
| Edit account | `#accountList click` / `#accountForm submit` | `PATCH /api/accounts/{account_id}` | Wired |
| Delete account | `#accountList click` | `DELETE /api/accounts/{id}` | Wired |

## Settings

| UI action | Handler | Backend behavior | Status |
| --- | --- | --- | --- |
| Save template | `#templateForm submit` | `POST /api/templates` or `PATCH /api/templates/{id}` | Wired |
| Edit template | `#templateList click` | Local form population | Wired |
| Delete template | `#templateList click` | `DELETE /api/templates/{id}` | Wired |
| Cancel template edit | `#cancelTemplateEditButton click` | Local form reset | Wired |
| Save category mapping | `#categoryMappingForm submit` | `POST /api/category-mappings` or `PATCH /api/category-mappings/{id}` | Wired |
| Edit category mapping | `#categoryMappingList click` | Local form population | Wired |
| Delete category mapping | `#categoryMappingList click` | `DELETE /api/category-mappings/{id}` | Wired |
| Export JSON | `#exportDataButton click` | `GET /api/export`, browser download | Wired |
| Import JSON | `#importDataInput change` | `POST /api/import` | Wired |
| Run diagnostics | `#runDiagnosticsButton click` | `GET /api/diagnostics` | Wired |
| Delete my account data | `#deleteMyDataButton click` | prompt confirmation, then `DELETE /api/auth/me` | Wired |

## Remaining UI Audit Gaps

- This is source-level wiring evidence, not an executed browser walkthrough.
- Dashboard latest-job cards are currently display-only; opening details happens from the Queue list.
- Browser evidence is still needed for copy-to-clipboard fallback, file import/export, mobile layout, keyboard flow, and destructive confirmation clarity.
- Visible queue wording now says `Queue assisted package` and `Assisted package queue` to avoid implying automatic marketplace submission.
