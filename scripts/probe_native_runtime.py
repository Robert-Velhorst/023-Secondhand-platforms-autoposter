"""Report the verified engine using memory only; never open operator records."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from app.sqlite_runtime import runtime_evidence

parser = argparse.ArgumentParser()
parser.add_argument("--image", action="store_true")
arguments = parser.parse_args()
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
print(json.dumps(report, sort_keys=True))
