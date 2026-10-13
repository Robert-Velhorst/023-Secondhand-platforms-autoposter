from pathlib import Path


def test_final_repository_search_keeps_production_acceptance_open():
    content = Path("docs/FINAL_NO_EXCUSES_SEARCH.md").read_text(encoding="utf-8")

    required_phrases = [
        "final repository search",
        "not final production-launch acceptance",
        "not release-ready",
        "Real non-technical user walkthrough is not executed",
        "Deployment database, worker, backup, production secrets, and CORS evidence are missing",
        "docs/FINAL_ACCEPTANCE_RECORD.md is not accepted",
        "Eleven phases remain `Partial`",
        "remains partial",
    ]
    for phrase in required_phrases:
        assert phrase in content
