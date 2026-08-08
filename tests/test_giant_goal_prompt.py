from pathlib import Path

REQUIRED_ARTIFACTS = {
    "docs/TECHNICAL_AUDIT.md",
    "docs/CRITICAL_PATH.md",
    "docs/ACCEPTANCE_TESTS.md",
    "docs/GOAL_COMPLETION_MATRIX.md",
    "docs/FINAL_VERIFICATION_REPORT.md",
    "docs/UI_ACTION_AUDIT.md",
    "docs/API_USAGE_AUDIT.md",
    "docs/SECURITY.md",
    "docs/OPERATOR_RUNBOOK.md",
    "docs/CODEX_WORKLOG.md",
    "docs/CODEX_CHECKPOINTS.md",
    "docs/TASK_GRAPH.md",
}


def test_goal_prompt_required_artifacts_exist():
    assert not {path for path in REQUIRED_ARTIFACTS if not Path(path).is_file()}


def test_release_tooling_and_honest_provider_contract_are_documented():
    readme = Path("README.md").read_text(encoding="utf-8")
    runbook = Path("docs/OPERATOR_RUNBOOK.md").read_text(encoding="utf-8")
    security = Path("docs/SECURITY.md").read_text(encoding="utf-8")

    for command in ("app.operator_control", "app.reconcile", "app.support_bundle"):
        assert command in readme
        assert command in runbook
    assert "deterministic_local" in readme
    assert "assisted" in security.lower()
