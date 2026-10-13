from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class FeatureFlagSettings(Protocol):
    dev_auto_login: bool
    auto_create_tables: bool
    job_process_inline: bool


@dataclass(frozen=True)
class FeatureFlag:
    name: str
    env_var: str
    enabled: bool
    production_allowed: bool
    description: str
    production_error: str


def build_feature_flags(settings: FeatureFlagSettings) -> tuple[FeatureFlag, ...]:
    return (
        FeatureFlag(
            name="dev_auto_login",
            env_var="DEV_AUTO_LOGIN",
            enabled=settings.dev_auto_login,
            production_allowed=False,
            description="Create a local demo session without normal login.",
            production_error="DEV_AUTO_LOGIN must be false in production",
        ),
        FeatureFlag(
            name="auto_create_tables",
            env_var="AUTO_CREATE_TABLES",
            enabled=settings.auto_create_tables,
            production_allowed=False,
            description="Create database tables automatically at app startup.",
            production_error="AUTO_CREATE_TABLES must be false in production; run Alembic migrations explicitly",
        ),
        FeatureFlag(
            name="inline_job_processing",
            env_var="JOB_PROCESS_INLINE",
            enabled=settings.job_process_inline,
            production_allowed=False,
            description="Process publish jobs inside the API request instead of only through the worker.",
            production_error="JOB_PROCESS_INLINE must be false in production; run a separate worker process",
        ),
    )


def enabled_feature_flags(settings: FeatureFlagSettings) -> tuple[FeatureFlag, ...]:
    return tuple(flag for flag in build_feature_flags(settings) if flag.enabled)


def unsafe_production_feature_flags(settings: FeatureFlagSettings) -> tuple[FeatureFlag, ...]:
    return tuple(flag for flag in enabled_feature_flags(settings) if not flag.production_allowed)


def feature_flag_summary(settings: FeatureFlagSettings) -> dict[str, bool]:
    return {flag.name: flag.enabled for flag in build_feature_flags(settings)}
