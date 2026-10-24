# Source-built image client libraries

This candidate extends the SQLite and dependency stage in PR #120. Keep that
green PR's head unchanged until its separate merge decision is resolved.

The Linux image builds OpenSSL 4.1.0 and the PostgreSQL 18.6 client library from
the official archives pinned in `native-client-runtime.json`. Archive SHA-256
checks run before extraction. Only the client library and required build support
are compiled; no PostgreSQL server is built, started or connected.

The dedicated `/opt/autoposter-native` prefix keeps system and SDK libraries
separate. The builder exports source identity, library hashes and native version
calls. Ephemerally signed Alpine packages register libcrypto4, libssl4 and libpq
in the image's installed inventory; their upstream origins and versions remain
visible to the existing complete image scan. Private package-signing keys stay
in a single disposable builder step and do not enter the runtime image.

`requirements-image.txt` changes only Psycopg's extra from `binary` to `c`, at the
same pinned 3.3.6 version. Its separate hash lock is constrained by the existing
runtime lock. The C extension compiles against the selected pg_config and client
libraries using the locked wheel build tools. Windows dependencies and packaging
continue to use the existing binary extra; no operator installation is changed.

The existing image probe requires the C implementation, libpq 18.6, OpenSSL
4.1.0, matching library hashes, expected installed package versions and a loaded
libpq path under the dedicated prefix. It performs no database connection.
The image verifier requires these packages and rejects retained psycopg-binary.
The zero-finding raw scan gate remains unchanged.

## Qualification limits

Source preparation and lock resolution are not proof that this image builds.
Require current-head hosted build, native identity and complete scan evidence.
The existing host-side PostgreSQL integration job still uses its binary driver.
The image job additionally reuses the same eight PostgreSQL check files against
the unchanged candidate image, its C driver and an owned PostgreSQL 18.6 service.
Only hash-locked pure-Python pytest tools are mounted; no application or native
packages are installed over the candidate image. Runtime runs as UID 10001 with
read-only filesystems and bounded temporary fixtures.

The service uses a one-day CI-only certificate and TLS 1.3. The native probe
requires the exact disposable database name, service hostname, public dummy
credential, certificate path and `verify-full` mode. It verifies the actual TLS
session using PostgreSQL's own session metadata. The service and image run on a
dedicated internal Docker network with no published ports or external egress.
Its private key is outside the retained artifact directory. Neither the service
nor fixture certificate is operator infrastructure or production PKI.

This additional current-head qualification is pending until hosted evidence
passes. Live deployment, operator database recovery and provider acceptance
remain separate. No existing test cases are added, removed or relaxed.

CPython's own SSL extension still links its SDK's OpenSSL. The new PostgreSQL
TLS library does not update that extension or the Windows SDK. Older system
crypto packages can also remain for other tools. Those versions and the Windows
libpq 18.4 runtime remain explicit outstanding work for the full portfolio goal.

Sources: [OpenSSL 4.1.0](https://github.com/openssl/openssl/releases/tag/openssl-4.1.0),
[PostgreSQL 18.6 source](https://www.postgresql.org/ftp/source/v18.6/).
