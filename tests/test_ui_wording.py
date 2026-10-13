from pathlib import Path


def public_text() -> str:
    return "\n".join(
        [
            Path("public/index.html").read_text(encoding="utf-8"),
            Path("public/app.js").read_text(encoding="utf-8"),
        ]
    )


def test_frontend_uses_assisted_package_wording_for_queue_action():
    content = public_text()

    required_phrases = [
        "Queue assisted package",
        "Assisted package queue",
        "Assisted package queued",
        "manual submit",
    ]
    for phrase in required_phrases:
        assert phrase in content


def test_frontend_avoids_automatic_publishing_claims():
    content = public_text().lower()

    blocked_phrases = [
        "queue publish",
        "publishing queue",
        "fully automated",
        "automatic marketplace",
        "auto publish",
        "autopublish",
        "published for you",
    ]
    for phrase in blocked_phrases:
        assert phrase not in content


def test_frontend_surfaces_platform_compliance_notes():
    script = Path("public/app.js").read_text(encoding="utf-8")
    styles = Path("public/styles.css").read_text(encoding="utf-8")

    assert "complianceNotesHtml" in script
    assert "platform.compliance_notes" in script
    assert "Compliance" in script
    assert ".compliance-panel" in styles


def test_delivery_options_explains_that_basic_delivery_choices_are_automatic():
    content = public_text()

    assert "Pickup and shipping selections are included automatically" in content
    assert "Ophalen en verzenden worden automatisch opgenomen" in content
