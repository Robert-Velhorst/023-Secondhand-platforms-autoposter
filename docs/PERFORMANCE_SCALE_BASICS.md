# Performance And Scale Basics

This project is still a small-operator app, but the core API should stay predictable as listings, images, and jobs grow.

## Current Baseline

- List endpoints use bounded `limit` and `offset` parameters.
- The frontend requests paged listing and job data instead of loading unbounded records.
- The dashboard uses one owner-scoped aggregate endpoint instead of separate analytics/action-center/recent-item round trips.
- Listing, job, account, template, and mapping filters refresh only their own page.
- Jobs are processed by a separate worker when `JOB_PROCESS_INLINE=false`.
- Large binary image files are kept out of JSON export/import.
- Publishing jobs use idempotency keys to prevent duplicate work for the same listing revision and platform.
- PostgreSQL pool size, overflow, timeout, and recycle values are bounded environment settings.
- SQLite standalone mode enables foreign keys, WAL, a busy timeout, and normal synchronous mode for safe single-operator concurrency.
- Worker health uses database aggregates for fresh workers and reads only the latest heartbeat's timestamps; stale worker history is not materialized in Python.
- Analytics groups job counts and platform selection counts in SQL. Exact listing quality statistics are accumulated in batches of 250 listings, without loading job results or platform override payloads.
- The action center uses owner-scoped existence checks and at most 20 candidates per reminder category. Its final 20 retain the same severity and lexical-ID ordering. It does not load complete inventory or job history.

## Reproducible Local Read Benchmark — 2026-09-05

```powershell
python scripts/benchmark_read_paths.py --listings 1000 --repeats 3
```

The script creates only disposable in-memory SQLite data: 1,000 listings and mappings, 5,000 completed jobs containing result payloads, and 10,000 stale workers plus one active worker. It never opens the configured application database. Each sample uses a fresh session. Results include peak Python allocations, ORM object loads, and the complete normalized response so behavior can be compared alongside resource use.

Measured on this Windows 11 host with Python 3.14, comparing commit `62c52f7` with the read-path optimization:

| Path | Before median | After median | Before peak Python memory | After peak Python memory |
| --- | ---: | ---: | ---: | ---: |
| Worker health | 657.07 ms | 6.74 ms | 14.27 MiB | 1.37 MiB |
| Analytics | 1,860.89 ms | 452.00 ms | 34.35 MiB | 1.55 MiB |
| Action center | 1,069.53 ms | 36.33 ms | 34.20 MiB | 0.29 MiB |

All three normalized responses matched the baseline exactly on this fixture. Separate regression tests cover owner isolation, stale/paused worker reporting, mixed reminder types, priority, and the 20-item limit.

These medians are from three runs **with `tracemalloc` enabled**; tracing adds overhead. Peak memory describes Python allocations during each call, not total process RAM or database memory. The fixture is synthetic and timings are not production latency guarantees. Analytics still evaluates every owned listing for exact quality statistics; batching bounds memory, not total CPU work. Target PostgreSQL query plans and concurrent workloads still need measurement.

Compatibility was also verified on a disposable PostgreSQL 16.15 container limited to one CPU and 256 MiB RAM: Alembic migrated an empty database to `20260809_0013`, then all six read-path resource/behavior tests passed against that server with transaction-isolated fixtures. This includes the `json_array_length` filter supported by [PostgreSQL](https://www.postgresql.org/docs/current/functions-json.html) and [SQLite](https://www.sqlite.org/json1.html). This local database drill does not prove the supplied staging/production environment is configured or ready.

## Database Indexes

The schema now includes indexes for common read and maintenance paths:

- Listings by owner, status, and recent update order.
- Listing images by listing and display position.
- Platform accounts by owner, platform, status, and creation order.
- Category mappings by owner, platform, and source category.
- Publishing jobs by listing, platform, status, creation order, and due queue order.
- Job logs, attempts, drafts, and sessions by their parent records.

The index migration is idempotent because the initial Alembic revision creates current metadata on fresh databases.

## Operational Limits

- Keep API list limits capped at 100 unless a specific route has a measured need for larger batches.
- Keep worker batches controlled by `JOB_WORKER_BATCH_SIZE`.
- Prefer background job processing in production-style deployments.
- Do not add marketplace polling loops without platform-specific cooldowns and quota handling.
- Do not include image binaries in normal JSON exports.

## Remaining Scale Work

- Capture PostgreSQL migration and representative query evidence on the supplied target before production launch.
- Add query timing or metrics around list endpoints and worker batches.
- Validate `FOR UPDATE SKIP LOCKED` job claiming under the target PostgreSQL workload before scaling to multiple workers.
- Move local uploads to object storage for larger deployments.
