# User Guide

This guide explains the current assisted-posting workflow for a seller using the dashboard. It does not describe automatic marketplace submission; every registered platform still requires user-controlled final action on the marketplace.

## Sign In And Create A Listing

1. Register or sign in with email and password.
2. Open Listings.
3. Select New listing.
4. Fill the core fields: title, price, condition, category, location, description, delivery details, category attributes, and optional item specifics.
5. Upload one or more product images.
6. Save the listing.

The app keeps a revision number for each listing. Editing a listing creates a new revision, and assisted package idempotency uses that revision so repeated queueing does not create duplicate jobs for the same package.

## Improve Listing Quality

Use Quality assistant from the listing editor. It scores buyer-readiness, flags missing or weak fields, adds category-specific checks for common categories such as electronics, furniture, fashion, and vehicles, and offers deterministic suggestions. Suggestions are not applied automatically; choose Apply for each suggestion you want.

## Prepare Platform Packages

1. Select the target platforms.
2. Add a platform-specific description variant if needed.
3. Select Validate.
4. Review platform capabilities, compliance notes, and the prepublish cards.
5. Fix missing fields or copy mapped fields from the review panel.
6. Select Queue assisted package.

The queue action prepares a package and job log. It does not log in to marketplaces, bypass account prompts, choose paid placement, or submit the marketplace listing.

Use Regenerate package only when you intentionally want a fresh assisted package for the current listing. It creates a new listing revision before queueing.

## Queue And Job Review

Open Queue to watch assisted package jobs. The queue supports:

- platform, status, sorting, and paging controls;
- manual refresh;
- live refresh with pause/resume;
- job logs;
- user-confirmed manual completion with marketplace URL and optional listing ID;
- retry guidance.

Retry only after fixing the listing, platform account, or validation issue that caused the previous job to fail. For `needs_user_action` jobs, retry is mainly for regenerating package output after a deliberate listing change.

Selecting Queue assisted package again for the same unchanged listing and platform/account returns the original job, even if it failed or was skipped. This protects against double clicks and repeated requests; it is not a retry. Use the eligible job's retry action after correcting the problem, or save a listing change or deliberately select Regenerate package to queue a new revision. A successful request alone does not mean the package succeeded: read the job's status and log.

After you finish the marketplace-side posting steps, open the job details, paste the marketplace listing URL, optionally add the listing ID, and record completion. The app updates the job and platform mapping from your confirmation; it still treats final marketplace submission as manual.

## Accounts, Templates, And Mappings

Accounts identify the platform account context and setup status. You can create, edit, disable, or delete account metadata. The app strips token-like keys from manual connection metadata and does not expose raw platform passwords, active marketplace tokens, or secret references.

The normal dashboard can prepare assisted packages without choosing a saved platform account. If an integration selects one, it must be your account for that marketplace. An unavailable or mismatched account is rejected before the request creates jobs or a new revision. If an account's marketplace changes after a job was queued, that job fails safely when processed. Restore the correct account details before retrying, or prepare a new package using a suitable account; retry cannot switch an existing job to another account. This does not sign you into a marketplace or enable automatic posting.

Templates help reuse description text. Use variants such as `default`, `short`, `seasonal`, or platform-specific copy styles to keep multiple reusable versions under clear labels. Category mappings translate a master listing category into a platform-specific category. Both settings screens support search/filter/sort/page controls.

## Data Portability And Privacy

Use Export JSON to download portable listing/configuration data. The JSON export excludes password hashes, sessions, platform tokens, raw secrets, and image binaries. Use Export listings CSV or Import listings CSV for spreadsheet workflows. Use Export images ZIP when you need a separate archive of uploaded image files with a manifest. Use Import JSON to restore supported portable data into the current account.

Delete my account data removes owned listings, jobs, templates, mappings, accounts, sessions, and uploaded local image files.

The Privacy activity list shows recent sanitized export, import, image export, and deletion-related audit events for your own account. It does not show raw exported data, platform secrets, or email hashes.

## Diagnostics

Run diagnostics from Settings to inspect startup safety, database, migrations, upload directory, platform adapters, and legacy script isolation. A local-development warning can be acceptable, but production launch requires the release readiness gate.

## Known Limits

- final marketplace submission is manual for all registered production platforms.
- eBay OAuth/token foundations exist, but official publishing is not implemented.
- Browser/accessibility walkthrough evidence is still required before final launch.
- Deployment-specific PostgreSQL, edge security, backup, and rate-limit evidence is still required before client launch.
