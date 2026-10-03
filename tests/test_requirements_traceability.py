from pathlib import Path

STATUSES = {"Implemented", "Partial", "Missing", "Blocked", "Not applicable"}
MATRIX_PATH = "docs/GOAL_COMPLETION_MATRIX.md"


def phase_statuses(path: str = MATRIX_PATH) -> dict[int, str]:
    statuses: dict[int, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not cells[0].isdigit():
            continue
        status = next((cell for cell in cells[1:] if cell in STATUSES), None)
        if status:
            statuses[int(cells[0])] = status
    return statuses


def summary_counts(path: str = MATRIX_PATH) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        for status in STATUSES:
            prefix = f"- {status}: "
            if stripped.startswith(prefix):
                counts[status] = int(stripped.removeprefix(prefix).removesuffix("."))
    return counts


def test_goal_matrix_covers_every_pdf_phase_exactly_once():
    matrix = phase_statuses()

    assert len(matrix) == 116
    assert set(matrix) == set(range(116))


def test_completion_matrix_summary_matches_phase_rows():
    matrix = phase_statuses()
    summary = summary_counts()

    assert summary == {status: list(matrix.values()).count(status) for status in sorted(STATUSES)}


def test_traceability_groups_cover_full_phase_range_and_compatibility_path_is_canonicalized():
    traceability = Path("docs/REQUIREMENTS_TRACEABILITY.md").read_text(encoding="utf-8")
    compatibility = Path("docs/COMPLETION_MATRIX.md").read_text(encoding="utf-8")

    phase_ranges = (
        "0-4", "5-9", "10-14", "15-19", "20-27", "28-36", "37-48",
        "49-58", "59-67", "68-77", "78-88", "89-99", "100-105", "106-115",
    )
    for phase_range in phase_ranges:
        assert f"| {phase_range} |" in traceability
    assert "docs/GOAL_COMPLETION_MATRIX.md" in compatibility
