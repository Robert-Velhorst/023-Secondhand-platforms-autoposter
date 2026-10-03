# Bug Hunt Log

## 2026-08-08

| Area | Finding | Resolution |
| --- | --- | --- |
| Goal traceability | Repository tracked 89 phases while supplied PDF defines 116 | Added canonical 116-phase matrix and synchronized tests. |
| Listing form | No autosave despite explicit goal phase | Added debounced autosave with visible recovery copy. |
| Suggestions | Deterministic logic lacked a named provider/security boundary | Added fail-closed local provider abstraction and disclosure. |
| Workflow guidance | Dashboard metrics did not guide a first-time or exception-driven user | Added owner-scoped onboarding and reminders. |
| Operations | Worker lacked a persistent emergency stop | Added database-backed pause/resume/status CLI. |
| Support | No dedicated sanitized debug bundle | Added support bundle with secret-presence booleans only. |
| Data repair | No executable reconciliation command | Added check-only default and explicitly safe image-order repair. |

No fake marketplace success was introduced. Remaining launch findings are listed in `docs/ROADMAP_AND_BLOCKED_ITEMS.md`.

## 2026-10-03

| Area | Finding | Resolution |
| --- | --- | --- |
| Listing-to-marketplace delivery data | A normal listing had pickup enabled, but the UI sent an empty `delivery_options` object, so Marktplaats validation still reported delivery details missing. The raw JSON textarea also gave no indication that basic choices were already available. | The form now derives `delivery_options.pickup` and `delivery_options.shipping` from the existing checkboxes, preserves additional object fields, handles non-object JSON safely, and explains the optional extra details in English and Dutch. A fresh Windows standalone UI run confirmed validation no longer reports `delivery_options`; only the deliberately omitted image remains missing. |
| Dutch UI completeness | Switching to Dutch translates navigation and form labels, but platform compliance copy, validation/job states, and several native option values remain English. | Open. The implementation should localize data-driven platform warnings and option/status labels, then verify rendered English and Dutch flows. |
