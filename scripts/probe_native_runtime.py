"""Report the verified engine using memory only; never open operator records."""

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from app.sqlite_runtime import runtime_evidence

parser = argparse.ArgumentParser()
parser.add_argument("--image", action="store_true")
parser.add_argument("--postgres-ci", action="store_true")
arguments = parser.parse_args()
if arguments.postgres_ci and not arguments.image:
    parser.error("--postgres-ci requires --image")
evidence = runtime_evidence()
assert evidence["version"] == "3.54.1"
assert tuple(sys.version_info[:3]) == (3, 15, 1)
report = {
    "python": sys.version,
    "native_sqlite": evidence,
    "operator_database_opened": False,
    "deployment_acceptance": False,
}
if arguments.image:
    import ssl

    import psycopg
    import yaml

    native_root = Path("/opt/autoposter-native")
    native = json.loads((native_root / "share/build-provenance.json").read_text(encoding="utf-8"))
    assert psycopg.pq.__impl__ == "c", "The image must use the source-built C driver"
    assert psycopg.pq.version() == 180006
    for relative, digest in native["libraries"].items():
        assert hashlib.sha256((native_root / relative).read_bytes()).hexdigest() == digest
    crypto = ctypes.CDLL(str(native_root / "lib/libcrypto.so.4"))
    crypto.OpenSSL_version.argtypes = [ctypes.c_int]
    crypto.OpenSSL_version.restype = ctypes.c_char_p
    native_ssl = crypto.OpenSSL_version(0).decode("ascii")
    assert native_ssl.startswith("OpenSSL 4.1.0 ")
    loaded = {
        line.split()[-1]
        for line in Path("/proc/self/maps").read_text().splitlines()
        if len(line.split()) >= 6 and ".so" in line.split()[-1]
    }
    pq_paths = {path for path in loaded if Path(path).name.startswith("libpq.so")}
    assert pq_paths and all(path.startswith(str(native_root / "lib") + "/") for path in pq_paths)
    assert any(Path(path).name.startswith("libssl.so.4") for path in loaded)
    native_packages = json.loads(
        subprocess.check_output(
            [
                "apk",
                "--no-network",
                "query",
                "--from",
                "installed",
                "--installed",
                "--format",
                "json",
                "--fields",
                "name,version",
                "libcrypto4",
                "libssl4",
                "libpq",
            ],
            text=True,
        )
    )
    assert {item["name"]: item["version"] for item in native_packages} == {
        "libcrypto4": "4.1.0-r0",
        "libssl4": "4.1.0-r0",
        "libpq": "18.6-r0",
    }
    # The CPython SDK uses its own SSL module; reporting it separately avoids
    # conflating the new PostgreSQL TLS library with a Python SSL upgrade.
    report.update(
        postgres_client={
            "implementation": psycopg.pq.__impl__,
            "version": psycopg.pq.version(),
            "openssl": native_ssl,
            "loaded_libpq": sorted(pq_paths),
            "packages": native_packages,
            "provenance": native,
        },
        python_sdk_ssl=ssl.OPENSSL_VERSION,
    )
    assert yaml.__with_libyaml__, "The current PyYAML source must include the native LibYAML extension"
    report["libyaml"] = yaml._yaml.get_version_string()
    assert os.getuid() == 10001
    package = json.loads(
        subprocess.check_output(
            [
                "apk",
                "--no-network",
                "query",
                "--from",
                "installed",
                "--installed",
                "--format",
                "json",
                "--fields",
                "name,version",
                "sqlite-libs",
            ],
            text=True,
        )
    )
    assert package == [{"name": "sqlite-libs", "version": "3.54.1-r0"}]
    system_library = Path("/usr/lib/libsqlite3.so.0")
    owner = json.loads(
        subprocess.check_output(
            [
                "apk",
                "--no-network",
                "query",
                "--from",
                "installed",
                "--installed",
                "--format",
                "json",
                "--fields",
                "name,version",
                "--match",
                "owner",
                str(system_library),
            ],
            text=True,
        )
    )
    assert owner == package
    system_digest = hashlib.sha256(system_library.read_bytes()).hexdigest()
    assert system_digest == evidence["binary_sha256"]
    report.update(uid=os.getuid(), system_sqlite_package=package, system_sqlite_sha256=system_digest)
    if arguments.postgres_ci:
        # This optional connection is bound to the owned CI service and its
        # one-day fixture certificate. Never accept an operator database URL.
        dsn = os.environ.get("AUTOPOSTER_CI_POSTGRES_URL", "")
        target = urlsplit(dsn)
        expected_query = {
            "sslmode": "verify-full",
            "sslrootcert": "/qualification-tls/server.crt",
            "connect_timeout": "10",
        }
        if (
            target.scheme != "postgresql"
            or target.hostname != "postgres-ci"
            or target.port != 5432
            or target.username != "postgres"
            or target.password != "disposable-ci-password"
            or target.path != "/autoposter_job_test_image_ci"
            or target.fragment
            or sorted(parse_qsl(target.query)) != sorted(expected_query.items())
        ):
            raise RuntimeError("The native CI probe requires its exact disposable TLS service")
        with psycopg.connect(dsn, autocommit=True, options="-c default_transaction_read_only=on") as connection:
            server = connection.execute("SELECT current_setting('server_version_num')::int").fetchone()[0]
            tls = connection.execute(
                "SELECT ssl, version, cipher, bits FROM pg_stat_ssl WHERE pid = pg_backend_pid()"
            ).fetchone()
            assert server == 180006
            assert tls and tls[0] is True and tls[1] == "TLSv1.3" and tls[3] >= 128
        report["disposable_postgres"] = {
            "server_version": server,
            "tls_version": tls[1],
            "cipher": tls[2],
            "cipher_bits": tls[3],
            "certificate_mode": "verify-full",
            "client_implementation": psycopg.pq.__impl__,
            "client_version": psycopg.pq.version(),
            "read_only_probe": True,
        }
print(json.dumps(report, sort_keys=True))
