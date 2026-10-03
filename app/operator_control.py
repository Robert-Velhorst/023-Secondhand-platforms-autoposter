from __future__ import annotations

import argparse
import json

from app.config import get_settings, validate_startup_safety
from app.database import SessionLocal
from app.services.operator_controls import operator_control_status, set_job_processing_paused


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect or change worker emergency controls")
    parser.add_argument("action", choices=("status", "pause", "resume"))
    parser.add_argument("--reason", default="", help="Required for pause")
    parser.add_argument("--actor", default="operator-cli")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_startup_safety(get_settings())
    db = SessionLocal()
    try:
        if args.action == "status":
            status = operator_control_status(db)
        else:
            try:
                status = set_job_processing_paused(
                    db,
                    paused=args.action == "pause",
                    reason=args.reason,
                    updated_by=args.actor,
                )
            except ValueError as exc:
                print(json.dumps({"status": "error", "message": str(exc)}, sort_keys=True))
                return 2
        print(json.dumps({"status": "ok", **status}, sort_keys=True))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
