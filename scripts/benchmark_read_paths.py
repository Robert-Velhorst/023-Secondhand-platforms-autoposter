"""Measure read paths on disposable, synthetic SQLite data; never opens app data."""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
import tracemalloc
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Listing, PlatformListingMapping, PublishingJob, User, WorkerHeartbeat
from app.services.action_center import build_action_center
from app.services.analytics import build_user_analytics
from app.services.worker_health import worker_status


def seed(db: Session, size: int) -> None:
    now = datetime.now(UTC)
    db.execute(User.__table__.insert(), {"id": 1, "email": "benchmark@example.com", "password_hash": "unused"})
    db.execute(Listing.__table__.insert(), [
        {"id": i, "owner_id": 1, "title": f"Benchmark item {i}", "price_cents": 1000,
         "internal_notes": "unused notes " * 100, "status": "draft"}
        for i in range(1, size + 1)
    ])
    db.execute(PlatformListingMapping.__table__.insert(), [
        {"id": i, "listing_id": i, "platform": "marktplaats", "status": "draft", "overrides": {"unused": "x" * 1000}}
        for i in range(1, size + 1)
    ])
    db.execute(PublishingJob.__table__.insert(), [
        {"id": i + 1, "listing_id": (i % size) + 1, "platform": "marktplaats", "status": "published",
         "idempotency_key": f"benchmark-{i}", "result": {"unused": "x" * 2000}}
        for i in range(size * 5)
    ])
    db.execute(WorkerHeartbeat.__table__.insert(), [
        {"worker_id": f"old-{i}", "started_at": now - timedelta(days=2),
         "last_seen_at": now - timedelta(days=1), "processed_jobs": 100}
        for i in range(size * 10)
    ] + [{"worker_id": "active", "started_at": now, "last_seen_at": now, "processed_jobs": 7}])
    db.commit()


def measure(engine, callback, repeats: int) -> dict:
    elapsed = []
    peaks = []
    loaded_counts = []
    result = None
    for _ in range(repeats):
        gc.collect()
        loaded = 0

        def track_load(_session, _instance):
            nonlocal loaded
            loaded += 1

        with Session(engine) as db:
            event.listen(db, "loaded_as_persistent", track_load)
            tracemalloc.start()
            started = time.perf_counter()
            result = callback(db)
            elapsed.append((time.perf_counter() - started) * 1000)
            peaks.append(tracemalloc.get_traced_memory()[1])
            tracemalloc.stop()
            loaded_counts.append(loaded)
    if result is not None:
        result.pop("generated_at", None)
        result.pop("last_heartbeat_at", None)
        result.pop("last_worker_started_at", None)
    return {"median_ms_with_tracing": round(median(elapsed), 2),
            "peak_python_bytes": max(peaks), "loaded_orm_objects": max(loaded_counts), "result": result}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listings", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.listings < 1 or args.repeats < 1:
        parser.error("listings and repeats must be positive")
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            seed(db, args.listings)
        print(json.dumps({
            "fixture": {"listings": args.listings, "jobs": args.listings * 5,
                        "stale_workers": args.listings * 10},
            "worker_status": measure(engine, lambda db: worker_status(db, 3600), args.repeats),
            "analytics": measure(engine, lambda db: build_user_analytics(db, 1), args.repeats),
            "action_center": measure(engine, lambda db: build_action_center(db, 1), args.repeats),
        }, default=str, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
