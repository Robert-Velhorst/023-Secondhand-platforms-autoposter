# Acceptance Tests

Date: 2026-07-12

## Scope

The local acceptance suite covers the product's core seller workflow through the API. Executed
browser evidence for registration, onboarding, listing creation, autosave, action-center refresh,
and mobile layout is recorded in `docs/BROWSER_ACCESSIBILITY_QA.md`.

## Automated Acceptance Flow

`tests/test_acceptance_workflow.py` verifies that a seller can:

- register and authenticate;
- create platform account metadata without leaking raw tokens through export;
- create a description template;
- create a category mapping;
- create a rich listing;
- upload a valid image;
- run the listing quality assistant;
- validate mapped fields for Marktplaats;
- queue and process an assisted posting package;
- review the resulting queue/job details;
- view local analytics;
- export owned data;
- import the export into another account;
- review privacy/audit activity for the export.

## Boundary

This is acceptance coverage for the application contract and seller workflow. It does not claim cross-browser UI execution, real marketplace submission, production deployment, or official API publishing.
