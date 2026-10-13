from pathlib import Path

from tests.test_requirements_traceability import phase_statuses


def test_external_evidence_backlog_matches_partial_phases():
    matrix = phase_statuses()
    expected_partial_phases = {phase for phase, status in matrix.items() if status == "Partial"}
    content = Path("docs/EXTERNAL_EVIDENCE_BACKLOG.md").read_text(encoding="utf-8")

    for phase in expected_partial_phases:
        assert f"| {phase} |" in content

    for phase, status in matrix.items():
        if status != "Partial":
            assert f"| {phase} |" not in content


def test_external_evidence_backlog_names_capture_records():
    content = Path("docs/EXTERNAL_EVIDENCE_BACKLOG.md").read_text(encoding="utf-8")

    required_phrases = [
        "python scripts/release_gate.py",
        "docs/RELEASE_EVIDENCE_RECORD.md",
        "docs/NON_TECHNICAL_USER_WALKTHROUGH_RECORD.md",
        "docs/FINAL_ACCEPTANCE_RECORD.md",
        "docs/FINAL_NO_EXCUSES_SEARCH.md",
        "docs/FINAL_RESPONSE_REQUIREMENTS.md",
        "blocked on external evidence",
    ]
    for phrase in required_phrases:
        assert phrase in content
