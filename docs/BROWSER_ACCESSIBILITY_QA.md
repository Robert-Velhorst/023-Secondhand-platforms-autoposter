# Browser And Accessibility QA Checklist

This checklist captures the manual browser, responsive, and accessibility checks required before a client launch.

Automated source-level accessibility smoke coverage is tracked separately in `docs/ACCESSIBILITY_AUDIT.md`. This checklist remains the manual browser, keyboard, zoom, screen-reader, and responsive launch gate.

Executed Chromium evidence for the prepublish safety review is recorded in `docs/BROWSER_PREPUBLISH_WALKTHROUGH.md`. That evidence is intentionally narrower than this full launch checklist.

Executed Chromium evidence for frontend error and recovery behavior is recorded in `docs/BROWSER_ERROR_UX_WALKTHROUGH.md`. That evidence is also narrower than this full launch checklist.

Executed UI/UX debugging rounds are summarized in `docs/UI_UX_DEBUGGING_ROUNDS.md`.

Executed responsive and browser compatibility evidence is recorded in `docs/RESPONSIVE_BROWSER_COMPATIBILITY.md`. This checklist remains open for keyboard, zoom, and screen-reader launch evidence.

## 2026-08-08 Local Browser Evidence

The in-app Chromium browser executed this fresh-account flow against
`http://127.0.0.1:8013` on the working checkout:

1. register a local test user;
2. verify the five-step onboarding/action center;
3. create a first listing;
4. edit title, price, category, location, and description;
5. observe the visible `Saved automatically` state and revision increment;
6. return to the dashboard and verify the first onboarding step changed to `Done`;
7. verify the missing-image reminder and refreshed local analytics;
8. reload at a 390 x 844 viewport and confirm navigation, metrics, onboarding, and the reminder remain reachable.

The page reported no browser console warning or error during this flow. The browser screenshot
transport produced tiled captures, so DOM snapshots and semantic interaction results are the
authoritative evidence for this run. This does not close the production-candidate keyboard, 200%
zoom, screen-reader, Firefox, Safari/iOS, or Android checks below.

## Scope

Run this against the exact deployment candidate and environment that will be shown to users.

Minimum browsers:

- Chrome or Edge on desktop.
- Firefox on desktop.
- Safari on iOS or Chrome on Android.

Minimum viewport sizes:

- 390 x 844 mobile.
- 768 x 1024 tablet.
- 1366 x 768 laptop.
- 1920 x 1080 desktop.

## Setup

1. Start from a fresh user account.
2. Use production-like settings:
   - `APP_ENV=production`
   - non-default `SECRET_KEY`
   - restrictive `CORS_ORIGINS`
   - `AUTH_TRANSPORT=bearer`
   - `JOB_PROCESS_INLINE=false` when a worker is expected
3. Run `python scripts/verify.py` before beginning browser checks.
4. Keep browser developer tools open and treat console errors as findings.

## Core Workflow Checks

- Register a new account.
- Sign out and sign back in.
- Create a listing with title, description, price, condition, category, location, and delivery options.
- Upload at least one valid image.
- Reject an invalid image type and confirm the error is understandable.
- Validate the listing for Marktplaats and eBay.
- Queue assisted posting jobs.
- Confirm queued jobs appear in the Queue view.
- Run the worker and confirm job status/log updates are visible.
- Retry a retryable job only when the UI makes the action clear.
- Create, edit, apply, and delete a template.
- Create, edit, and delete a category mapping.
- Create and delete a platform account metadata record.
- Export user data.
- Import the export into a different account.
- Delete the original account and confirm the session no longer works.

## Responsive Layout Checks

- No text overlaps controls or adjacent content.
- Tables, lists, forms, and job cards remain readable at each viewport size.
- Primary actions remain visible without horizontal page scrolling.
- Dialogs and long panels fit within the viewport or scroll internally.
- Image thumbnails keep stable dimensions while loading and after upload.
- Filter, sort, and pagination controls remain usable on mobile.
- The sidebar/navigation remains reachable on mobile.

## Keyboard Checks

- Every interactive control can be reached with `Tab`.
- Focus order follows the visual workflow.
- The focused element is visibly indicated.
- Buttons can be activated with `Enter` or `Space` as appropriate.
- Form fields can be edited without mouse interaction.
- Modal/dialog focus does not disappear behind the page.
- Destructive actions are not triggered accidentally by a single stray keypress.

## Accessibility Checks

- Every visible form field has an accessible label.
- Error messages are visible near the relevant action or field.
- Global errors are announced or placed where keyboard users encounter them.
- Text contrast is readable in normal and disabled states.
- Status badges do not rely on color alone.
- Uploaded image controls expose useful text for remove/reorder actions.
- Page headings and section headings form a sensible hierarchy.
- Browser zoom at 200 percent does not hide essential actions.

## Evidence To Capture

- Date and commit SHA.
- Deployment URL or local URL.
- Browser/version matrix used.
- Viewport sizes checked.
- Account used for the walkthrough.
- Screenshots of the listing editor, queue, settings, and mobile layout.
- Console errors or network failures, if any.
- Accessibility findings and whether each is blocking or non-blocking.

## Pass Criteria

The release candidate passes this checklist only when:

- all core workflows complete without unhandled errors,
- no blocking accessibility issue remains,
- no responsive layout prevents normal task completion,
- no console error indicates a broken API call or missing asset,
- launch blockers are copied into `docs/RELEASE_READINESS.md` or an issue tracker.
