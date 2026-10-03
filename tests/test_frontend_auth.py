"""Deterministic JS state checks; rendered Playwright QA is recorded separately."""

import shutil
import subprocess

import pytest


def test_shipped_frontend_auth_handlers():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the frontend auth state checks")
    result = subprocess.run(
        [node, "--test", "--test-reporter=tap", "tests/frontend_auth.test.cjs"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "# pass 11" in result.stdout
