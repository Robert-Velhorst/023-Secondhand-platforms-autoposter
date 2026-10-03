# License and Third-Party Service Review

Python dependency inventory is pinned in `requirements.txt` and audited by `scripts/audit_dependencies.py` plus the supply-chain workflow. JavaScript has no runtime package bundle in the shipped static frontend; Playwright is development/browser-evidence tooling.

Third-party operational boundaries:

- Marktplaats, Koopplein, Nextdoor, and Tweedehands are assisted destinations only. Their names and links identify user-selected destinations and do not imply partnership or API approval.
- eBay OAuth and Inventory API access verification are foundations only. Production publishing is disabled until developer-account approval, credentials, policy review, sandbox proof, and ambiguous-outcome handling exist.
- S3-compatible object storage is optional and operator-provided. Bucket policy, region, retention, and service terms remain deployment choices.

Before launch, the acceptance owner must review current dependency licenses, marketplace terms, privacy agreements, and storage/data-processing terms. No repository document grants provider authorization.
