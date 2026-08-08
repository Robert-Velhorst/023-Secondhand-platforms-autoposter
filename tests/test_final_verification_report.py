from pathlib import Path


def test_final_verification_report_matches_current_local_gate():
    content = Path("docs/FINAL_VERIFICATION_REPORT.md").read_text(encoding="utf-8")

    required_phrases = [
        "Date: 2026-08-08",
        "Pytest suite: passed, 210 tests.",
        "Release gate: blocked as expected",
        "python scripts/release_gate.py",
        "python scripts/release_gate.py --json",
        "Final response preflight: blocked as expected",
        "total missing evidence count",
        "total missing evidence count of 77",
        "not release-ready yet",
        "Not captured",
        "final acceptance is not accepted",
        "not yet a final client launch release",
    ]
    for phrase in required_phrases:
        assert phrase in content
