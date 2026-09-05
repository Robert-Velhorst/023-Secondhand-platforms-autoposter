from pathlib import Path


def test_production_compose_requires_migrations_before_services_start():
    content = Path("docker-compose.production.yml").read_text(encoding="utf-8")

    assert 'command: ["alembic", "upgrade", "head"]' in content
    assert "condition: service_completed_successfully" in content
    assert "worker:" in content
    assert "UPLOAD_VOLUME" in content
    assert "postgres:" not in content


def test_production_environment_template_uses_safe_required_values():
    content = Path(".env.production.example").read_text(encoding="utf-8")

    required = [
        "APP_ENV=production",
        "AUTH_TRANSPORT=bearer",
        "AUTO_CREATE_TABLES=false",
        "JOB_PROCESS_INLINE=false",
        "DATABASE_URL=postgresql+psycopg://",
        "WORKER_HEARTBEAT_TIMEOUT_SECONDS=30",
    ]
    for value in required:
        assert value in content


def test_ci_workflows_use_immutable_node24_action_pins_and_least_privilege():
    workflows = [
        Path(".github/workflows/verify.yml").read_text(encoding="utf-8"),
        Path(".github/workflows/supply-chain.yml").read_text(encoding="utf-8"),
    ]

    for content in workflows:
        event_block = content.split("permissions:", 1)[0]
        concurrency_block = content.split("concurrency:", 1)[1].split("jobs:", 1)[0]

        assert "push:" in event_block
        assert "pull_request:" in event_block
        assert "pull_request:" not in concurrency_block
        assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1" in content
        assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0" in content
        assert "permissions:\n  contents: read" in content
        assert "timeout-minutes: 15" in content
        assert "@v4" not in content
        assert "@v5" not in content


def test_dependabot_covers_python_and_github_actions():
    content = Path(".github/dependabot.yml").read_text(encoding="utf-8")

    assert "package-ecosystem: pip" in content
    assert "package-ecosystem: github-actions" in content
    assert "package-ecosystem: docker" in content


def test_container_build_context_excludes_local_state_and_runs_unprivileged():
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8").splitlines()
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert {".git", ".venv", ".tmp", ".env", ".env.*", "data", "uploads", "legacy", "tests"} <= set(
        dockerignore
    )
    assert "COPY . ." not in dockerfile
    assert "COPY --chown=autoposter:autoposter app ./app" in dockerfile
    assert "USER autoposter" in dockerfile
    assert "FROM python:3.12-slim@sha256:" in dockerfile
