import os
import subprocess
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app import models  # noqa: F401
from app.database import Base


def test_alembic_cli_uses_database_url_environment(tmp_path):
    db_path = tmp_path / "cli-migration-test.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "operator_controls" in inspect(create_engine(env["DATABASE_URL"])).get_table_names()


def test_alembic_migration_runs_from_empty_database(tmp_path):
    db_path = tmp_path / "migration-test.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    tables = set(inspect(engine).get_table_names())

    assert "alembic_version" in tables
    assert "users" in tables
    assert "listings" in tables
    assert "listing_images" in tables
    assert "publishing_jobs" in tables
    assert "publishing_job_logs" in tables
    image_columns = {column["name"] for column in inspect(engine).get_columns("listing_images")}
    assert "file_size" in image_columns
    assert "checksum_sha256" in image_columns
    session_columns = {column["name"] for column in inspect(engine).get_columns("user_sessions")}
    assert "revoked_at" in session_columns
    listing_columns = {column["name"] for column in inspect(engine).get_columns("listings")}
    assert "revision" in listing_columns
    assert "pickup_allowed" in listing_columns
    assert "shipping_cost_cents" in listing_columns
    assert "brand" in listing_columns
    assert "category_attributes" in listing_columns
    assert "internal_notes" in listing_columns
    job_columns = {column["name"] for column in inspect(engine).get_columns("publishing_jobs")}
    assert "listing_revision" in job_columns
    assert "action_type" in job_columns
    assert "operation_mode" in job_columns
    template_columns = {column["name"] for column in inspect(engine).get_columns("listing_templates")}
    assert "variant" in template_columns
    listing_indexes = {index["name"] for index in inspect(engine).get_indexes("listings")}
    assert "ix_listings_owner_updated_at" in listing_indexes
    job_indexes = {index["name"] for index in inspect(engine).get_indexes("publishing_jobs")}
    assert "ix_publishing_jobs_due_queue" in job_indexes
    template_indexes = {index["name"] for index in inspect(engine).get_indexes("listing_templates")}
    assert "ix_listing_templates_owner_variant" in template_indexes
    assert "audit_events" in tables
    assert "login_throttles" in tables
    assert "platform_oauth_states" in tables
    assert "worker_heartbeats" in tables
    assert "operator_controls" in tables
    audit_columns = {column["name"] for column in inspect(engine).get_columns("audit_events")}
    assert "user_email_hash" in audit_columns
    assert "event_data" in audit_columns
    audit_indexes = {index["name"] for index in inspect(engine).get_indexes("audit_events")}
    assert "ix_audit_events_user_created_at" in audit_indexes
    assert "ix_audit_events_action_created_at" in audit_indexes
    assert "ix_publishing_jobs_listing_platform_status" in job_indexes
    throttle_columns = {column["name"] for column in inspect(engine).get_columns("login_throttles")}
    assert "identifier_hash" in throttle_columns
    assert "attempts" in throttle_columns
    throttle_indexes = {index["name"] for index in inspect(engine).get_indexes("login_throttles")}
    assert "ix_login_throttles_identifier_hash" in throttle_indexes
    oauth_state_columns = {column["name"] for column in inspect(engine).get_columns("platform_oauth_states")}
    assert "state_hash" in oauth_state_columns
    assert "consumed_at" in oauth_state_columns
    oauth_state_indexes = {index["name"] for index in inspect(engine).get_indexes("platform_oauth_states")}
    assert "ix_platform_oauth_states_state_hash" in oauth_state_indexes
    assert "ix_platform_oauth_states_expires_at" in oauth_state_indexes
    control_columns = {column["name"] for column in inspect(engine).get_columns("operator_controls")}
    assert control_columns >= {"job_processing_paused", "reason", "updated_by", "updated_at"}


def test_model_schema_renders_for_postgresql_dialect():
    dialect = postgresql.dialect()
    rendered = []

    for table in Base.metadata.sorted_tables:
        rendered.append(str(CreateTable(table).compile(dialect=dialect)))
        for index in table.indexes:
            rendered.append(str(CreateIndex(index).compile(dialect=dialect)))

    sql = "\n".join(rendered)

    assert "CREATE TABLE users" in sql
    assert "CREATE TABLE listings" in sql
    assert "CREATE TABLE publishing_jobs" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "JSON" in sql
    assert "CREATE INDEX ix_publishing_jobs_due_queue" in sql
    assert "ON DELETE CASCADE" in sql
