# Legacy Script Quarantine

The repository still retains pre-existing Selenium/browser automation scripts under `legacy/selenium/`. They are not imported by the FastAPI app, not run at startup, and not required by `requirements.txt`.

Optional dependencies for these scripts live in `requirements-legacy.txt`.

The historical configuration example is retained separately at
[`legacy/selenium/.env.example`](../legacy/selenium/.env.example). It is reference
material, not web-app configuration or evidence that those scripts work today.
The root `.env.example` contains only current application settings and can be
copied for development without deleting a legacy section. Existing `.env` files
are not rewritten automatically: remove legacy-only keys from the web-app
configuration yourself, preserving any needed historical values separately.
Do not weaken strict settings validation to accommodate legacy values or run
legacy automation as part of verifying the new application's setup.

## Rules

- Do not run legacy scripts in production app startup.
- Do not commit real credentials, LastPass secrets, cookies, browser profiles, scraped data, or downloaded images.
- Do not bypass CAPTCHAs, anti-bot controls, login protections, SMS prompts, payment prompts, or platform security systems.
- Run only in a user-controlled local browser session when platform terms and account permissions allow it.
- Prefer official APIs for future production automation.

## Quarantined Legacy Files

| File | Purpose | Risk | Current Status |
| --- | --- | --- | --- |
| `legacy/selenium/main.py` | Old orchestrator for scraping Tweedehands and posting elsewhere through Selenium/LastPass. | High: credentials, browser automation, platform controls. | Legacy reference only. Not used by web app. |
| `legacy/selenium/scrape_second_hand.py` | Old Tweedehands scraping flow. | High: authenticated scraping and local CSV/images. | Legacy reference only. |
| `legacy/selenium/markplaats.py` | Old Marktplaats Selenium login/posting helper. | High: login, cookies, 2FA, paid/free placement choices. | Legacy reference only. Current app uses assisted adapter. |
| `legacy/selenium/post_koopplein.py` | Old Koopplein Selenium posting helper. | Medium/high: account login and posting. | Legacy reference only. Current app uses assisted adapter. |
| `legacy/selenium/post_nextdoor.py` | Old Nextdoor Selenium posting helper. | High: neighborhood/account controls and anti-abuse flows. | Legacy reference only. Current app uses assisted adapter. |
| `legacy/selenium/post_ebay.py` | Old eBay Selenium posting helper. | High: CAPTCHA, SMS, marketplace policy, paid/shipping setup. | Legacy reference only. Current app uses assisted adapter. |
| `legacy/selenium/nlp_hanlder.py` | Old spaCy category matching helper. | Low runtime risk, but has a typo in filename and requires heavy model dependency. | Legacy reference only. |
| `legacy/selenium/test.py` | Old standalone spaCy test script. | Low, but not part of app tests. | Legacy reference only. |
| `legacy/selenium/setup.sh`, `legacy/selenium/start.desktop`, `legacy/selenium/stop.desktop`, `legacy/selenium/stop.sh`, `legacy/selenium/main.spec` | Old packaging/startup helpers. | Medium: unclear relation to new app. | Legacy reference only. |

## Duplicate Nested Folder

The old duplicate source folder was moved to `legacy/archive/023-Secondhand-platforms-autoposter-main/`.

The runtime script files in that archive were hash-checked against the quarantined `legacy/selenium/` copies and matched. The remaining archive-only files are old context files: `.env.example`, `.gitignore`, `Readme.md`, and `requirements.txt`.

## Future Quarantine Work

1. Keep `LEGACY_SCRIPTS.md` current for users who still expect the old scripts.
2. Keep tests proving root legacy entrypoints stay quarantined and `app.main` does not import Selenium, LastPass, spaCy, or legacy modules.
3. Remove the archive only after an explicit product decision that the old reference source is no longer useful.
