from pathlib import Path


def frontend_script() -> str:
    return Path("public/app.js").read_text(encoding="utf-8")


def test_frontend_centralizes_listing_review_state_resets():
    script = frontend_script()

    required_fragments = [
        "function resetListingReviewState()",
        "state.validationResults = {};",
        "state.qualityResult = null;",
        "function selectListing(listingId",
        "function markSelectedListingMutated()",
        "selectListing(null)",
        "selectListing(clone.id)",
        "markSelectedListingMutated();",
    ]
    for fragment in required_fragments:
        assert fragment in script


def test_frontend_invalidates_prepublish_state_when_platform_inputs_change():
    script = frontend_script()

    required_fragments = [
        '$(\"#platformList\").addEventListener("change"',
        '$(\"#platformList\").addEventListener("input"',
        "state.selectedPlatforms.add",
        "state.selectedPlatforms.delete",
        "resetListingReviewState();",
        "renderPrepublishReview(listing)",
        "[data-platform-description]",
    ]
    for fragment in required_fragments:
        assert fragment in script


def test_validation_requests_are_scoped_to_selected_platforms():
    script = frontend_script()

    required_fragments = [
        "const selectedPlatforms = [...state.selectedPlatforms];",
        "validate?platform=${encodeURIComponent(platform)}",
        "const results = (await Promise.all(validationRequests)).flat();",
    ]
    for fragment in required_fragments:
        assert fragment in script


def test_listing_form_has_debounced_autosave_with_visible_recovery_copy():
    script = frontend_script()

    required_fragments = [
        "function scheduleListingAutosave()",
        "setTimeout(autosaveSelectedListing, 1200)",
        '$("#listingForm").addEventListener("input", scheduleListingAutosave)',
        '$("#listingForm").addEventListener("change", scheduleListingAutosave)',
        '$("#editorMessage").textContent = "Saved automatically"',
        '$("#editorMessage").textContent = "Autosave failed - use Save to retry"',
    ]
    for fragment in required_fragments:
        assert fragment in script


def test_dashboard_renders_owner_scoped_action_center():
    script = frontend_script()

    assert 'api("/action-center")' in script
    assert "function renderActionCenter()" in script
    assert "data-action-view" in script
