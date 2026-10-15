# PostgreSQL 16 to 18 migration

This guide applies to the optional `postgres` service in `docker-compose.yml`.
The Compose service keeps its named volume, but PostgreSQL 18 uses
`/var/lib/postgresql/18/docker` while the existing PostgreSQL 16 cluster is at
`/var/lib/postgresql/data`. The startup preflight refuses to serve an empty
replacement database while the older cluster is still present.

This is an offline logical migration for the local Compose profile. It does not
migrate the production Hetzner database. Do not run `docker compose down
--volumes` during this process.

## Before changing the image

Stop API and worker writes, then make a verified PostgreSQL custom-format dump
while the PostgreSQL 16 service is still running. Store it outside the
repository and keep an independent copy:

```powershell
docker compose exec -T postgres pg_dump -Fc -U autoposter -d autoposter > autoposter.pg16.dump
```

Confirm that the dump is non-empty. Keep the original `postgres-data` volume
and the dump until the migrated application is accepted and a fresh PostgreSQL
18 backup has been verified.

## Initialize and restore PostgreSQL 18

After switching to the reviewed Compose configuration, initialize only the
database service once with the temporary allow setting. The PostgreSQL 18
cluster is created beside the untouched PostgreSQL 16 files; do not start the
API or worker yet.

```powershell
$env:AUTOPOSTER_POSTGRES18_ALLOW_EMPTY_TARGET = '1'
docker compose --profile postgres up -d postgres
Remove-Item Env:AUTOPOSTER_POSTGRES18_ALLOW_EMPTY_TARGET
```

Copy the dump into the running database container and restore it, stopping at
the first error:

```powershell
docker compose cp .\autoposter.pg16.dump postgres:/tmp/autoposter.pg16.dump
docker compose exec -T postgres pg_restore --exit-on-error --no-owner -U autoposter -d autoposter /tmp/autoposter.pg16.dump
```

Verify the application tables, representative row counts, and Alembic state
against the dump. Then create the completion marker as root in the database
container:

```powershell
docker compose exec -T -u 0 postgres sh -ec 'touch "$PGDATA/.autoposter-postgres18-migration-complete"'
```

Only after verification and the marker are in place should you run
`alembic upgrade head` and start the API and worker. Keep the PostgreSQL 16
files and dump until the upgraded application passes its acceptance checks.

## Recovery

If restoration or verification fails, stop the PostgreSQL 18 and application
containers. Remove no volumes. Preserve the dump and logs, then start a separate
PostgreSQL 16 container against a copy of the saved volume or restore the
pre-upgrade backup. Do not point PostgreSQL 16 at the PostgreSQL 18 data
directory.
