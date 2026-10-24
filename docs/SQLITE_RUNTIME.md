# Verified project-local SQLite runtime

The application selects SQLite **3.54.1** with CPython **3.15.1** before an
application database can be opened. `sqlite-runtime.json` pins upstream archive
checksums and Windows binary hashes. The current release and archive checksums
were checked against [SQLite's download page](https://www.sqlite.org/download.html).

## Provisioning and startup

From the repository root, using the selected Python environment:

```text
python -I scripts/setup_sqlite_runtime.py
```

Provisioning downloads only the pinned official SQLite assets and, for a Mac
SDK that embeds SQLite, the pinned exact CPython source. Files stay under
`.autoposter-runtime/sqlite/3.54.1/<profile>`. Windows uses the verified official
DLL. Linux builds the verified amalgamation with a thread-safe configuration.
Mac profiles build an SDK-specific standard SQLite extension against the
verified library. Neither the global SDK nor operator databases are modified.
Existing mismatched Windows binaries are rejected instead of overwritten.

For source entrypoints and child processes, select the early bootstrap:

```powershell
$env:PYTHONPATH = "$PWD/runtime_bootstrap;$PWD"
```

```sh
export PYTHONPATH="$PWD/runtime_bootstrap:$PWD"
```

The bootstrap runs before third-party modules can initialize the older SDK
binding. Application package import also enforces the guard. There are no
runtime downloads or fallback to an older library. Unsupported ABIs, wrong
Python versions, linked runtime paths, missing assets, checksum/provenance
mismatches, early SQLite initialization or incorrect active engine versions
stop startup. Only an in-memory database is used to report the version,
source identity and compile options before application data access.

## Packaging and container behavior

The Windows build provisions the DLL, verifies its hash and bundles it under
the same nested runtime layout. A runtime hook loads it before application
imports. The older root-level SDK SQLite DLL is omitted. The candidate supports:

```text
SecondhandAutoposter.exe --native-runtime-info
```

This emits version/hash information and exits before creating operator data,
starting services or opening a browser. CI requires the report to come from
the frozen executable and match the pinned DLL. Normal launch, migrations,
worker ownership, shutdown and recovery still need their separate acceptance.

The Docker candidate uses pinned Python 3.15.1 / Alpine 3.24. A builder compiles
the verified library and creates a signed local `sqlite-libs` APK. The private
build key is removed within that build step; only the temporary public key is
copied into the runtime for offline installation, then removed. Global Alpine
trust is unchanged. The project and system library hashes must match, and the
installed package must report `3.54.1-r0`. UID 10001 is required. The final
application image excludes compilers, dev dependencies and pip.

An independent CI job probes the image without networking, capabilities,
published ports or operator volumes. It reconciles the saved archive with the
inspected image/configuration, then scans every OS/Python package using pinned
Trivy 0.76.1. No advisory ignore or severity exclusion is configured. Any
finding, missing inventory, image mismatch or direct dependency mismatch fails.

## Dated qualification scope

On 24 October 2026, local Windows x64 provisioning and fresh-process startup
reported SQLite 3.54.1 with DLL SHA-256
`4b59d3cded9dc1608544160f3b4b10ac974c6ac0d6ffc23064e5f4c8dbd05aea`.
The source launcher's version-only path also passed without services or
operator database access. The separate SDK probe still reported its original
3.53.1 library. Lint, compilation and YAML/PowerShell/spec parsing passed.

The native head still requires hosted Linux/database, frozen Windows and
container inventory/scan results. Other listed platform profiles, real
operator backup/restore, browser/provider and Hetzner deployment acceptance
remain unqualified. Earlier green CI at `3469b80` predates this native change.

At `ec37aa8`, PostgreSQL integration and the frozen Windows native identity
job passed. Application verification passed 529 cases and skipped one; the
remaining clean-checkout fixture omitted the new runtime assets. That fixture
now carries the verified profile, specification and early bootstrap into its
isolated checkout. Its data/migration/API/worker assertions remain in place.

The first Alpine build stopped because PyYAML 6.0.3 has no public CPython 3.15
musl wheel. The corrected builder compiles the hash-pinned source using pip
26.2.2, setuptools 84.2.1, wheel 0.48.0 and Cython 3.3.0, all locked with
hashes. Ad hoc build dependency resolution is disabled. Only the installed
runtime prefix is copied to the final image; compilers and build tools stay
in the builder. The native LibYAML extension is required, with the stable
Alpine `yaml` package supplying its shared library. The corrected head requires
new CI; no passing image is claimed before that scan completes.

A separate local native inventory also found OpenSSL 3.5.9 in the selected
SDK and libpq 18.4 in the current Psycopg binary package. These remain below
the independently checked [OpenSSL 4.1.0 release](https://github.com/openssl/openssl/releases/tag/openssl-4.1.0)
and [PostgreSQL/libpq 18.6 target](https://www.postgresql.org/support/versioning/).
They were inventoried without a database connection and are not upgraded by
this SQLite change. Active native component qualification remains incomplete.

The provisioning, loader and image-identity pattern was adapted from
[Simbi's reviewed source](https://github.com/Robert-Velhorst/022-Simbi-Reach-out/commit/1af92c40c74a842d1ea4e6ee920f429e4f054e04).
The application's recovery and operator approval boundaries remain in place.
