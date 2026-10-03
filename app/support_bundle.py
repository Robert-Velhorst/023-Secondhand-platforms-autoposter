from __future__ import annotations

import argparse
import json
import platform
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import Settings, get_settings, validate_startup_safety
from app.database import SessionLocal
from app.doctor import run_checks
from app.feature_flags import feature_flag_summary
from app.models import PublishingJob
from app.services.operator_controls import operator_control_status
from app.version import __version__


def sanitized_runtime_summary(settings: Settings) -> dict:
    parsed = urlparse(settings.database_url)
    return {
        "app_env": settings.app_env,
        "app_version": __version__,
        "database_backend": parsed.scheme.split("+", 1)[0],
        "storage_backend": settings.storage_backend,
        "auth_transport": settings.auth_transport,
        "log_format": settings.log_format,
        "default_locale": settings.default_locale,
        "supported_locales": settings.supported_locale_list,
        "suggestion_provider": settings.suggestion_provider,
        "feature_flags": feature_flag_summary(settings),
        "cors_restricted": settings.cors_origins.strip() != "*",
        "public_base_url_https": settings.public_base_url.startswith("https://"),
        "secrets_present": {
            "secret_key_non_default": settings.secret_key not in {"", "change-me-in-production"},
            "ebay_client_id": bool(settings.ebay_oauth_client_id.strip()),
            "ebay_client_secret": bool(settings.ebay_oauth_client_secret.strip()),
        },
    }


def job_status_summary(db: Session) -> dict[str, int]:
    return {
        status: count
        for status, count in db.query(PublishingJob.status, func.count(PublishingJob.id))
        .group_by(PublishingJob.status)
        .all()
    }


def build_support_bundle(output_path: Path, settings: Settings, db: Session) -> Path:
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payloads = {
        "metadata.json": {
            "generated_at": datetime.now(UTC).isoformat(),
            "app_version": __version__,
            "python_version": platform.python_version(),
            "platform": sys.platform,
        },
        "runtime-summary.json": sanitized_runtime_summary(settings),
        "doctor.json": run_checks(settings),
        "operator-control.json": operator_control_status(db),
        "job-status-summary.json": job_status_summary(db),
    }
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in payloads.items():
            archive.writestr(name, json.dumps(payload, indent=2, sort_keys=True, default=str))
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a sanitized diagnostics bundle")
    parser.add_argument("--output", default="autoposter-support-bundle.zip")
    args = parser.parse_args(argv)
    settings = get_settings()
    validate_startup_safety(settings)
    db = SessionLocal()
    try:
        output = build_support_bundle(Path(args.output), settings, db)
    finally:
        db.close()
    print(json.dumps({"status": "ok", "output": str(output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
